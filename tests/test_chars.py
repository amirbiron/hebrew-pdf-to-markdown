"""קריאת האותיות: כשל של FPDFText_GetCharOrigin לא עובר בשקט.

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


if __name__ == "__main__":
    unittest.main()
