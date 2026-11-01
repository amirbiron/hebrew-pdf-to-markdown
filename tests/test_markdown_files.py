"""ה-Markdown על הקבצים האמיתיים, והמידע שנוסף לקורא בשבילו (סבב 5).

שלושה חלקים:
- המידע שנוסף לקורא: גודל האות (Char.size), הגיאומטריה של שורה, ומאיפה באה כל שורה של
  PageText.rows (RowSource). הוא לא משנה את הטקסט: הדוח של מערך הבדיקה זהה לפניו ואחריו.
- הבדיקות של harness/markdown_check.py על כל הקבצים בסט: שלמות, והתאים בסיבוב מלא.
- הבדיקות האלה מסוגלות להיכשל: אות שנמחקה מה-Markdown, ובנייה בלי הגנה על התווים.
"""

import collections
import unittest
from unittest import mock

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

from harness import markdown_check as mc
from harness.reader import read_pages
from harness.run import DEFAULT_PDFS, DEFAULT_TRUTH
from harness.tables import load_truth, score_tables
from hebrew_pdf import markdown as markdown_mod
from hebrew_pdf.chars import page_chars
from hebrew_pdf.markdown import build_markdown
from tests.test_no_bidi_controls import BIDI

TABLE_FILE = DEFAULT_PDFS / "env-vars_weasyprint.pdf"


class FontSizeTest(unittest.TestCase):
    def test_size_comes_from_the_matrix_when_the_font_size_is_one(self):
        # InDesign: FPDFText_GetFontSize מחזיר 1 לכל האותיות, והגודל כולו במטריצה
        with pdfium.PdfDocument(str(DEFAULT_PDFS / "gps-book_indesign.pdf")) as pdf:
            page = pdf[1]
            textpage = page.get_textpage()
            raw_sizes = {round(pdfium_raw.FPDFText_GetFontSize(textpage, i), 1) for i in range(textpage.count_chars())}
            sizes = collections.Counter(round(c.size, 1) for c in page_chars(page).chars)
        self.assertEqual(raw_sizes, {1.0})
        self.assertEqual(sizes.most_common(1)[0][0], 13.5)

    def test_synthetic_italic_does_not_inflate_the_size(self):
        # Chrome: אות נטויה מלאכותית (c=0.19 במטריצה) באותו גודל כמו אות ישרה
        with pdfium.PdfDocument(str(DEFAULT_PDFS / "optimization_chrome.pdf")) as pdf:
            page = pdf[0]
            textpage = page.get_textpage()
            matrix = pdfium_raw.FS_MATRIX()
            skewed = 0
            for i in range(textpage.count_chars()):
                if pdfium_raw.FPDFText_GetMatrix(textpage, i, matrix) and abs(matrix.c) > 0.1:
                    skewed += 1
            sizes = {round(c.size, 1) for c in page_chars(page).chars}
        self.assertGreater(skewed, 0)
        self.assertNotIn(12.4, sizes)
        self.assertIn(12.0, sizes)


class FontNameTest(unittest.TestCase):
    """שם הגופן של כל אות (chars.font_name), שהכותרות נשענות עליו (hebrew_pdf/markdown.py, סעיף 2). נמדד
    ב-pypdfium2 5.13.0 (PDFium 153.0.7999.0): בקבצים של WeasyPrint, Aspose ו-Canva יש לשם תג של תת-קבוצה
    ("XKQQSR+DejaVu-Sans"), וב-Chrome השם ריק לכל האותיות."""

    @staticmethod
    def fonts(file_name: str, page: int) -> collections.Counter:
        with pdfium.PdfDocument(str(DEFAULT_PDFS / file_name)) as pdf:
            return collections.Counter(c.font for c in page_chars(pdf[page]).chars if c.text.strip())

    def test_names_without_the_subset_tag(self):
        fonts = self.fonts("spec_weasyprint.pdf", 0)
        self.assertEqual(fonts.most_common(1)[0][0], "DejaVu-Sans")
        self.assertIn("DejaVu-Sans-Bold", fonts)
        self.assertFalse([name for name in fonts if "+" in name])

    def test_chrome_has_no_names(self):
        self.assertEqual(set(self.fonts("optimization_chrome.pdf", 0)), {""})


class RowSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = read_pages(TABLE_FILE)

    def test_every_row_has_a_source(self):
        for page in self.pages:
            self.assertEqual(len(page.rows), len(page.sources))
            covered = sorted(i for source in page.sources for i in source.lines)
            self.assertEqual(covered, list(range(len(page.lines))))

    def test_a_table_row_broken_over_three_lines(self):
        # עמודת הרכיב נשברת בעמוד אחרי הלוכסנים: "Bot/WebApp/", "MCP/", "Webserver"
        found = [source for page in self.pages for cells, source in zip(page.rows, page.sources)
                 if cells and cells[0] == "MONGODB_HEARTBEAT_FREQUENCY_MS"]
        self.assertEqual(len(found), 1)
        self.assertEqual(len(found[0].lines), 3)
        self.assertIsNotNone(found[0].table)

    def test_line_geometry(self):
        line = self.pages[0].lines[0]
        self.assertGreater(line.geometry.size, 0)
        self.assertLess(line.geometry.left, line.geometry.right)
        with pdfium.PdfDocument(str(TABLE_FILE)) as pdf:
            self.assertEqual(self.pages[0].height, pdf[0].get_size()[1])


class AllFilesTest(unittest.TestCase):
    """שלמות על כל הסט, כמו בדיקת התצוגה: לא רק על מה שמתויג."""

    @classmethod
    def setUpClass(cls):
        cls.files = {path.name: read_pages(path) for path in sorted(DEFAULT_PDFS.glob("*.pdf"))}

    def test_every_file_is_complete(self):
        self.assertEqual(len(self.files), 15)  # 12 אמיתיים, קובץ הטבלאות, ומסמך האפיון משתי תוכנות
        for name, pages in self.files.items():
            with self.subTest(file=name):
                built = build_markdown(pages)
                result = mc.completeness(pages, built, mc.parse(mc.to_html(built.text)))
                self.assertEqual((dict(result.missing), dict(result.extra)), ({}, {}))
                self.assertEqual(result.items, result.expected_items)

    def test_no_bidi_controls_in_the_output(self):
        # ההחלטה על תו כיוון בתחילת פסקה פתוחה; עד אז הפלט בלי תווי כיוון (tests/test_no_bidi_controls.py)
        controls = set(BIDI)
        for name, pages in self.files.items():
            with self.subTest(file=name):
                self.assertFalse(controls & set(build_markdown(pages).text))

    def test_the_round_trip_loses_no_table_cell(self):
        # התאים שהמפרסר מוציא מה-Markdown זהים לדף התשובות בדיוק כמו התאים של הקורא
        truth = load_truth(DEFAULT_TRUTH / "env-vars.truth.json")
        pages = self.files[TABLE_FILE.name]
        reader = score_tables(TABLE_FILE.name, truth, [row for page in pages for row in page.rows])
        parsed = mc.parse(mc.to_html(build_markdown(pages).text))
        markdown = score_tables(TABLE_FILE.name, truth, [row for table in parsed.tables for row in table])
        self.assertEqual(markdown.identical_cells, reader.identical_cells)


class ChecksCanFailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = read_pages(TABLE_FILE)
        cls.truth = load_truth(DEFAULT_TRUTH / "env-vars.truth.json")

    def test_a_deleted_letter_is_missing(self):
        built = build_markdown(self.pages)
        index = built.text.index("משתני סביבה")
        broken = built.text[:index] + built.text[index + 1:]
        result = mc.completeness(self.pages, built, mc.parse(mc.to_html(broken)))
        self.assertEqual(dict(result.missing), {"מ": 1})
        self.assertFalse(result.ok)

    def test_without_escaping_cells_break(self):
        def cells(markdown_text: str) -> int:
            parsed = mc.parse(mc.to_html(markdown_text))
            return score_tables("x", self.truth, [row for table in parsed.tables for row in table]).identical_cells

        good = cells(build_markdown(self.pages).text)
        with mock.patch.object(markdown_mod, "escape_text", lambda text: text):
            bad = cells(build_markdown(self.pages).text)
        self.assertLess(bad, good)


if __name__ == "__main__":
    unittest.main()
