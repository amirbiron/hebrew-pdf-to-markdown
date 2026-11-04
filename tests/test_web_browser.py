"""בדיקה אחת בדפדפן אמיתי (Playwright עם Chromium) על המסלול המרכזי של הדף: העלאה, סיכום, רשימת עמודים, מעבר
לעמוד, כיוון מימין לשמאל, העתקה, הורדה, ואפס הפרות CSP.

למה בדפדפן: את ה-CSP, את הכיוון ואת ההורדה רק דפדפן אוכף ומבצע (TESTING-PATTERNS.md, T1(c)). הבדיקה עוברת דרך
הדף כמו משתמש: בוחרת קובץ בשדה, לוחצת על הכפתורים, וקוראת מה שבאמת הגיע ללוח ולקובץ שירד.

הקובץ: ספר התדמית (16 עמודים), כי יש בו עמודים שנפסלו (הכריכה ועמוד 3, תמונות), ולכן גם ההודעה על עמוד שנפסל
במקום שלו בפלט נבדקת. השם שלו בהעלאה כולל תווים שאסורים בשם קובץ ותו כיוון (U+202E), כדי לבדוק את הניקוי של שם
ההורדה. דורש את Chromium של Playwright (python -m playwright install chromium בסביבת פיתוח רגילה).
"""

import json
import unittest

from playwright.sync_api import expect, sync_playwright

from tests.web_server import PDFS, Server

FILE = PDFS / "gps-book_indesign.pdf"
UPLOAD_NAME = "ספר:תדמית/GPS\u202e גרסה.pdf"
EXPECTED_DOWNLOAD = "ספר_תדמית_GPS גרסה.md"

# נרשם בדף לפני כל סקריפט שלו: כל הפרה של CSP (securitypolicyviolation), גם כזו שלא מגיעה לקונסול
RECORD_CSP = """
window.__csp = [];
document.addEventListener("securitypolicyviolation", (event) => {
  window.__csp.push(event.violatedDirective + " " + event.blockedURI);
});
"""


class MainPathTest(unittest.TestCase):
    def test_main_path(self):
        with Server() as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            origin = f"http://127.0.0.1:{server.port}"
            context = browser.new_context(accept_downloads=True)
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            page = context.new_page()
            console = []
            page.on("console", lambda message: console.append((message.type, message.text)))
            page.on("pageerror", lambda error: console.append(("pageerror", str(error))))
            page.add_init_script(RECORD_CSP)
            page.goto(origin + "/")

            # הכיוון: כל הדף, ואזור הפלט בכיוון קבוע ולא לפי פסקה
            self.assertEqual(page.get_attribute("html", "dir"), "rtl")
            style = page.eval_on_selector("#output", "el => [getComputedStyle(el).direction, getComputedStyle(el).unicodeBidi]")
            self.assertEqual(style[0], "rtl")
            self.assertNotEqual(style[1], "plaintext")

            # המגבלות ליד כפתור ההעלאה, לפני כל שגיאה
            self.assertIn("מגה-בייט", page.text_content("#limits"))
            self.assertIn("לא נשמר", page.text_content(".privacy"))

            page.set_input_files("#file", files=[{"name": UPLOAD_NAME, "mimeType": "application/pdf",
                                                  "buffer": FILE.read_bytes()}])
            with page.expect_response("**/api/convert", timeout=120000) as answer:
                page.click("#convert")
            result = json.loads(answer.value.body())
            page.wait_for_selector("#result", state="visible")
            markdown = result["markdown"]
            pages = result["pages"]

            # הסיכום: כמה עמודים בכל החלטה, כמו בתשובה
            counts = page.eval_on_selector_all("#summary .count", "items => items.map(i => i.textContent)")
            for entry in result["legend"]:
                expected = sum(1 for p in pages if p["decision"] == entry["decision"])
                self.assertIn(f"{expected}{entry['text']}", counts)
            self.assertEqual(sum(1 for p in pages if p["decision"] == "rejected"), 2)

            # רשימת העמודים: עמוד לכל עמוד, עם ההחלטה והסיבות
            self.assertEqual(page.locator("#pages > li").count(), len(pages))
            rejected = [p for p in pages if p["decision"] == "rejected"]
            first = page.locator("#pages > li").nth(rejected[0]["number"] - 1)
            self.assertIn(rejected[0]["decision_text"], first.text_content())
            self.assertIn(rejected[0]["reasons"][0]["text"], first.text_content())

            # עמוד שנפסל מסומן במקום שלו בפלט, ולא נבחר בסימון
            banner = page.locator(f"#page-{rejected[1]['number']} .banner")
            self.assertIn("נפסל", banner.text_content())
            self.assertEqual(banner.evaluate("el => getComputedStyle(el).userSelect"), "none")

            # מעבר לעמוד: לחיצה ברשימה מביאה את הסמן של העמוד לתוך אזור הפלט
            target = pages[11]
            page.locator("#pages > li").nth(target["number"] - 1).locator("button.goto").click()
            segment = page.locator(f"#page-{target['number']}")
            self.assertIn("current", segment.get_attribute("class"))
            self.assertIn(f"<!-- page {target['number']} -->", segment.text_content())
            visible = page.evaluate("""(id) => {
                const box = document.getElementById(id).getBoundingClientRect();
                const pane = document.getElementById("output").getBoundingClientRect();
                return box.top >= pane.top - 1 && box.top < pane.bottom;
            }""", f"page-{target['number']}")
            self.assertTrue(visible, "הסמן של העמוד לא הגיע לאזור הנראה של הפלט")

            # מה שמוצג בפלט הוא ה-Markdown, חוץ מההודעות על עמודים שנפסלו
            shown = page.evaluate("""() => Array.from(document.querySelectorAll('#output .line'))
                .map(l => l.textContent).join('')""")
            self.assertEqual(shown, markdown)

            # העתקה: מה שהגיע ללוח הוא ה-Markdown, תו בתו
            page.click("#copy")
            # בלי wait_for_function: הוא מעריך מחרוזת בתוך הדף, וה-CSP של הדף חוסם את זה (unsafe-eval), כמו שצריך
            expect(page.locator("#action-status")).to_have_text("ה-Markdown הועתק.")
            self.assertEqual(page.evaluate("navigator.clipboard.readText()"), markdown)

            # הורדה: שם שנגזר מהשם שהועלה, אחרי ניקוי, והתוכן הוא ה-Markdown ב-UTF-8
            with page.expect_download() as download_info:
                page.click("#download")
            download = download_info.value
            self.assertEqual(download.suggested_filename, EXPECTED_DOWNLOAD)
            with open(download.path(), "rb") as saved:
                self.assertEqual(saved.read(), markdown.encode("utf-8"))

            # בחירת קובץ אחר מורידה את התוצאה הקודמת, כדי שהעתקה והורדה לא יפעלו על קובץ שכבר לא בשדה
            small = (PDFS / "doc-2p_weasyprint.pdf").read_bytes()
            for name, expected in (("CON.txt.pdf", "_CON.txt.md"), ("NUL.tar.gz.pdf", "_NUL.tar.gz.md"),
                                   ("COM\u00b9.pdf", "_COM\u00b9.md"), ("console.pdf", "console.md"), ("COM0.pdf", "COM0.md")):
                with self.subTest(name=name):
                    page.set_input_files("#file", files=[{"name": name, "mimeType": "application/pdf", "buffer": small}])
                    expect(page.locator("#result")).to_be_hidden()
                    page.click("#convert")
                    expect(page.locator("#result")).to_be_visible(timeout=60000)
                    # שם שמור ב-Windows מקבל קידומת גם עם סיומת; COM0 ו-console אינם שמורים (Microsoft, Naming Conventions)
                    expect(page.locator("#download-name")).to_have_text(expected)

            # אפס הפרות CSP ואפס שגיאות בקונסול
            self.assertEqual(page.evaluate("window.__csp"), [])
            self.assertEqual([entry for entry in console if entry[0] in ("error", "pageerror", "warning")], [])
            browser.close()


if __name__ == "__main__":
    unittest.main()
