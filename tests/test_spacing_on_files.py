"""ריווח לפי הפער בעמוד, על הקבצים האמיתיים (hebrew_pdf/spacing.py).

תווי הרווח שבקובץ לא אמינים: יש רווחים שמצוירים בתוך מילה או על סוגר, יש פערים בין
מילים בלי שום תו רווח, ויש כותרות שבהן תו רווח (ברוחב אפס) בין כל שתי אותיות. כל
המקרים כאן הם שורות מתויגות (המספר בהערה הוא המספר ב-testset/labels.md), ועוד שורות
שבהן אין אף זוג אותיות סמוכות, כמו מספרי העמודים, שבהן "הפער הרגיל בין אותיות" לא
מוגדר.

הבדיקות עוברות דרך הקורא של מערך הבדיקה (harness/reader.py), כמו הדוח.
"""

import unittest

from harness.reader import read_pages
from harness.run import DEFAULT_PDFS
from harness.textdiff import normalize

_cache: dict[str, list[list[str]]] = {}


def page_texts(file_name: str, page: int) -> list[str]:
    if file_name not in _cache:
        _cache[file_name] = [[normalize(line.text) for line in p.lines] for p in read_pages(DEFAULT_PDFS / file_name)]
    return _cache[file_name][page - 1]


class LetterSpacedHeadingTest(unittest.TestCase):
    def test_heading_with_spaced_letters(self):  # שורה 12
        self.assertIn("הצעת מחיר QT-00011", page_texts("price-quote_weasyprint.pdf", 1))

    def test_heading_with_spaced_letters_and_quotes(self):  # שורה 17
        self.assertIn('סה"כ לתשלום', page_texts("price-quote_weasyprint.pdf", 2))


class SpaceNextToBracketTest(unittest.TestCase):
    def test_google_docs(self):  # שורה 1
        self.assertIn("הסבר על טופס איפיון ראשוני לצ׳טבוט (לפני דיאגרמה)",
                      page_texts("chatbot-spec-form_gdocs.pdf", 1))

    def test_google_docs_english_in_brackets(self):  # שורה 5
        self.assertIn("1. חיבור פייסבוק (Meta OAuth): המשתמש נכנס למערכת ומבצע FB Connect. ה-Backend",
                      page_texts("doc-6p_gdocs.pdf", 1))

    def test_chrome(self):  # שורה 35
        self.assertIn("← זה הזמן לבחון ולדייק את הפרומפט (ההנחיה) של ה-AI בפאנל.",
                      page_texts("optimization_chrome.pdf", 1))

    def test_aspose_space_drawn_on_the_bracket(self):  # שורה 37
        self.assertIn('רב בריח (08) תעשיות בע"מ', page_texts("financial-report-q2-2025_aspose.pdf", 35))


class SpaceInsideWordTest(unittest.TestCase):
    def test_illustrator(self):  # שורה 29: ה-? לא ממופה בקובץ (U+001C), ולכן לא זהה לתיוג
        self.assertIn("ומה איתך\x1c", page_texts("marketing-flyer_illustrator.pdf", 1))

    def test_aspose(self):  # שורה 40, בלי גבולות התאים
        self.assertIn("רווח (הפסד) מפעילויות נמשכות (206) (29,396) (2,073) (20,496) (53,464)",
                      page_texts("financial-report-q2-2025_aspose.pdf", 35))


class LineWithoutLettersTest(unittest.TestCase):
    """בשורה בלי שתי אותיות סמוכות כל הפערים הם בין מילים; הם נשארים רווחים."""

    def test_page_number_with_slash(self):
        self.assertIn("2 / 8", page_texts("mentoros-overview_weasyprint.pdf", 2))

    def test_page_number_between_dashes(self):
        self.assertIn("- 4 -", page_texts("financial-report-q2-2025_aspose.pdf", 35))


if __name__ == "__main__":
    unittest.main()
