"""בדיקת התצוגה (harness/display_check.py), על כל השורות בסט ולא רק על המתויגות.

שלושה דברים נבדקים כאן:
1. הבדיקה מסוגלת להיכשל: הפלט של האב-טיפוס נכשל בה בעשרות שורות.
2. השורות שנכשלות עם הקורא הנוכחי הן בדיוק הרשימה הידועה למטה, וכל אחת מהן עם
   הסיבה. שורה חדשה שנכשלת, או שורה שהפסיקה להיכשל, מפילות את הבדיקה: שינוי כזה
   צריך להיראות ולהיות מוסבר, לא לעבור בשקט.
3. לאלגוריתם התצוגה יש שני מימושים: של הקורא (hebrew_pdf/logical_order.py, שבודק
   את עצמו בזמן הבנייה) ו-python-bidi. הם חייבים להסכים על כל שורה בסט.
"""

import collections
import unittest

import pypdfium2 as pdfium
from bidi import get_display

from harness.display_check import _paragraph_breaks_as_separators, displays_like_page
from harness.run import DEFAULT_PDFS
from harness.textdiff import normalize
from hebrew_pdf.chars import page_chars
from hebrew_pdf.lines import Component, Line, group_rows, read_document
from hebrew_pdf.logical_order import display_levels, display_order
from prototype import hebrew_pdf_prototype as prototype

# (קובץ, עמוד): מספר השורות שלא עוברות את בדיקת התצוגה, והסיבה
KNOWN_FAILURES = {
    # "וב-Database (Supabase):": בעמוד שני הסוגריים מצוירים באותה צורה, "(", והסוגר
    # הסוגר מוצג בקצה השמאלי, מחוץ לרצף האנגלי. כך מציג מי שלא מיישם את כלל N0 (זוגות
    # סוגריים, בתקן מאז Unicode 6.3); לפי התקן אין טקסט לוגי שמוצג כך. הקורא מוציא
    # את הטקסט הנכון, והבדיקה מסמנת עמוד שצויר לא לפי התקן.
    ("doc-6p_gdocs.pdf", 4): 1,
    # קובץ הטבלאות: תאים שבמקור יש בהם קטעי קוד, למשל "אחרי עליית Gunicorn (`1`/`0`)", שבעמוד
    # מצויר "(0/1) Gunicorn". WeasyPrint הציגה כל קטע קוד כאילו הוא מבודד משאר הטקסט, ולכן
    # ה-/ לא נחשב מפריד בין שתי ספרות (כלל W4), וסוגריים אחרי קטע קוד לא שייכים לו (N0).
    # נבדק בסבב 5ב, אחרי שהקובץ נבנה מחדש בלי שבירה באמצע מילה, בכל אחת מהשורות: הטקסט הנכון של
    # השורה מהמקור (testset/sources/env-vars.md), עם בידוד (U+2068, U+2069) סביב כל קטע קוד, מוצג
    # ב-python-bidi בדיוק כמו בעמוד (בלי הבחנה בצורת הסוגר: python-bidi לא משקף), ובלי בידוד לא.
    # כך ב-13 מתוך 20 השורות. ב-7 האחרות (מסומנות "לא הוסבר") קטע קוד מתחיל או נגמר בלוכסן, בנקודה
    # או בסוגר ("(`/api/code/run`)"), ואף אחת משתי הקריאות לא מוצגת כמו העמוד; לא נחקר הלאה (סבב 6,
    # "קטעי קוד מבודדים" במסמך האפיון). בקובץ הקודם (63 עמודים) היו 6 שורות כאלה: הטור של התיאור
    # רחב יותר עכשיו, ויותר קטעי קוד נכנסים בשורה אחת עם הסוגריים שסביבם.
    ("env-vars_weasyprint.pdf", 2): 1,  # (`/oauth/consent/` → `oauth/identify`); לא הוסבר
    ("env-vars_weasyprint.pdf", 3): 3,  # Gunicorn (`1`/`0`); ו-(`Org1=ghp_...`) ו-`webapp/app.py` (`python app.py`), לא הוסברו
    ("env-vars_weasyprint.pdf", 4): 1,  # (`/api/code/run`); לא הוסבר
    ("env-vars_weasyprint.pdf", 7): 1,  # (`0.0`–`1.0`)
    ("env-vars_weasyprint.pdf", 11): 2,  # `DEFAULT_CONTEXT_EXCHANGES` (5); (`services/advisor_service.py`)
    ("env-vars_weasyprint.pdf", 13): 1,  # כאשר ערכו `true`/`1` משתמשים
    ("env-vars_weasyprint.pdf", 17): 1,  # (`monitoring/metrics_storage.py`)
    ("env-vars_weasyprint.pdf", 19): 1,  # `mongo` (GridFS)
    ("env-vars_weasyprint.pdf", 20): 2,  # (`high`/`normal`/...); `hostname:pid` (fallback)
    ("env-vars_weasyprint.pdf", 21): 1,  # (`*.onrender.com`); לא הוסבר
    ("env-vars_weasyprint.pdf", 22): 4,  # Content-Length; `us.posthog.com` (WebApp); ו-(`POSTHOG_HOST`) ו-`/admin/mcp`, לא הוסברו
    ("env-vars_weasyprint.pdf", 24): 1,  # (`production`/`development`)
    # מסמך האפיון מ-Chrome: "שהומר ל-PDF (63 עמודים לרוחב, 6" בסוף שורה, והסוגר נסגר בשורה הבאה.
    # Chrome מזווג סוגריים בפסקה כולה, לפני השבירה לשורות (UAX #9, BD16: הזוגות נמצאים ברצף של
    # הפסקה), ולכן "(" מקבל את הכיוון של מה שבתוכו (עברית) ומצויר "63) PDF". הבדיקה מציגה כל שורה
    # כפסקה משלה, ובשורה לבדה אין ל-"(" זוג. הקורא מוציא את הטקסט הנכון; ב-WeasyPrint אותה שורה עוברת
    # ("PDF (63", זיווג בתוך השורה בלבד).
    ("spec_chrome.pdf", 2): 1,
}


def forward_display(text: str) -> str:
    """התצוגה לפי המימוש של הקורא, משמאל לימין."""
    return "".join(text[i] for i in display_order(display_levels(list(text))))


class DisplayCheckUnitTest(unittest.TestCase):
    def test_logical_text_passes(self):
        self.assertTrue(displays_like_page(Line("שלום Meta, Google עולם", "םלוע Meta, Google םולש", rtl=True)))

    def test_reversed_english_order_fails(self):
        self.assertFalse(displays_like_page(Line("שלום Google ,Meta עולם", "םלוע Meta, Google םולש", rtl=True)))

    def test_spaces_are_collapsed_but_their_position_counts(self):
        self.assertTrue(displays_like_page(Line("ומה  איתך", "ךתיא  המו", rtl=True)))
        self.assertFalse(displays_like_page(Line("ומהא יתך", "ךתיא המו", rtl=True)))

    def test_each_component_is_shown_on_its_own(self):
        # שני תאים: כל אחד נכון לבד, אבל כפסקה אחת "FastAPI" ו-"Backend" היו מתחלפים
        cells = (Component("Backend", "Backend", True), Component("FastAPI + Python 3.12", "FastAPI + Python 3.12", True),
                 Component("שרת API", "API תרש", True))
        line = Line("Backend FastAPI + Python 3.12 שרת API", "API תרש FastAPI + Python 3.12 Backend", True,
                    components=cells)
        self.assertTrue(displays_like_page(line))
        self.assertFalse(displays_like_page(Line(line.text, line.visual, True)))

    def test_the_text_is_shown_in_the_direction_the_reader_used(self):
        # שורה בלי עברית: הלוכסן שבסוף הכתובת מוצג בקצה השמאלי רק בפסקה מימין לשמאל
        self.assertTrue(displays_like_page(Line("https://x.com/", "/https://x.com", rtl=True)))
        self.assertFalse(displays_like_page(Line("https://x.com/", "/https://x.com", rtl=False)))
        self.assertTrue(displays_like_page(Line("/https://x.com", "/https://x.com", rtl=False)))


class WholeSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # (קובץ, עמוד, Line של הקורא, השורה של האב-טיפוס). לאב-טיפוס השורה בעמוד היא עם תווי
        # הרווח שבקובץ, כי ממנה הוא בנה את הטקסט; לקורא היא עם הרווחים לפי הפער
        cls.lines = []
        for path in sorted(DEFAULT_PDFS.glob("*.pdf")):
            with pdfium.PdfDocument(str(path)) as pdf:
                pages = read_document(pdf)
                for number, (page, page_text) in enumerate(zip(pdf, pages, strict=True), 1):
                    rows = group_rows(page_chars(page).chars)
                    for row, line in zip(rows, page_text.lines, strict=True):
                        if normalize(line.visual):
                            old_visual = "".join(c.text for c in sorted(row, key=lambda c: c.x))
                            old = Line(prototype.build_line([tuple(c) for c in row]), old_visual,
                                       rtl=bool(prototype.HEBREW.search(old_visual)))
                            cls.lines.append((path.name, number, line, old))

    def test_the_whole_set_is_checked(self):
        # נמדד (סבב 5ב): 5107 שורות עם טקסט: 3541 ב-12 הקבצים האמיתיים, 946 בקובץ הטבלאות, ו-310 בכל
        # אחד משני הקבצים של מסמך האפיון
        self.assertGreater(len(self.lines), 5000)

    def test_prototype_output_fails_the_check(self):
        # כל שורה מוצגת בכיוון שהאב-טיפוס התכוון אליו: מימין לשמאל רק כשיש בה עברית
        failures = sum(not displays_like_page(old) for _, _, _, old in self.lines)
        self.assertGreater(failures, 100)  # נמדד: 173 (גם על הקוד של סוף סבב 2)

    def test_failures_are_exactly_the_known_ones(self):
        failures = collections.Counter(
            (name, number) for name, number, line, _ in self.lines if not displays_like_page(line))
        self.assertEqual(dict(failures), KNOWN_FAILURES)

    def test_reader_display_agrees_with_python_bidi(self):
        disagreements = []
        for _, _, line, _ in self.lines:
            if not line.rtl:  # המימוש של הקורא מציג רק בפסקה מימין לשמאל
                continue
            for text in (line.text, line.visual):  # גם טקסט שלא הקורא בנה
                text = _paragraph_breaks_as_separators(text)
                if normalize(forward_display(text)) != normalize(get_display(text, base_dir="R")):
                    disagreements.append(text)
        self.assertEqual(disagreements, [])


if __name__ == "__main__":
    unittest.main()
