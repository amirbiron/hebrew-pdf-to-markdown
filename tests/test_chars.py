"""קריאת האותיות: כשל של FPDFText_GetCharOrigin לא עובר בשקט, והשיקוף ש-PDFium עושה למירכאות מתבטל.

הכשל מדומה לפי החוזה שב-PDFium (public/fpdf_text.h): הפונקציה מחזירה false ולא
נוגעת ב-x וב-y. בלי בדיקה של ערך ההחזרה האות מקבלת בשקט את המיקום של האות הקודמת.
בסט הבדיקה עצמו אין אף כשל (נמדד: 0 מתוך 159,741 אותיות), ולכן הכשל מדומה.
"""

import collections
import ctypes
import unittest
from pathlib import Path
from unittest import mock

import pypdfium2 as pdfium

from hebrew_pdf import chars as chars_mod
from hebrew_pdf.lines import geometry_of, read_document

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


class SurrogatePairsTest(unittest.TestCase):
    """אימוג'י ב-doc-6p_gdocs.pdf: PDFium שומר כל אחד כשני אינדקסים, שני החצאים של זוג UTF-16, החצי הנמוך
    לפני הגבוה (chars.characters). הקורא מחבר אותם לתו אחד, עם המיקום של שניהם, ולא מדלג עליהם."""

    DOC = Path(__file__).resolve().parent.parent / "testset" / "pdfs" / "doc-6p_gdocs.pdf"

    def test_the_emoji_reach_the_chars(self):
        with pdfium.PdfDocument(str(self.DOC)) as document:
            page = document[0]
            textpage = page.get_textpage()
            result = chars_mod.page_chars(page)
            emoji = [c for c in result.chars if ord(c.text[0]) > 0xFFFF]
            self.assertEqual([c.text for c in emoji], ["\U0001F680", "\U0001F504", "\U0001F4B0"])
            self.assertFalse([c for c in result.chars if any(0xD800 <= ord(ch) <= 0xDFFF for ch in c.text)])
            self.assertEqual(result.skipped, 0)
            # המיקום: של שני החצאים, שהם אותו CharInfo ב-PDFium (נמדד: אותה נקודת מוצא ואותה תיבה)
            codes = [chars_mod.pdfium_raw.FPDFText_GetUnicode(textpage, i) for i in range(textpage.count_chars())]
            halves = [i for i, code in enumerate(codes) if 0xD800 <= code <= 0xDFFF]
            self.assertEqual(len(halves), 6)
            first = halves[:2]
            boxes = [textpage.get_charbox(i) for i in first]
            self.assertEqual(boxes[0], boxes[1])
            self.assertAlmostEqual(emoji[0].x, (boxes[0][0] + boxes[0][2]) / 2)
            x, y = ctypes.c_double(), ctypes.c_double()
            self.assertTrue(chars_mod.pdfium_raw.FPDFText_GetCharOrigin(textpage, first[0], x, y))
            self.assertAlmostEqual(emoji[0].baseline, y.value)
            self.assertGreater(emoji[0].right, emoji[0].left)

    def test_the_page_is_complete(self):
        with pdfium.PdfDocument(str(self.DOC)) as document:
            pages = read_document(document)
        for number, page in enumerate(pages, 1):
            with self.subTest(page=number):
                output = "".join(part.text for line in page.lines for part in line.parts)
                emoji = collections.Counter(c for c in output if ord(c) > 0xFFFF)
                self.assertEqual(emoji, collections.Counter(c for c in page.reference if ord(c) > 0xFFFF))
        self.assertEqual(sum(1 for page in pages for line in page.lines for part in line.parts
                             for c in part.text if ord(c) > 0xFFFF), 26)

    def test_a_lone_half_is_an_unmapped_char_and_not_dropped(self):
        pdf = pdfium.PdfDocument(str(PDF))
        try:
            page = pdf[0]
            bad = first_hebrew_index(page)
            real = chars_mod.pdfium_raw.FPDFText_GetUnicode

            def lone_half(textpage, index):
                return 0xD83D if index == bad else real(textpage, index)

            baseline = chars_mod.page_chars(page)
            with mock.patch.object(chars_mod.pdfium_raw, "FPDFText_GetUnicode", lone_half):
                result = chars_mod.page_chars(page)
            self.assertEqual(len(result.chars), len(baseline.chars))
            self.assertEqual([c.text for c in result.chars].count("\ufffd"), 1)
            self.assertEqual(result.reference.count("\ufffd"), 1)
        finally:
            pdf.close()

    def test_a_half_is_neutral_for_pdfium(self):
        # בטבלה של PDFium החצאים הם ON (core/fxcrt/fx_ucddata.inc), ולכן הרצף אחרי אימוג'י בשורה עברית עדיין
        # מימין לשמאל, והמירכאות אחריו משתקפות. unicodedata נותן לחצי L, ואז הן לא היו משתקפות
        text = "א\udcb0\ud83d“"
        self.assertEqual(PdfiumMirroringTest.mirrored(text), "^^^^")


class LineSizeTest(unittest.TestCase):
    def test_the_size_is_a_size_of_one_of_the_chars(self):
        # כותרת ב-doc-6p_gdocs.pdf: 25 אותיות ב-13 ו-25 ב-17. החציון הרגיל הוא 15, גודל שאין לאף אות, והוא היה
        # נספר כקבוצת גודל חדשה של כותרות
        glyphs = [chars_mod.Char("א", k, 0.0, k, k + 1, 10.0, size) for k, size in enumerate([13.0] * 25 + [17.0] * 25)]
        self.assertEqual(geometry_of(glyphs).size, 13.0)
        self.assertEqual(chars_mod.size_of(glyphs), 13.0)
        self.assertEqual(chars_mod.size_of([]), 0.0)


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
