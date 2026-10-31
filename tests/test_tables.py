"""מדידת הטבלאות מול דף התשובות (harness/tables.py).

ארבעה חלקים: קריאת דף התשובות (קלט מחוץ לתהליך: כל מבנה לא תקין נעצר עם סיבה), החישוב
על מקרים קטנים, דף התשובות שבריפו, והמדידה הראשונה שתועדה ב-testset/ground_truth/README.md:
אותו מדד על הפלט של האב-טיפוס חייב לתת את אותם מספרים, כדי שהמספרים בפרוזה והקוד לא
ייפרדו בלי שמישהו ישים לב.
"""

import json
import tempfile
import unicodedata
import unittest
from pathlib import Path

import pypdfium2 as pdfium

from harness.reader import read_pages
from harness.run import DEFAULT_PDFS, DEFAULT_TRUTH
from harness.tables import TruthFileError, TruthTable, load_truth, pdf_name, score_tables
from prototype import hebrew_pdf_prototype as prototype
from tests.test_harness_can_fail import reversed_ltr_reader

TRUTH = DEFAULT_TRUTH / "env-vars_weasyprint.truth.json"
HEADER = ("משתנה", "תיאור", "ברירת מחדל")


def table(*rows: tuple[str, ...]) -> TruthTable:
    return TruthTable("סעיף", HEADER, tuple(rows))


class LoadTruthTest(unittest.TestCase):
    def load(self, data) -> list[TruthTable]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.truth.json"
            path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
            return load_truth(path)

    def test_valid(self):
        tables = self.load({"tables": [{"section": "ס", "rows": [["א", "ב"], ["X", ""]]}]})
        self.assertEqual(tables, [TruthTable("ס", ("א", "ב"), (("X", ""),))])

    def test_bad_structures_stop_with_a_reason(self):
        good_rows = [["א", "ב"], ["X", "1"]]
        cases = {
            "not json": "JSON",
            json.dumps([1, 2]): "tables",
            json.dumps({"tables": []}): "tables",
            json.dumps({"tables": ["x"]}): "לא אובייקט",
            json.dumps({"tables": [{"section": 3, "rows": good_rows}]}): "section",
            json.dumps({"tables": [{"rows": "x"}]}): "rows",
            json.dumps({"tables": [{"rows": [["א"], [1]]}]}): "לא רשימה של טקסטים",
            json.dumps({"tables": [{"rows": [[], ["X"]]}]}): "שורת הכותרת ריקה",
            json.dumps({"tables": [{"rows": [["א", "ב"], ["X"]]}]}): "1 תאים במקום 2",
            json.dumps({"tables": [{"rows": [["א"], ["  "]]}]}): "התא הראשון ריק",
            json.dumps({"tables": [{"rows": good_rows}, {"rows": good_rows}]}): "כבר מופיע בטבלה 1",
        }
        for data, message in cases.items():
            with self.subTest(data=data):
                with self.assertRaises(TruthFileError) as caught:
                    self.load(data)
                self.assertIn(message, str(caught.exception))

    def test_pdf_name(self):
        self.assertEqual(pdf_name(TRUTH), "env-vars_weasyprint.pdf")


class ScoreTest(unittest.TestCase):
    def test_exact_rows_in_any_order_among_other_lines(self):
        truth = [table(("A_VAR", "תיאור ארוך של A", "10"), ("B_VAR", "תיאור של B", ""))]
        output = [("כותרת",), ("B_VAR", "תיאור של B", ""), ("טקסט אחר",), ("A_VAR", "תיאור ארוך של A", "10")]
        score = score_tables("x.pdf", truth, output)
        self.assertEqual((score.rows, score.aligned, score.identical_rows), (2, 2, 2))
        self.assertEqual((score.cells, score.identical_cells), (6, 6))

    def test_a_line_that_is_one_cell_does_not_align(self):
        # כך נראה קורא שלא מפריד בין תאים: כל השורה היא תא אחד
        score = score_tables("x.pdf", [table(("A_VAR", "תיאור", "10"))], [("A_VAR תיאור 10",)])
        self.assertEqual((score.aligned, score.identical_cells), (0, 0))
        self.assertEqual(score.whole, 2)  # "A_VAR" ו-"תיאור" מופיעים ברצף בשורה, גם בלי גבולות ("10" קצר מדי)

    def test_an_empty_cell_must_be_an_empty_cell(self):
        # בלי התא הריק כל מה שאחריו זז מקום, כמו "תא ריק נשאר ריק" בטבלת התיוג
        truth = [table(("A_VAR", "", "10"))]
        dropped = score_tables("x.pdf", truth, [("A_VAR", "10")])
        kept = score_tables("x.pdf", truth, [("A_VAR", "", "10")])
        self.assertEqual((dropped.identical_cells, dropped.identical_rows), (1, 0))
        self.assertEqual((kept.identical_cells, kept.identical_rows), (3, 1))

    def test_spaces_are_collapsed(self):
        score = score_tables("x.pdf", [table(("A_VAR", "שני  רווחים", "1"))], [(" A_VAR", "שני רווחים ", "1")])
        self.assertEqual(score.identical_rows, 1)

    def test_extra_cells_make_the_row_not_identical(self):
        score = score_tables("x.pdf", [table(("A_VAR", "ת", "1"))], [("A_VAR", "ת", "1", "עוד")])
        self.assertEqual((score.identical_cells, score.identical_rows), (3, 0))

    def test_of_several_lines_with_the_same_first_cell_the_best_one_counts(self):
        truth = [table(("A_VAR", "תיאור", "10"))]
        output = [("A_VAR",), ("A_VAR", "תיאור", "10"), ("A_VAR", "תיאור")]
        self.assertEqual(score_tables("x.pdf", truth, output).identical_rows, 1)

    def test_cell_broken_over_two_lines_is_not_whole(self):
        truth = [table(("A_VAR", "תיאור ארוך שנשבר", "10"))]
        score = score_tables("x.pdf", truth, [("A_VAR", "תיאור ארוך", "10"), ("שנשבר",)])
        description = next(c for c in score.columns if c.name == "תיאור")
        self.assertEqual((description.whole_counted, description.whole), (1, 0))

    def test_short_cells_are_not_counted_as_whole(self):
        score = score_tables("x.pdf", [table(("A_VAR", "כן", "10"))], [("A_VAR", "כן", "10")])
        self.assertEqual(score.whole_counted, 1)  # רק A_VAR: "כן" ו-"10" קצרים מדי

    def test_columns_with_the_same_header_are_counted_together(self):
        truth = [table(("A_VAR", "א", "1")), table(("B_VAR", "ב", "2"))]
        score = score_tables("x.pdf", truth, [])
        self.assertEqual([(c.name, c.cells) for c in score.columns], [(name, 2) for name in HEADER])


class RepoTruthFileTest(unittest.TestCase):
    def test_loads_cleanly(self):
        tables = load_truth(TRUTH)
        self.assertEqual(len(tables), 6)
        self.assertEqual(sum(len(t.rows) for t in tables), 468)
        self.assertEqual(tables[0].header, ("משתנה", "תיאור", "חובה", "ברירת מחדל", "דוגמה", "רכיב"))

    def test_no_invisible_format_characters(self):
        # התא מציג טקסט, ותו עיצוב בלתי נראה (Cf, כמו RLM) לא מוצג (tools/build_table_pdf.py)
        cells = [cell for t in load_truth(TRUTH) for row in (t.header, *t.rows) for cell in row]
        self.assertEqual([cell for cell in cells if any(unicodedata.category(ch) == "Cf" for ch in cell)], [])

    def test_every_truth_file_has_its_pdf(self):
        truth_files = sorted(DEFAULT_TRUTH.glob("*.truth.json"))
        self.assertTrue(truth_files)
        for path in truth_files:
            self.assertTrue((DEFAULT_PDFS / pdf_name(path)).exists(), path.name)


class FirstMeasurementTest(unittest.TestCase):
    """המדידה הראשונה, לפני כל טיפול בטבלאות (testset/ground_truth/README.md): "מבין 1,820
    התאים שנבדקו ... 55% נמצאו שלמים בשורה אחת של הפלט. עמודת התיאור: 6%"."""

    @classmethod
    def setUpClass(cls):
        cls.tables = load_truth(TRUTH)
        with pdfium.PdfDocument(str(DEFAULT_PDFS / "env-vars_weasyprint.pdf")) as pdf:
            prototype_lines = [line for page in pdf for line in prototype.page_text(page).split("\n")]
        cls.prototype = score_tables("env-vars_weasyprint.pdf", cls.tables, [(line,) for line in prototype_lines])

    def test_the_documented_numbers(self):
        self.assertEqual(self.prototype.whole_counted, 1820)
        self.assertEqual(round(100 * self.prototype.whole / self.prototype.whole_counted), 55)
        description = next(c for c in self.prototype.columns if c.name == "תיאור")
        self.assertEqual(round(100 * description.whole / description.whole_counted), 6)

    def test_a_broken_reader_scores_lower(self):
        # המדידה רגישה לקורא: קורא שהופך כל רצף לטיני וספרות מאבד תאים שלמים
        def rows(reader):
            return [line.cells for p in reader(DEFAULT_PDFS / "env-vars_weasyprint.pdf") for line in p.lines]
        real = score_tables("x.pdf", self.tables, rows(read_pages))
        broken = score_tables("x.pdf", self.tables, rows(reversed_ltr_reader))
        self.assertLess(broken.whole, real.whole * 3 // 4)


if __name__ == "__main__":
    unittest.main()
