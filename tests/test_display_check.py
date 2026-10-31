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
from hebrew_pdf.lines import Line, group_rows, read_page
from hebrew_pdf.logical_order import bidi_class, display_levels, display_order, is_rtl
from prototype import hebrew_pdf_prototype as prototype

# (קובץ, עמוד): מספר השורות שלא עוברות את בדיקת התצוגה, והסיבה
KNOWN_FAILURES = {
    # "וב-Database (Supabase):": בעמוד שני הסוגריים מצוירים באותה צורה, "(", והסוגר
    # הסוגר מוצג בקצה השמאלי, מחוץ לרצף האנגלי. כך מציג מי שלא מיישם את כלל N0 (זוגות
    # סוגריים, בתקן מאז Unicode 6.3); לפי התקן אין טקסט לוגי שמוצג כך. הקורא מוציא
    # את הטקסט הנכון, והבדיקה מסמנת עמוד שצויר לא לפי התקן.
    ("doc-6p_gdocs.pdf", 4): 1,
    # "מה זה MentorOS?" ו-"2" רחוק בקצה השמאלי: שני רכיבים נפרדים באותה שורה. אין
    # טקסט לוגי אחד שמוצג כך; צריך הפרדה בין רכיבים (הסבב של גבולות התאים).
    ("mentoros-overview_weasyprint.pdf", 2): 1,
}


def forward_display(text: str) -> str:
    """התצוגה לפי המימוש של הקורא, משמאל לימין."""
    return "".join(text[i] for i in display_order(display_levels(list(text))))


class DisplayCheckUnitTest(unittest.TestCase):
    def test_logical_text_passes(self):
        self.assertTrue(displays_like_page(Line("שלום Meta, Google עולם", "םלוע Meta, Google םולש")))

    def test_reversed_english_order_fails(self):
        self.assertFalse(displays_like_page(Line("שלום Google ,Meta עולם", "םלוע Meta, Google םולש")))

    def test_spaces_are_collapsed_but_their_position_counts(self):
        self.assertTrue(displays_like_page(Line("ומה  איתך", "ךתיא  המו")))
        self.assertFalse(displays_like_page(Line("ומהא יתך", "ךתיא המו")))


class WholeSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = []  # (קובץ, עמוד, Line של הקורא, טקסט של האב-טיפוס)
        for path in sorted(DEFAULT_PDFS.glob("*.pdf")):
            with pdfium.PdfDocument(str(path)) as pdf:
                for number, page in enumerate(pdf, 1):
                    rows = group_rows(page_chars(page).chars)
                    lines = read_page(page).lines
                    for row, line in zip(rows, lines, strict=True):
                        if normalize(line.visual):
                            old = prototype.build_line([tuple(c) for c in row])
                            cls.lines.append((path.name, number, line, old))

    def test_the_whole_set_is_checked(self):
        self.assertGreater(len(self.lines), 3000)  # נמדד: 3541 שורות עם טקסט

    def test_prototype_output_fails_the_check(self):
        failures = sum(not displays_like_page(Line(old, line.visual)) for _, _, line, old in self.lines)
        self.assertGreater(failures, 100)  # נמדד: 172

    def test_failures_are_exactly_the_known_ones(self):
        failures = collections.Counter(
            (name, number) for name, number, line, _ in self.lines if not displays_like_page(line))
        self.assertEqual(dict(failures), KNOWN_FAILURES)

    def test_reader_display_agrees_with_python_bidi(self):
        disagreements = []
        for _, _, line, _ in self.lines:
            for text in (line.text, line.visual):  # גם טקסט שלא הקורא בנה
                text = _paragraph_breaks_as_separators(text)
                if not is_rtl([bidi_class(ch) for ch in text]):
                    continue
                if normalize(forward_display(text)) != normalize(get_display(text, base_dir="R")):
                    disagreements.append(text)
        self.assertEqual(disagreements, [])


if __name__ == "__main__":
    unittest.main()
