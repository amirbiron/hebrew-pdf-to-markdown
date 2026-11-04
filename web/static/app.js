// הדף של "PDF עברי ל-Markdown".
//
// כל מה שמגיע מהשרת נכנס לדף כטקסט (textContent), אף פעם לא כ-HTML: ה-Markdown, הסיבות, ההערות וההודעות הם תוכן
// של קובץ שמשתמש העלה, כלומר תוכן חיצוני (CRITICAL-PATTERNS.md, K4). בקובץ הזה אין innerHTML בכלל.
//
// התצוגה: ה-Markdown הגולמי, שורה אחרי שורה, בכיוון קבוע מימין לשמאל (dir="rtl" על #output, בלי unicode-bidi:
// plaintext). כך כל שורה מוצגת בפסקה עברית, וזה מה שבדיקת התצוגה של הקורא מאשרת. שורה שנראית לא נכון רק בגלל
// זה היא ממצא על הקורא, ולא משהו לתקן כאן.
//
// מה שמועתק ומורד הוא המחרוזת result.markdown כמו שהיא, ולא הטקסט של הדף: בדף יש גם הודעות (עמוד שנפסל) שאינן
// חלק מהקובץ.

"use strict";

(function () {
  const fileInput = document.getElementById("file");
  const convertButton = document.getElementById("convert");
  const statusLine = document.getElementById("status");
  const limitsLine = document.getElementById("limits");
  const result = document.getElementById("result");
  const output = document.getElementById("output");
  const pagesList = document.getElementById("pages");
  const actionStatus = document.getElementById("action-status");

  // המגבלה מהשרת (web/limits.py), שנכתבה לדף כשהוא הוגש. בדיקה מוקדמת בלבד: השרת בודק בעצמו
  const maxBytes = Number(limitsLine.dataset.maxBytes);
  // הזמן שהדף מחכה לתשובה, כדי שהכפתור לא יישאר כבוי לנצח מול חיבור שנתקע: ההעלאה (60 שניות) וההמרה (90) בשרת,
  // ועוד שוליים
  const RESPONSE_MS = 180000;
  const GENERIC_ERROR = "לא הצלחנו להשלים את ההמרה. נסו שוב בעוד רגע.";

  let current = null; // {markdown, pages, legend, downloadName}

  fileInput.addEventListener("change", () => {
    convertButton.disabled = !fileInput.files.length;
    clearResult();
    setStatus("");
  });
  convertButton.addEventListener("click", convert);
  document.getElementById("copy").addEventListener("click", copy);
  document.getElementById("download").addEventListener("click", download);

  // התוצאה שייכת לקובץ שהומר. כשנבחר קובץ אחר, או כשמתחילה המרה חדשה, היא יורדת מהדף, כדי שהעתקה והורדה לא
  // יפעלו על קובץ אחר משזה שמוצג בשדה, גם אם ההמרה החדשה נכשלת
  function clearResult() {
    current = null;
    result.hidden = true;
    output.replaceChildren();
    pagesList.replaceChildren();
    actionStatus.textContent = "";
  }

  function setStatus(text, isError) {
    statusLine.textContent = text;
    statusLine.classList.toggle("error", Boolean(isError));
  }

  async function convert() {
    const file = fileInput.files[0];
    if (!file) return;
    if (Number.isFinite(maxBytes) && file.size > maxBytes) {
      setStatus("הקובץ גדול מדי. " + limitsLine.textContent, true);
      return;
    }
    clearResult();
    convertButton.disabled = true;
    fileInput.disabled = true;
    setStatus("ממיר… בקובץ גדול זה יכול לקחת עד דקה וחצי.");
    try {
      const response = await fetch("/api/convert", {
        method: "POST",
        body: file,
        headers: { "Content-Type": "application/pdf" },
        signal: AbortSignal.timeout(RESPONSE_MS),
      });
      const body = await readJson(response);
      if (!response.ok || !body || typeof body.markdown !== "string" || !Array.isArray(body.pages)) {
        setStatus(body && typeof body.message === "string" ? body.message : GENERIC_ERROR, true);
        return;
      }
      show(body, file.name);
      setStatus("");
    } catch (error) {
      // רשת שנפלה או זמן שנגמר: אין תשובה מהשרת, ולכן הודעה כללית
      setStatus(GENERIC_ERROR, true);
    } finally {
      convertButton.disabled = !fileInput.files.length;
      fileInput.disabled = false;
    }
  }

  async function readJson(response) {
    // תשובה שאינה JSON (למשל דף שגיאה של פרוקסי) היא תשובה בלי הודעה, ולא חריגה
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  function show(body, fileName) {
    current = {
      markdown: body.markdown,
      pages: body.pages,
      legend: Array.isArray(body.legend) ? body.legend : [],
      downloadName: downloadName(fileName),
    };
    document.getElementById("result-name").textContent = fileName;
    document.getElementById("download-name").textContent = current.downloadName;
    renderSummary();
    renderOutput();
    renderPages();
    actionStatus.textContent = "";
    result.hidden = false;
    result.scrollIntoView({ block: "start" });
  }

  function renderSummary() {
    const counts = document.getElementById("summary");
    const legend = document.getElementById("legend");
    counts.replaceChildren();
    legend.replaceChildren();
    for (const entry of current.legend) {
      const count = current.pages.filter((page) => page.decision === entry.decision).length;
      const item = document.createElement("li");
      item.className = "count decision-" + entry.decision;
      const number = document.createElement("span");
      number.className = "count-number";
      number.textContent = String(count);
      const name = document.createElement("span");
      name.textContent = entry.text;
      item.append(number, name);
      counts.append(item);

      const term = document.createElement("dt");
      term.className = "decision-" + entry.decision;
      term.textContent = entry.text;
      const description = document.createElement("dd");
      description.textContent = entry.help;
      legend.append(term, description);
    }
  }

  function legendText(code) {
    const entry = current.legend.find((item) => item.decision === code);
    return entry ? entry.text : code;
  }

  // ה-Markdown כשורות: כל שורה ב-span משלה (#line-N), כדי שאפשר יהיה להגיע לשורה ולא רק לעמוד. העמודים מקובצים לפי
  // השורה של הסמן שלהם (page.line, מספר ה-"\n" לפניו), בסדר שבו הם מופיעים בטקסט
  function renderOutput() {
    const lines = current.markdown.split("\n");
    const starts = current.pages
      .filter((page) => Number.isInteger(page.line) && page.line >= 0 && page.line < lines.length)
      .slice()
      .sort((a, b) => a.line - b.line);
    output.replaceChildren();
    let segment = null;
    let next = 0;
    for (let i = 0; i < lines.length; i++) {
      while (next < starts.length && starts[next].line === i) {
        const page = starts[next++];
        segment = document.createElement("span");
        segment.className = "segment decision-" + page.decision;
        segment.id = "page-" + page.number;
        segment.tabIndex = -1;
        if (page.decision === "rejected") segment.append(rejectedBanner(page));
        output.append(segment);
      }
      const line = document.createElement("span");
      line.className = "line";
      line.id = "line-" + i;
      line.textContent = i < lines.length - 1 ? lines[i] + "\n" : lines[i];
      (segment || output).append(line);
    }
  }

  // עמוד שנפסל מסומן במקום שלו בפלט, כדי שלא ייראה כאילו הוא פשוט חסר. ההודעה היא חלק מהדף ולא מהקובץ: היא לא
  // נבחרת בסימון (user-select: none ב-style.css) ולא מועתקת
  function rejectedBanner(page) {
    const banner = document.createElement("span");
    banner.className = "banner";
    banner.setAttribute("role", "note");
    const reasons = page.reasons.map((reason) => reason.text).join("; ");
    banner.textContent = "עמוד " + page.number + " נפסל: " + reasons + ". " +
      "אם יש ממנו טקסט בקובץ שיורד, הוא חסר או שגוי בחלקו, ואין לסמוך עליו בלי להשוות ל-PDF.";
    return banner;
  }

  function renderPages() {
    pagesList.replaceChildren();
    for (const page of current.pages) {
      const item = document.createElement("li");
      item.className = "page decision-" + page.decision;

      const head = document.createElement("div");
      head.className = "page-head";
      const go = document.createElement("button");
      go.type = "button";
      go.className = "goto";
      go.textContent = "עמוד " + page.number;
      go.addEventListener("click", () => jump("page-" + page.number));
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = page.decision_text || legendText(page.decision);
      head.append(go, badge);
      item.append(head);

      if (page.reasons.length) item.append(entries("סיבות", page.reasons, "reasons"));
      if (page.notes.length) item.append(entries("הערות", page.notes, "notes"));
      pagesList.append(item);
    }
  }

  // רשימה של סיבות או הערות. כל אחת לבד, עם ההסבר שלה, ולא משפט אחד לעמוד
  function entries(title, list, kind) {
    const box = document.createElement("div");
    box.className = kind;
    const heading = document.createElement("p");
    heading.className = "entries-title";
    heading.textContent = title + ":";
    const ul = document.createElement("ul");
    for (const entry of list) {
      const li = document.createElement("li");
      const text = document.createElement("span");
      text.className = "entry-text";
      text.textContent = entry.text;
      li.append(text);
      if (typeof entry.help === "string") {
        const help = document.createElement("span");
        help.className = "entry-help";
        help.textContent = entry.help;
        li.append(help);
      }
      ul.append(li);
    }
    box.append(heading, ul);
    return box;
  }

  function jump(id) {
    const target = document.getElementById(id);
    if (!target) return;
    for (const old of output.querySelectorAll(".current")) old.classList.remove("current");
    target.classList.add("current");
    target.scrollIntoView({ block: "start" });
    target.focus({ preventScroll: true });
  }

  async function copy() {
    if (!current) return;
    try {
      // דורש הקשר מאובטח (HTTPS או localhost), ואחרת navigator.clipboard לא קיים (BY-STACK/browser-handoff.md, דפוס 2)
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(current.markdown);
      actionStatus.textContent = "ה-Markdown הועתק.";
    } catch (error) {
      actionStatus.textContent = "ההעתקה לא הצליחה בדפדפן הזה. אפשר להוריד את הקובץ במקום.";
    }
  }

  function download() {
    if (!current) return;
    const blob = new Blob([current.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = current.downloadName;
    document.body.append(link);
    link.click();
    link.remove();
    // הכתובת משוחררת אחרי שההורדה התחילה, ולא נשארת מחזיקה את התוכן בזיכרון (BY-STACK/browser-handoff.md, דפוס 5)
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    actionStatus.textContent = "";
  }

  // שם הקובץ להורדה, מהשם של הקובץ שהועלה. השם לא נשלח לשרת. הניקוי: בלי סיומת PDF; בלי תווי בקרה ותווי עיצוב
  // בלתי נראים (Cc, Cf: בהם תווי הכיוון, ש-U+202E שבהם הופך "fdp.exe" לשם שנראה אחר); בלי תווים שאסורים בשם קובץ
  // ב-Windows או מפרידים תיקיות; רווחים מכווצים, ובלי נקודות ורווחים בקצוות. אורך עד 120 תווים, לפי תווים ולא בתים.
  // שם שלא נשאר ממנו כלום מקבל שם כללי. שם שמור ב-Windows מקבל קידומת, גם כשאחריו סיומת: לפי Microsoft, "NUL.txt"
  // ו-"NUL.tar.gz" שווים ל-NUL, והרשימה היא CON, PRN, AUX, NUL, COM1 עד COM9, LPT1 עד LPT9, ו-COM ו-LPT עם ¹ ² ³
  // (https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file, Naming Conventions)
  function downloadName(original) {
    let stem = String(original || "").normalize("NFC").replace(/\.pdf$/iu, "");
    stem = stem.replace(/[\p{Cc}\p{Cf}]/gu, "");
    stem = stem.replace(/[\\/:*?"<>|]/gu, "_");
    stem = stem.replace(/\s+/gu, " ").replace(/^[\s.]+|[\s.]+$/gu, "");
    stem = Array.from(stem).slice(0, 120).join("").replace(/[\s.]+$/gu, "");
    if (!stem) stem = "document";
    if (/^(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(\.|$)/iu.test(stem)) stem = "_" + stem;
    return stem + ".md";
  }
})();
