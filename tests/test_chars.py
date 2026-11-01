"""קריאת האותיות: כשל של FPDFText_GetCharOrigin לא עובר בשקט, והשיקוף ש-PDFium עושה למירכאות מתבטל.

הכשל מדומה לפי החוזה שב-PDFium (public/fpdf_text.h): הפונקציה מחזירה false ולא
נוגעת ב-x וב-y. בלי בדיקה של ערך ההחזרה האות מקבלת בשקט את המיקום של האות הקודמת.
בסט הבדיקה עצמו אין אף כשל (נמדד: 0 מתוך 159,741 אותיות), ולכן הכשל מדומה.
"""

import collections
import unittest
from pathlib import Path
from unittest import mock

import pypdfium2 as pdfium

from hebrew_pdf import chars as chars_mod
from hebrew_pdf.lines import read_document

PDF = Path(__file__).resolve().parent.parent / "testset" / "pdfs" / "optimization_chrome.pdf"
REAL_GET_CHAR_ORIGIN = chars_mod.pdfium_raw.FPDFText_GetCharOrigin


def first_hebrew_index(page) -> int:
    textpage = page.get_textpage()
    for i in range(textpage.count_chars()):
        if "א" <= textpage.get_text_range(i, 1) <= "ת":
            return i
    raise AssertionError("אין אות עברית בעמוד")


def failing_origin(bad_index: int):
    def fake(textpage, index, x, y):
        if index == bad_index:
            return 0  # כמו PDFium: false, ו-x ו-y לא משתנים
        return REAL_GET_CHAR_ORIGIN(textpage, index, x, y)
    return fake


def non_finite_origin(bad_index: int):
    def fake(textpage, index, x, y):
        ok = REAL_GET_CHAR_ORIGIN(textpage, index, x, y)
        if index == bad_index:
            y.value = float("nan")
        return ok
    return fake


class CharOriginFailureTest(unittest.TestCase):
    def setUp(self):
        self.pdf = pdfium.PdfDocument(str(PDF))
        self.page = self.pdf[0]
        self.bad = first_hebrew_index(self.page)
        self.baseline = chars_mod.page_chars(self.page)

    def tearDown(self):
        self.page.close()
        self.pdf.close()

    def assert_one_char_skipped(self, result):
        self.assertEqual(result.skipped, 1)
        missing = collections.Counter(self.baseline.chars) - collections.Counter(result.chars)
        extra = collections.Counter(result.chars) - collections.Counter(self.baseline.chars)
        self.assertEqual(sum(missing.values()), 1)
        # אף אות לא קיבלה מיקום שאין לה באמת (למשל המיקום של האות הקודמת)
        self.assertEqual(extra, collections.Counter())

    def test_baseline_has_no_skipped_chars(self):
        self.assertEqual(self.baseline.skipped, 0)
        self.assertGreater(len(self.baseline.chars), 100)

    def test_failed_origin_is_skipped_and_counted(self):
        with mock.patch.object(chars_mod.pdfium_raw, "FPDFText_GetCharOrigin", failing_origin(self.bad)):
            self.assert_one_char_skipped(chars_mod.page_chars(self.page))

    def test_non_finite_origin_is_skipped_and_counted(self):
        with mock.patch.object(chars_mod.pdfium_raw, "FPDFText_GetCharOrigin", non_finite_origin(self.bad)):
            self.assert_one_char_skipped(chars_mod.page_chars(self.page))

    def test_count_reaches_the_page_result(self):
        with mock.patch.object(chars_mod.pdfium_raw, "FPDFText_GetCharOrigin", failing_origin(self.bad)):
            self.assertEqual(read_document(self.pdf)[0].skipped_chars, 1)



class PdfiumMirroringTest(unittest.TestCase):
    """המירכאות “ ” ‘ ’: PDFium משקף אותן ברצף שהוא קורא מימין לשמאל, אף ש-Unicode לא מגדיר אותן כמשתקפות
    (hebrew_pdf/chars.py, _mirrored_in_lines). התנאי מועתק מ-CloseTempLine בגרסה שבתוך pypdfium2."""

    @staticmethod
    def mirrored(text: str, r2l: bool = False) -> str:
        """הטקסט, עם ^ במקום כל תו ש-PDFium שיקף. "|" הוא שבירת שורה ש-PDFium הוסיף."""
        indices = chars_mod._mirrored_in_lines([(c, c == "|") for c in text], r2l)
        return "".join("^" if i in indices else c for i, c in enumerate(text))

    def test_a_neutral_after_hebrew_is_mirrored(self):
        self.assertEqual(self.mirrored("“שלום”"), "“^^^^^")

    def test_the_first_neutral_of_a_line_is_not(self):
        # בגרסה שבתוך pypdfium2 הכיוון מתחיל משמאל לימין (auto_order=false); בגרסה קודמת של PDFium הוא
        # נקבע לפי מספר הרצפים, וזה בדיוק מה שמכריע ב-5 מתוך 217 המירכאות בסט
        self.assertEqual(self.mirrored("“שלום"), "“^^^^")

    def test_latin_resets_and_weak_does_not(self):
        self.assertEqual(self.mirrored("א“ab”1“"), "^^ab”1“")
        self.assertEqual(self.mirrored("א1“"), "^1^")

    def test_a_line_break_starts_again(self):
        self.assertEqual(self.mirrored("א“|“"), "^^|“")

    def test_an_r2l_document_starts_right_to_left(self):
        self.assertEqual(self.mirrored("“ab", r2l=True), "^ab")


class QuotesInTheTableFileTest(unittest.TestCase):
    """על קובץ הטבלאות: התאים עם מירכאות יוצאים כמו בדף התשובות. נבדק גם מול pdfminer, שקורא את מפת
    התווים של הקובץ בלי עיבוד: 217 מתוך 217 המירכאות בסט זהות לו אחרי ביטול השיקוף (סבב 5ב)."""

    def test_default_cell_and_heading(self):
        pdf = Path(__file__).resolve().parent.parent / "testset" / "pdfs" / "env-vars_weasyprint.pdf"
        with pdfium.PdfDocument(str(pdf)) as document:
            pages = read_document(document)
        rows = {row[0]: row for page in pages for row in page.rows if row}
        self.assertEqual(rows["MONGODB_APPNAME"][3], "”“ (ריק)")  # כמו במקור ובדף התשובות
        self.assertIn("תפעול, אינטגרציות ופיצ’רים", [line.text for page in pages for line in page.lines])


if __name__ == "__main__":
    unittest.main()
