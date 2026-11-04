"""כיול הספים של הציון (hebrew_pdf/score.py), בשלושת הכלים של מסמך האפיון ("כיול ומדידה"):

1. שגיאות מכוונות. לוקחים עמודים שהפלט שלהם ידוע כנכון (known_good: עמודים של קבצים עם דף תשובות שהפלט שלהם
   זהה לו, ועמודים שכל השורות המתויגות בהם זהות), ומשחיתים את הפלט בכל צורות הכשל שראינו (FORMS). ההשחתה היא
   של הטקסט שהקורא הוציא, ולא של הקורא: היא לא תלויה באיך הקורא הגיע לפלט. מה שבעמוד (Component.visual) ורשימת
   התווים של PDFium (PageText.reference) נשארים, כמו כשקורא שבור מוציא פלט שגוי מקובץ תקין. יוצאים מזה שני
   סוגים. "תווי בקרה במקום אותיות", שהוא כשל של הקובץ ולא של הקורא, ולכן התו משתנה גם ברשימת התווים של PDFium.
   והצורות של הרווחים (מסבב 6ב), שהן החלטה אחרת של הקורא על פער, ולכן משתנים גם הרווחים שבעמוד (Component.visual
   הוא התווים בעמוד עם הרווחים שהקורא קבע) והטקסט נבנה מהם מחדש בסדר הלוגי של החבילה (logical_order.to_logical),
   כמו שקורא עם החלטה אחרת היה מוציא. כל צורה בשתי עוצמות: רכיב אחד בעמוד (one), וכל הרכיבים שהצורה חלה עליהם
   (all), כמו קורא שנכשל בכל הקובץ. נמדד רק על עמודים שאין בהם כשל ודאי לפני ההשחתה (_hard_failure): אחרת
   "נתפס" אינו אומר כלום.
   הצורות של סבב 6ב (BLIND) הן הכשלים שעוד נשארו בקורא, שבהם כל שורה עדיין מוצגת כמו העמוד: רווחים (מילים
   שנדבקו, רווח בתוך מילה), שורות של טבלה שהתאחדו, תא בעמודה הלא נכונה, ושורות של שני גושים זה לצד זה שנשזרו.
   בדיקת התצוגה לא רואה אותם מעצם ההגדרה, ולכן הם מודדים את הנקודה העיוורת של הציון.
2. השארת תוכנה אחת בחוץ (leave_one_out): לכל תוכנה, הספים מחושבים מהעמודים של שאר התוכנות, ונבדקים על העמודים
   שלה. סף שמשתנה מאוד בין התוכנות הוא דגל, לא ערך.
3. רגישות (stable_range): לכל סף, הטווח שבו ההחלטה והסיבות של כל עמוד בסט לא משתנות.

איך נקבע כל סף (ההסבר המלא והמספרים ליד הקבועים ב-hebrew_pdf/score.py):
- MIN_PLAUSIBLE: הסימנים של הסבירות הם גיבוי לבדיקת התצוגה, ובנויים לתפוס היפוך של אותיות עבריות (אות סופית
  במקום לא נכון). הדרישה (required_plausible): שהם לבדם יתפסו 95% מהעמודים שכל השורות בהם הפוכות, בשתי
  הצורות שהם בנויים להן (SIGNAL_TARGETS): האחוזון ה-95 של הציון של העמודים המושחתים (ההתייעצות על מדידה, סעיף
  1.6). הערך: האמצע של הטווח היציב שמכיל את הדרישה, כשהאמצע הזה מעליה; אחרת של הטווח היציב הראשון שכולו מעליה
  (chosen_range).
- MAX_EFFORT: השחתה של הפלט לא משנה את מאמץ התיקון (הוא נמדד מול הקובץ), ולכן אין לו שגיאות מכוונות. הכלל
  (effort_envelope): המאמץ הגבוה ביותר בעמוד שהפלט שלו ידוע כנכון. עד שם יש ראיה שהתיקונים של הקורא עובדים, ומעבר
  לזה אין. הערך: האמצע של הטווח היציב שמכיל אותו.

פרטיות: הכיול נשען על הטקסט של העמודים, אבל מה שיוצא ממנו הוא מספרים בלבד.
"""

import dataclasses
import math
import random
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from hebrew_pdf import score as score_mod
from hebrew_pdf.lines import Component, PageText, RowSource, join_lines
from hebrew_pdf.logical_order import to_logical

# ---------- צורות ההשחתה ----------

_LTR_RUN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.,:/_+\-]*[A-Za-z0-9])?")
_CONTROL = "\x1d"  # תו בקרה, כמו האותיות של GPS בפלאייר (U+001D עד U+001F)


def _reverse_line(text: str, rng: random.Random) -> str:
    """כל השורה הפוכה תו-תו, כמו "תוריכממ תוסנכה" במקום "הכנסות ממכירות"."""
    return text[::-1]


def _reverse_ltr(text: str, rng: random.Random) -> str:
    """כל רצף של אנגלית או מספר הפוך ("noriB rimA", "5202"), והעברית במקומה."""
    return _LTR_RUN.sub(lambda m: m.group(0)[::-1], text)


def _reverse_letters(text: str, rng: random.Random) -> str:
    """האותיות של כל מילה עברית הפוכות, וסדר המילים נשמר."""
    return score_mod._WORD.sub(lambda m: m.group(0)[::-1], text)


def _reverse_words(text: str, rng: random.Random) -> str:
    """סדר המילים הפוך והאותיות נכונות, כמו poppler ("100% באותיות, אבל סדר המילים בשורה הפוך")."""
    return " ".join(reversed(text.split(" ")))


def _punct_to_start(text: str, rng: random.Random) -> str:
    """סימן הפיסוק שבסוף השורה עובר לתחילתה (".זה מנטור שזוכר")."""
    stripped = text.rstrip(" ")
    if len(stripped) > 1 and stripped[-1] in ".,:;!?":
        return stripped[-1] + stripped[:-1]
    return text


def _drop_char(text: str, rng: random.Random) -> str:
    """תו אחד (לא רווח) נשמט."""
    positions = [k for k, char in enumerate(text) if char != " "]
    if not positions:
        return text
    k = rng.choice(positions)
    return text[:k] + text[k + 1:]


def _control_char(text: str, rng: random.Random) -> str:
    """אות אחת הופכת לתו בקרה."""
    positions = [k for k, char in enumerate(text) if char.isalpha()]
    if not positions:
        return text
    k = rng.choice(positions)
    return text[:k] + _CONTROL + text[k + 1:]


def _drop_space(visual: str, rng: random.Random) -> str:
    """רווח אחד בין שתי מילים יורד: הקורא החליט שהפער אינו רווח, ושתי המילים נדבקו ("בינייםלא" בדוח הכספי).
    מקבל את התווים כמו שהם בעמוד (Component.visual)."""
    positions = [k for k in range(1, len(visual) - 1)
                 if visual[k] == " " and visual[k - 1] != " " and visual[k + 1] != " "]
    if not positions:
        return visual
    k = rng.choice(positions)
    return visual[:k] + visual[k + 1:]


def _split_word(visual: str, rng: random.Random) -> str:
    """רווח נכנס בין שתי אותיות של מילה: הקורא החליט שהפער בתוך המילה הוא רווח ("מפעיל וי ות" ב-Aspose)."""
    positions = [k for k in range(1, len(visual)) if visual[k - 1].isalpha() and visual[k].isalpha()]
    if not positions:
        return visual
    k = rng.choice(positions)
    return visual[:k] + " " + visual[k:]


@dataclass(frozen=True)
class Form:
    key: str
    name: str  # השם בעברית, לדוח
    # מה הצורה משנה: text: הטקסט של רכיב (change על הטקסט); spacing: הרווחים שבעמוד (change על Component.visual),
    # והטקסט נבנה מהם מחדש; glue: כל הרכיבים של שורה לרכיב אחד; rows: שתי שורות טבלה סמוכות לשורה אחת; cell: תא
    # לעמודה שכנה; interleave: השורות של שני גושים, לסירוגין
    kind: str
    change: Callable[[str, random.Random], str] | None = None
    in_file: bool = False  # כשל של הקובץ: התו משתנה גם ברשימת התווים של PDFium


FORMS = (
    Form("reverse_line", "היפוך שורה שלמה", "text", _reverse_line),
    Form("reverse_ltr", "היפוך רצפי אנגלית ומספרים", "text", _reverse_ltr),
    Form("reverse_letters", "היפוך אותיות בתוך מילה", "text", _reverse_letters),
    Form("reverse_words", "היפוך סדר המילים", "text", _reverse_words),
    Form("punct_to_start", "הזזת פיסוק לתחילת השורה", "text", _punct_to_start),
    Form("glue", "הדבקת שתי עמודות", "glue"),
    Form("drop", "השמטת תווים", "text", _drop_char),
    Form("control", "תווי בקרה במקום אותיות", "text", _control_char, in_file=True),
    Form("drop_space", "רווח בין מילים שירד", "spacing", _drop_space),
    Form("split_word", "רווח בתוך מילה", "spacing", _split_word),
    Form("merge_rows", "איחוד שתי שורות טבלה סמוכות", "rows"),
    Form("shift_cell", "תא בעמודה השכנה", "cell"),
    Form("interleave", "שזירת שורות משני גושים זה לצד זה", "interleave"),
)
# הצורות של סבב 6ב: כל שורה עדיין מוצגת כמו העמוד, והן מודדות את הנקודה העיוורת של בדיקת התצוגה
BLIND = ("drop_space", "split_word", "merge_rows", "shift_cell", "interleave")
INTENSITIES = (("one", "רכיב אחד"), ("all", "כל הרכיבים"))
# הצורות שהסימנים של הסבירות בנויים להן: היפוך של אותיות עבריות, שמזיז אותיות סופיות. לפיהן נקבעת הדרישה
# ל-MIN_PLAUSIBLE. שאר הצורות נמדדות ומוצגות, אבל הסימנים לא נועדו להן (בדיקת התצוגה והשלמות כן)
SIGNAL_TARGETS = ("reverse_line", "reverse_letters")
CATCH_SHARE = 0.95  # הסימנים לבדם תופסים לפחות כך מהעמודים המושחתים (ההתייעצות על מדידה, סעיף 1.6)


def _rebuild(page: PageText, new: dict[tuple[int, int], str], glued: set[int],
             visuals: dict[tuple[int, int], str] | None = None) -> PageText:
    """העמוד עם טקסט אחר לרכיבים new ((שורה, רכיב): טקסט), ושורות glued שכל הרכיבים שלהן נדבקו לרכיב אחד.
    visuals: לרכיבים שהרווחים שלהם בעמוד השתנו (צורות spacing), מה שבעמוד החדש.

    מה שבעמוד (visual, חוץ מ-visuals; הגיאומטריה, רשימת התווים) לא משתנה. התאים של שורה בטבלה, ושל שורת טבלה
    שאוחדה (PageText.rows), מורכבים מהטקסטים של הרכיבים, ולכן הטקסט הישן מוחלף בהם בחדש."""
    visuals = visuals or {}
    lines = []
    for i, line in enumerate(page.lines):
        if i in glued:
            visual_order = line.parts[::-1] if page.rtl_document else line.parts
            text = " ".join(part.text for part in visual_order)
            lines.append(dataclasses.replace(line, text=text, components=(Component(text, line.visual, line.rtl),)))
            continue
        components = tuple(dataclasses.replace(part, text=new.get((i, j), part.text),
                                               visual=visuals.get((i, j), part.visual))
                           for j, part in enumerate(line.parts))
        columns = line.columns
        if columns is not None:
            columns = _swapped(columns, [(part.text, new[(i, j)]) for j, part in enumerate(line.parts)
                                         if (i, j) in new])
        lines.append(dataclasses.replace(line, text=" ".join(c.text for c in components), components=components,
                                         columns=columns))
    rows = []
    for cells, source in zip(page.rows, page.sources):
        if source.table is None:
            rows.append(lines[source.lines[0]].cells)
        else:
            rows.append(_swapped(cells, [(part.text, new[(i, j)]) for i in source.lines
                                         for j, part in enumerate(page.lines[i].parts) if (i, j) in new]))
    return dataclasses.replace(page, lines=lines, table_rows=rows)


def _swapped(cells: Sequence[str], changes: list[tuple[str, str]]) -> tuple[str, ...]:
    """בכל החלפה, המופע הראשון של הטקסט הישן בתא הראשון שמכיל אותו. רכיב הוא חלק מהתא שלו (התאים מחוברים
    מהרכיבים), כך שהוא תמיד נמצא; כשאותו טקסט חוזר בשני תאים בשורה, ייתכן שהוחלף בתא הלא נכון, וזה לא משנה
    את הספירות של הציון (אותם תווים ואותן מילים)."""
    out = list(cells)
    for old, new in changes:
        for k, cell in enumerate(out):
            if old in cell:
                out[k] = cell.replace(old, new, 1)
                break
    return tuple(out)


def _table_rows(page: PageText) -> list[int]:
    """האינדקסים ב-PageText.rows של השורות שבטבלה."""
    return [k for k, source in enumerate(page.sources) if source.table is not None]


def _merge_rows(page: PageText, intensity: str, rng: random.Random) -> PageText | None:
    """שתי שורות טבלה סמוכות, באותה טבלה ועם אותן עמודות, לשורה אחת: בכל עמודה הטקסטים מתחברים כמו אצל הקורא
    (lines.join_lines). כך הקורא מחבר שורה שהיא שורה חדשה כאילו היא המשך ("146,137 449,413")."""
    rows, sources = list(page.rows), list(page.sources)
    pairs = [k for k in _table_rows(page) if k + 1 < len(rows) and sources[k + 1].table == sources[k].table
             and sources[k].table is not None and len(rows[k]) == len(rows[k + 1])]
    if not pairs:
        return None
    if intensity == "all":
        chosen, last = [], -2
        for k in pairs:
            if k > last + 1:
                chosen.append(k)
                last = k
    else:
        chosen = [rng.choice(pairs)]
    for k in sorted(chosen, reverse=True):
        merged = tuple(join_lines([cell for cell in (a, b) if cell]) for a, b in zip(rows[k], rows[k + 1]))
        rows[k:k + 2] = [merged]
        sources[k:k + 2] = [RowSource(sources[k].lines + sources[k + 1].lines, sources[k].table)]
    return dataclasses.replace(page, table_rows=rows, row_sources=sources)


def _shift_cell(page: PageText, intensity: str, rng: random.Random) -> PageText | None:
    """תא של שורת טבלה עובר לעמודה השכנה, ומתחבר לטקסט שכבר בה לפי סדר הקריאה, כמו רכיב שהקורא שייך לעמודה
    הלא נכונה (lines._line). העמודה שממנה הוא יצא נשארת ריקה."""
    rows = list(page.rows)
    candidates = {k: [j for j, cell in enumerate(rows[k]) if cell.strip(" ")] for k in _table_rows(page)
                  if len(rows[k]) >= 2}
    candidates = {k: cells for k, cells in candidates.items() if cells}
    if not candidates:
        return None
    chosen = sorted(candidates) if intensity == "all" else [rng.choice(sorted(candidates))]
    for k in chosen:
        cells = list(rows[k])
        j = rng.choice(candidates[k])
        neighbours = [n for n in (j - 1, j + 1) if 0 <= n < len(cells)]
        n = rng.choice(neighbours)
        moved = cells[j]
        cells[j] = ""
        # בסדר הקריאה: מה שבא מעמודה קודמת נכנס לפני הטקסט של העמודה, ומה שבא מעמודה מאוחרת אחריו
        cells[n] = join_lines([text for text in ((moved, cells[n]) if j < n else (cells[n], moved)) if text])
        rows[k] = tuple(cells)
    return dataclasses.replace(page, table_rows=rows)


def _interleave(page: PageText, dropped: frozenset, intensity: str, rng: random.Random) -> PageText | None:
    """השורות של שני גושים רצופים נשזרות לסירוגין (א1, ב1, א2, ב2), כמו קורא שקורא שורה-שורה על פני שתי עמודות
    שעומדות זו לצד זו (הפלאייר). כל שורה נשארת כמו שהיא ומוצגת כמו העמוד; רק הסדר שבו הן נקראות משתנה. חל על
    רצפים של לפחות ארבע שורות מחוץ לטבלה שלא ירדו מה-Markdown: one: חלון אחד של ארבע (א1 א2 ב1 ב2), all: כל רצף,
    החצי הראשון שלו מול השני."""
    table_lines = {i for source in page.sources if source.table is not None for i in source.lines}
    eligible = [i for i, line in enumerate(page.lines) if i not in table_lines and line.visual.strip(" ")
                and not any((i, j) in dropped for j in range(len(line.parts)))]
    runs: list[list[int]] = []
    for i in eligible:
        if runs and runs[-1][-1] == i - 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    runs = [run for run in runs if len(run) >= 4]
    if not runs:
        return None
    if intensity == "all":
        windows = runs
    else:
        run = rng.choice(runs)
        start = rng.randrange(len(run) - 3)
        windows = [run[start:start + 4]]
    order = list(range(len(page.lines)))
    for window in windows:
        half = len(window) // 2
        first, second = window[:half], window[half:2 * half]
        woven = [i for pair in zip(first, second) for i in pair]
        for position, index in zip(window, woven):
            order[position] = index
    lines = [page.lines[i] for i in order]
    rows = [lines[source.lines[0]].cells if source.table is None else cells
            for cells, source in zip(page.rows, page.sources)]
    return dataclasses.replace(page, lines=lines, table_rows=rows)


def corrupt(page: PageText, dropped: frozenset, form: Form, intensity: str, rng: random.Random) -> PageText | None:
    """העמוד אחרי ההשחתה, או None כשהצורה לא חלה על אף רכיב בעמוד (אין שורה שמסתיימת בפיסוק, וכו').
    רק מה שמגיע ל-Markdown מושחת (לא מה שב-dropped). הדבקה חלה על שורה מחוץ לטבלה עם שני רכיבים לפחות."""
    if form.kind == "glue":
        table_lines = {i for source in page.sources if source.table is not None for i in source.lines}
        eligible = [i for i, line in enumerate(page.lines) if len(line.parts) >= 2 and i not in table_lines
                    and not any((i, j) in dropped for j in range(len(line.parts)))]
        if not eligible:
            return None
        chosen = eligible if intensity == "all" else [rng.choice(eligible)]
        return _rebuild(page, {}, set(chosen))
    if form.kind == "rows":
        return _merge_rows(page, intensity, rng)
    if form.kind == "cell":
        return _shift_cell(page, intensity, rng)
    if form.kind == "interleave":
        return _interleave(page, dropped, intensity, rng)
    probe = random.Random(0)
    field_of = (lambda part: part.visual) if form.kind == "spacing" else (lambda part: part.text)
    eligible = [(i, j) for i, line in enumerate(page.lines) for j, part in enumerate(line.parts)
                if (i, j) not in dropped and form.change(field_of(part), probe) != field_of(part)]
    if not eligible:
        return None
    chosen = eligible if intensity == "all" else [rng.choice(eligible)]
    if form.kind == "spacing":
        visuals = {(i, j): form.change(page.lines[i].parts[j].visual, rng) for i, j in chosen}
        new = {key: "".join(to_logical(list(visual), lambda char: char, page.rtl_document).texts)
               for key, visual in visuals.items()}
        return _rebuild(page, new, set(), visuals)
    new = {(i, j): form.change(page.lines[i].parts[j].text, rng) for i, j in chosen}
    corrupted = _rebuild(page, new, set())
    if form.in_file:
        reference = page.reference or ""
        for (i, j), text in new.items():
            old = page.lines[i].parts[j].text
            lost = (Counter(old) - Counter(text))
            for char in lost.elements():
                reference = reference.replace(char, _CONTROL, 1)
        corrupted = dataclasses.replace(corrupted, reference=reference)
    return corrupted


# ---------- ההחלטה, כפונקציה של הספים ----------

# הכללים שמחליטים, לפי הסדר: עד סבב 6 (TODAY), והראיות החדשות של סבב 6ב (NEW). ועוד ראיה אחת שנמדדת ולא מחליטה
# (EVIDENCE_ONLY): החלטות של הקורא שקרובות לסף שלהן (lines.PageText.near_decisions)
TODAY = ("נפסל", "תצוגה", "סימנים", "שלמות")
NEW = ("קבוצות ספרות", "תאים מספריים")
RULES = TODAY + NEW
EVIDENCE_ONLY = ("קרוב לסף",)


@dataclass(frozen=True)
class Outcome:
    """מה שהציון מוצא בעמוד, בלי הספים: מזה ההחלטה מחושבת לכל סף (decide)."""
    rejected: bool
    display_failures: int = 0
    plausible: float = 1.0  # Signals.score
    complete: bool = True
    effort: float = 0.0  # Effort.score
    words: int = 0  # Signals.words: האם הסימנים מכריעים תלוי בסף (Signals.decides)
    bad_numbers: int = 0  # Plausibility.bad_numbers
    crowded: int = 0  # Plausibility.crowded_cells
    near: int = 0  # PageText.near_decisions: ראיה שנמדדת ולא מחליטה


def outcome(page: PageText, dropped: frozenset) -> Outcome:
    scored = score_mod.score_page(page, dropped)
    if scored.decision == score_mod.REJECTED:
        return Outcome(True, near=page.near_decisions)
    plausibility = scored.plausibility
    return Outcome(False, plausibility.display_failures, plausibility.signals.score, scored.completeness.ok,
                   scored.effort.score, plausibility.signals.words, plausibility.bad_numbers,
                   plausibility.crowded_cells, page.near_decisions)


def decide(out: Outcome, min_plausible: float) -> dict[str, bool]:
    """לכל כלל ב-RULES וב-EVIDENCE_ONLY: האם הוא מסמן את העמוד בסף הזה. "היום": אחד מכללי TODAY; "עם הראיות":
    אחד מכללי RULES, כלומר ההחלטה של הציון. מאמץ התיקון אינו כאן: מסבב 6ב הוא הערה ולא כלל."""
    if out.rejected:
        hits = {name: name == "נפסל" for name in RULES}
    else:
        hits = {"נפסל": False, "תצוגה": out.display_failures > 0,
                "סימנים": score_mod.Signals(out.words).decides(min_plausible) and out.plausible < min_plausible,
                "שלמות": not out.complete, "קבוצות ספרות": out.bad_numbers > 0, "תאים מספריים": out.crowded > 0}
    hits["קרוב לסף"] = out.near > 0
    hits["היום"] = any(hits[name] for name in TODAY)
    hits["עם הראיות"] = any(hits[name] for name in RULES)
    return hits


def _hard_failure(out: Outcome) -> bool:
    """כשל שאינו תלוי באף סף שמכיילים: פסילה, שורה שלא מוצגת כמו העמוד, תו שחסר או נוסף, או אחת הראיות של סבב 6ב
    (מספר או תא מספרי לא תקינים)."""
    return out.rejected or out.display_failures > 0 or not out.complete or out.bad_numbers > 0 or out.crowded > 0


# ---------- הכיול ----------

@dataclass(frozen=True)
class Corrupted:
    producer: str
    form: str
    intensity: str
    outcome: Outcome
    baseline: Outcome  # אותו עמוד לפני ההשחתה


@dataclass(frozen=True)
class Range:
    """טווח של ערכי סף שבו ההחלטות והסיבות בכל הסט זהות: low לא כולל, high כולל (או ההפך, לפי הכלל)."""
    low: float
    high: float

    @property
    def middle(self) -> float:
        return (self.low + self.high) / 2


@dataclass(frozen=True)
class Fold:
    producer: str
    pages: int  # עמודים ידועים כנכונים של התוכנה, בלי כשל ודאי
    required: float | None  # הדרישה ל-MIN_PLAUSIBLE מהעמודים של שאר התוכנות
    caught: tuple[int, int]  # עמודים מושחתים של התוכנה (SIGNAL_TARGETS, all) שהסימנים תפסו בדרישה הזו, מתוך
    flagged: tuple[int, int]  # עמודים נקיים של התוכנה שסומנו בדרישה הזו, מתוך
    envelope: float | None  # המאמץ הגבוה ביותר בעמוד ידוע כנכון של שאר התוכנות
    over: tuple[int, int]  # עמודים של התוכנה (כל העמודים שלא נפסלו) מעל המעטפת הזו, מתוך


@dataclass(frozen=True)
class Calibration:
    known_good: int  # עמודים ידועים כנכונים
    clean: int  # מתוכם, בלי כשל ודאי: עליהם נמדדות ההשחתות
    clean_flagged: Counter  # מהעמודים הנקיים, כמה סומנו בספים של הציון, לפי הכלל (decide)
    known_good_flagged: Counter  # מכל העמודים הידועים כנכונים, כמה סומנו, לפי הכלל
    corrupted: list[Corrupted]
    # None בשלושת השדות שאחרי זה, ובשתי הבחירות: אין ראיה (אין עמוד מושחת בצורות של SIGNAL_TARGETS, או אין עמוד
    # ידוע כנכון שלא נפסל), למשל בסט של קובץ אחד. אז הכיול לא בוחר ערך, והדוח אומר את זה
    required_plausible: float | None  # האחוזון ה-95 של הציון של העמודים המושחתים ב-SIGNAL_TARGETS
    envelope: float | None  # המאמץ הגבוה ביותר בעמוד ידוע כנכון
    plausible_range: Range  # הטווח היציב סביב MIN_PLAUSIBLE
    effort_range: Range  # הטווח היציב סביב MAX_EFFORT
    plausible_choice: Range | None  # chosen_range: MIN_PLAUSIBLE באמצע שלו
    effort_choice: Range | None  # הטווח היציב שמכיל את envelope: MAX_EFFORT באמצע שלו
    folds: list[Fold] = field(default_factory=list)
    count_rules: dict = field(default_factory=dict)  # לכלל של ספירה: כמה עמודים בסט עם 1, 2, 3 ומעלה
    all_flagged: Counter = field(default_factory=Counter)  # מכל העמודים בסט שלא נפסלו, כמה כל כלל מסמן
    pages: int = 0  # העמודים בסט שלא נפסלו


def known_good(truth_pages: dict[str, list[bool]],
               exact_by_page: dict[tuple[str, int], list[bool]]) -> list[tuple[str, int]]:
    """(קובץ, אינדקס עמוד מ-0) של העמודים שהפלט שלהם ידוע כנכון: עמודים של קובץ עם דף תשובות שהפלט שלהם זהה לו
    (truth_pages: לכל קובץ, לכל עמוד, tables.pages_matching_truth), ועמודים שיש בהם לפחות שורה מתויגת ומאושרת
    אחת וכולן זהות (exact_by_page: לכל (קובץ, אינדקס עמוד), האם כל תיוג זהה). עד סבב 6ב נספרו כל העמודים של
    קובץ עם דף תשובות, גם כאלה שיש בהם טקסט שגוי."""
    good = {(name, i) for name, pages in truth_pages.items() for i, same in enumerate(pages) if same}
    good |= {key for key, exact in exact_by_page.items() if exact and all(exact)}
    return sorted(good)


def _percentile(values: Sequence[float], share: float) -> float:
    """הערך שחלק share מהערכים קטנים ממנו או שווים לו (האחוזון, בלי אינטרפולציה)."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(share * len(ordered)) - 1))]


def required_plausible(corrupted: Sequence[Corrupted]) -> float | None:
    """הדרישה ל-MIN_PLAUSIBLE: הגבוה מבין האחוזונים ה-95 של הציון של העמודים המושחתים, בכל צורה ב-SIGNAL_TARGETS
    בעוצמה all. סף מעליו תופס, בסימנים לבדם, לפחות 95% מהעמודים בכל אחת מהצורות. None: אין עמודים כאלה."""
    found = []
    for form in SIGNAL_TARGETS:
        scores = [c.outcome.plausible for c in corrupted if c.form == form and c.intensity == "all"
                  and not c.outcome.rejected]
        if scores:
            found.append(_percentile(scores, CATCH_SHARE))
    return max(found) if found else None


def stable_range(values: Sequence[float], at: float, flagged_below: bool) -> Range:
    """הטווח של ערכי הסף סביב at שבו אף עמוד לא עובר צד. flagged_below: עמוד מסומן כשהציון שלו קטן מהסף
    (סבירות); אחרת כשהוא גדול ממנו (מאמץ). values: הציונים של כל העמודים בסט."""
    distinct = sorted(set(values))
    if flagged_below:  # מסומן אם value < at: יציב עבור at ב-(הגדול שקטן מ-at, הקטן שגדול או שווה ל-at]
        low = max((v for v in distinct if v < at), default=0.0)
        high = min((v for v in distinct if v >= at), default=1.0)
    else:  # מסומן אם value > at: יציב עבור at ב-[הגדול שקטן או שווה ל-at, הקטן שגדול מ-at)
        low = max((v for v in distinct if v <= at), default=0.0)
        high = min((v for v in distinct if v > at), default=1.0)
    return Range(low, high)


def first_range_above(values: Sequence[float], required: float) -> Range:
    """הטווח היציב הראשון (flagged_below) שכולו מעל required: מהציון הראשון בסט שגדול או שווה ל-required."""
    above = sorted(v for v in set(values) if v >= required)
    low = above[0] if above else required
    high = above[1] if len(above) > 1 else 1.0
    return Range(low, high)


def chosen_range(values: Sequence[float], required: float) -> Range:
    """הטווח היציב ש-MIN_PLAUSIBLE נקבע באמצע שלו: הטווח שהדרישה נמצאת בו, כשהאמצע שלו מעל הדרישה; אחרת הטווח
    היציב הראשון שכולו מעליה (first_range_above). כך הערך תמיד באמצע של טווח שלם, רחוק משני הערכים שבהם ההחלטות
    בסט משתנות, ותמיד מעל הדרישה.

    עד סבב 6ב הכלל היה רק first_range_above. מסבב 6ב עמוד קצר לא מסומן בגלל האורך, ולכן עמוד קצר בלי סימן כבר
    לא קובע ערך שבו ההחלטות משתנות (_critical_plausible), והטווח שמכיל את הסף נמתח למטה עד מתחת לדרישה. הכלל
    הישן היה קופץ אז לטווח הבא, שמשנה החלטות בסט (מעל 0.790 שני עמודים ידועים כנכונים, עמוד 9 של מסמך האפיון
    בשתי התוכנות, היו מסומנים), אף שהטווח הנוכחי כבר מכיל ערכים מעל הדרישה. על הנתונים של סבב 6 שני הכללים
    בוחרים אותו טווח."""
    containing = stable_range(values, required, True)
    return containing if containing.middle > required else first_range_above(values, required)


def _critical_plausible(outs: Sequence[Outcome]) -> list[float]:
    """ערכי הסף שבהם ההחלטה של עמוד לפי הסימנים מתהפכת. עמוד מסומן בסף t כשהוא לא קצר (Signals.decides: הציון
    שלו בלי אף סימן, n / (n + z²), מגיע ל-t) והציון שלו מתחת ל-t. לכן לעמוד עם סימן שני ערכים: הציון שלו, והציון
    שלו בלי סימנים. עמוד בלי סימן לא מסומן באף סף (שני הערכים זהים), ואין לו ערך. ההערה "עמוד קצר" זזה גם היא
    עם הסף, אבל היא לא חלק מההחלטה."""
    values = []
    for out in outs:
        bare = score_mod.wilson_lower(out.words, out.words)
        if out.plausible < bare:
            values += [out.plausible, bare]
    return values


def calibrate(read_files: dict[str, list[PageText]], dropped_by_file: dict[str, frozenset],
              good: Sequence[tuple[str, int]], producer_of: Callable[[str], str],
              min_plausible: float = score_mod.MIN_PLAUSIBLE, max_effort: float = score_mod.MAX_EFFORT) -> Calibration:
    """dropped_by_file: markdown.Markdown.dropped של כל קובץ (עמוד מ-1, שורה, רכיב)."""
    def dropped_on(name: str, index: int) -> frozenset:
        return frozenset((line, part) for page, line, part in dropped_by_file.get(name, ()) if page == index + 1)

    outcomes = {(name, i): outcome(page, dropped_on(name, i))
                for name, pages in read_files.items() for i, page in enumerate(pages)}
    clean = [key for key in good if not _hard_failure(outcomes[key])]
    corrupted: list[Corrupted] = []
    for name, i in clean:
        page, dropped = read_files[name][i], dropped_on(name, i)
        baseline = outcomes[(name, i)]
        for form in FORMS:
            for intensity, _ in INTENSITIES:
                rng = random.Random(f"{name}|{i}|{form.key}|{intensity}")
                changed = corrupt(page, dropped, form, intensity, rng)
                if changed is not None:
                    corrupted.append(Corrupted(producer_of(name), form.key, intensity, outcome(changed, dropped),
                                               baseline))

    required = required_plausible(corrupted)
    envelope = max((outcomes[key].effort for key in good if not outcomes[key].rejected), default=None)
    live = [o for o in outcomes.values() if not o.rejected]
    plausible_values = _critical_plausible(live)
    effort_values = [o.effort for o in live]

    def rule_counts(outs) -> Counter:
        counts: Counter = Counter()
        for out in outs:
            counts.update(name for name, hit in decide(out, min_plausible).items() if hit)
        return counts

    folds = []
    for producer in sorted({producer_of(name) for name in read_files}):
        own_clean = [key for key in clean if producer_of(key[0]) == producer]
        others = [c for c in corrupted if c.producer != producer]
        fold_required = required_plausible(others)
        own_corrupted = [c for c in corrupted if c.producer == producer and c.form in SIGNAL_TARGETS
                         and c.intensity == "all" and not c.outcome.rejected]
        caught = sum(c.outcome.plausible < fold_required for c in own_corrupted) if fold_required is not None else 0
        flagged = sum(outcomes[key].plausible < fold_required for key in own_clean) if fold_required is not None else 0
        other_good = [outcomes[key].effort for key in good
                      if producer_of(key[0]) != producer and not outcomes[key].rejected]
        fold_envelope = max(other_good) if other_good else None
        own_pages = [key for key in outcomes if producer_of(key[0]) == producer and not outcomes[key].rejected]
        over = sum(outcomes[key].effort > fold_envelope for key in own_pages) if fold_envelope is not None else 0
        folds.append(Fold(producer, len(own_clean), fold_required, (caught, len(own_corrupted)),
                          (flagged, len(own_clean)), fold_envelope, (over, len(own_pages))))

    pages = list(read_files)
    count_rules = {}
    for label, count_of in (("תווים לא ממופים", lambda p: sum(score_mod.unmapped_char(c) for c in score_mod._all_text(p))
                             + p.marked_unmapped),
                            ("תווים בטקסט מסובב", lambda p: p.rotated_chars)):
        counts = [count_of(page) for name in pages for page in read_files[name]]
        count_rules[label] = Counter(min(c, 3) for c in counts if c)
    for label, count_of in (("שורות שלא מוצגות כמו העמוד", lambda o: o.display_failures),
                            ("מספרים עם קבוצות ספרות לא תקינות", lambda o: o.bad_numbers),
                            ("תאים עם כמה מספרים בעמודה של מספרים", lambda o: o.crowded)):
        count_rules[label] = Counter(min(count_of(o), 3) for o in live if count_of(o))
    missing = Counter()
    for name in pages:
        for i, page in enumerate(read_files[name]):
            if not outcomes[(name, i)].rejected:
                lost = sum(score_mod._completeness(page).missing.values()) + sum(score_mod._completeness(page).extra.values())
                if lost:
                    missing[min(lost, 3)] += 1
    count_rules["תווים שחסרים או נוספו"] = missing

    return Calibration(
        len(good), len(clean), rule_counts(outcomes[key] for key in clean), rule_counts(outcomes[key] for key in good),
        corrupted, required, envelope,
        stable_range(plausible_values, min_plausible, True), stable_range(effort_values, max_effort, False),
        chosen_range(plausible_values, required) if required is not None else None,
        stable_range(effort_values, envelope, False) if envelope is not None else None, folds, count_rules,
        rule_counts(live), len(live))


def catch_table(calibration: Calibration, min_plausible: float = score_mod.MIN_PLAUSIBLE
                ) -> list[tuple[str, str, int, Counter]]:
    """לכל צורה ועוצמה: (צורה, עוצמה, מספר העמודים המושחתים, כמה נתפסו לפי כל כלל של decide, וב"היום" וב"עם
    הראיות"). רק עמודים שיצאו תקין לפני ההשחתה בסף הזה, עם כל הכללים: עמוד שכבר סומן "נתפס" בלי קשר להשחתה."""
    rows = []
    for form in FORMS:
        for intensity, _ in INTENSITIES:
            found = [c for c in calibration.corrupted if c.form == form.key and c.intensity == intensity
                     and not decide(c.baseline, min_plausible)["עם הראיות"]]
            counts: Counter = Counter()
            for c in found:
                counts.update(name for name, hit in decide(c.outcome, min_plausible).items() if hit)
            rows.append((form.key, intensity, len(found), counts))
    return rows


def form_name(key: str) -> str:
    return next(form.name for form in FORMS if form.key == key)


def intensity_name(key: str) -> str:
    return dict(INTENSITIES)[key]
