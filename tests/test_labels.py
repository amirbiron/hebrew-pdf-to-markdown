"""קריאת טבלת התיוג: escapes, ולידציה של כל תא, והקובץ האמיתי שבריפו."""

import unittest
from pathlib import Path

from harness.labels import (
    COLUMNS,
    STATUS_APPROVED,
    STATUS_PENDING,
    LabelsFileError,
    escape_cell,
    parse_labels,
    split_cells,
    split_row,
)

ROOT = Path(__file__).resolve().parent.parent
KNOWN = frozenset({"a.pdf", "b.pdf"})
HEADER = "| " + " | ".join(COLUMNS) + " |\n|---|---|---|---|---|---|\n"


class SplitRowTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(split_row("| 1 | שלום | x |"), ["1", "שלום", "x"])

    def test_escaped_pipe_stays_in_cell(self):
        self.assertEqual(split_row(r"| a \| b | c |"), ["a | b", "c"])

    def test_escaped_backslash_then_real_pipe(self):
        self.assertEqual(split_row(r"| a\\| b |"), ["a\\", "b"])

    def test_backslash_before_letter_is_kept(self):
        self.assertEqual(split_row(r"| C:\path |"), [r"C:\path"])

    def test_no_trailing_pipe(self):
        self.assertEqual(split_row("| a | b"), ["a", "b"])

    def test_empty_cell(self):
        self.assertEqual(split_row("| a | | b |"), ["a", "", "b"])

    def test_no_leading_pipe(self):
        self.assertEqual(split_row("a | b |"), ["a", "b"])

    def test_formatting_characters_are_escaped(self):
        self.assertEqual(escape_cell("*א* _ב_ `ג` ~ד~ <ה> [ו] &ז"),
                         "\\*א\\* \\_ב\\_ \\`ג\\` \\~ד\\~ \\<ה> \\[ו\\] \\&ז")

    def test_escape_round_trip(self):
        samples = ["a | b", "\\", "a\\|b", "x \\ | y", "שאלה? | תשובת הלקוח", "C:\\path\\", "|",
                   "סה\"כ *לא* כולל", "__init__", "<b>x</b> &amp;", "[קישור](http://x)", "~מחוק~", "`קוד`"]
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(split_row("| " + escape_cell(text) + " | z |"), [text, "z"])


class CellSeparatorTest(unittest.TestCase):
    """גבול בין תאים ב"הטקסט הנכון" הוא <br>, ו-\\| הוא תמיד התו | עצמו (שורה 32 מול 38)."""

    def test_br_separates_cells(self):
        self.assertEqual(split_cells("שאלה? <br> תשובת הלקוח"), ("שאלה?", "תשובת הלקוח"))

    def test_empty_cell_stays_empty(self):
        self.assertEqual(split_cells("הכנסות ממכירות <br> <br> 366,343"), ("הכנסות ממכירות", "", "366,343"))

    def test_every_form_github_shows_as_a_line_break(self):
        for raw in ("א<br>ב", "א<br/>ב", "א <br /> ב", "א<BR>ב", 'א<br class="x">ב'):
            with self.subTest(raw=raw):
                self.assertEqual(split_cells(raw), ("א", "ב"))

    def test_other_tags_are_text(self):
        self.assertEqual(split_cells("a <brx> b <b> c"), ("a <brx> b <b> c",))

    def test_escaped_br_is_text(self):
        self.assertEqual(split_cells(r"a \<br> b"), ("a <br> b",))

    def test_escaped_backslash_then_a_real_br(self):
        self.assertEqual(split_cells(r"a\\<br>b"), ("a\\", "b"))

    def test_escaped_pipe_is_text_not_a_boundary(self):
        self.assertEqual(split_cells(r"מאיה קארגי \| 058-7999120 \| OOHMYWEB.COM"),
                         ("מאיה קארגי | 058-7999120 | OOHMYWEB.COM",))


class ParseLabelsTest(unittest.TestCase):
    def parse(self, rows: str):
        return parse_labels("# כותרת\n\n" + HEADER + rows + "\nהערות אחרי הטבלה | לא נקראות\n", KNOWN)

    def test_valid_rows(self):
        labels, problems = self.parse(
            f"| 1 | a.pdf | 2 | פלט | נכון \\| עוד | {STATUS_APPROVED} |\n"
            f"| 2 | b.pdf | 1 | | נכון | {STATUS_PENDING} |\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual([(l.number, l.file, l.page, l.expected, l.status) for l in labels], [
            (1, "a.pdf", 2, ("נכון | עוד",), STATUS_APPROVED),
            (2, "b.pdf", 1, ("נכון",), STATUS_PENDING),
        ])
        self.assertEqual(labels[0].source_line, 5)

    def test_row_with_cells(self):
        labels, problems = self.parse(f"| 1 | a.pdf | 2 | פלט | א <br> <br> ב \\| ג | {STATUS_APPROVED} |\n")
        self.assertEqual(problems, [])
        self.assertEqual(labels[0].expected, ("א", "", "ב | ג"))

    def test_only_empty_cells_is_an_empty_text(self):
        labels, problems = self.parse(f"| 1 | a.pdf | 2 | פלט | <br> | {STATUS_APPROVED} |\n")
        self.assertEqual(labels, [])
        self.assertIn("הטקסט הנכון ריק", problems[0].message)

    def test_bad_rows_are_reported_not_swallowed(self):
        cases = {
            f"| 1 | a.pdf | 2 | פלט | נכון | עוד | {STATUS_APPROVED} |": "7 תאים",
            f"| 1a | a.pdf | 2 | פלט | נכון | {STATUS_APPROVED} |": "מספר לא תקין",
            f"| \u0661 | a.pdf | 2 | פלט | נכון | {STATUS_APPROVED} |": "מספר לא תקין",  # ספרה ערבית-הודית: int() היה מקבל אותה
            f"| 0 | a.pdf | 2 | פלט | נכון | {STATUS_APPROVED} |": "מספר לא תקין",
            f"| 1 | c.pdf | 2 | פלט | נכון | {STATUS_APPROVED} |": "קובץ לא מוכר",
            f"| 1 | a.pdf | 0 | פלט | נכון | {STATUS_APPROVED} |": "עמוד לא תקין",
            f"| 1 | a.pdf | 2 | פלט | | {STATUS_APPROVED} |": "הטקסט הנכון ריק",
            "| 1 | a.pdf | 2 | פלט | נכון | אושר |": "סטטוס לא מוכר",
        }
        for row, expected_message in cases.items():
            with self.subTest(row=row):
                labels, problems = self.parse(row + "\n")
                self.assertEqual(labels, [])
                self.assertEqual(len(problems), 1)
                self.assertIn(expected_message, problems[0].message)
                self.assertEqual(problems[0].source_line, 5)

    def test_duplicate_number(self):
        labels, problems = self.parse(
            f"| 1 | a.pdf | 1 | | x | {STATUS_APPROVED} |\n| 1 | a.pdf | 2 | | y | {STATUS_APPROVED} |\n")
        self.assertEqual(len(labels), 1)
        self.assertEqual(len(problems), 1)
        self.assertIn("כבר מופיע בשורה 5", problems[0].message)

    def test_row_without_leading_pipe_is_read_like_github_shows_it(self):
        # ב-GFM ה-| בקצוות לא חובה, ו-GitHub מציג את השורה כשורה רגילה בטבלה
        labels, problems = self.parse(
            f"| 1 | a.pdf | 1 | | x | {STATUS_APPROVED} |\n"
            f"2 | a.pdf | 1 | | y | {STATUS_APPROVED} |\n"
            f"| 3 | a.pdf | 1 | | z | {STATUS_APPROVED} |\n")
        self.assertEqual(problems, [])
        self.assertEqual([l.number for l in labels], [1, 2, 3])

    def test_text_line_inside_the_table_is_a_problem_and_rows_after_it_are_read(self):
        labels, problems = self.parse(
            f"| 1 | a.pdf | 1 | | x | {STATUS_APPROVED} |\n"
            "הערה שנכתבה בטעות בתוך הטבלה\n"
            f"| 3 | a.pdf | 1 | | z | {STATUS_APPROVED} |\n")
        self.assertEqual([l.number for l in labels], [1, 3])
        self.assertEqual([(p.source_line, "1 תאים" in p.message) for p in problems], [(6, True)])

    def test_heading_ends_the_table_without_a_problem(self):
        labels, problems = self.parse(
            f"| 1 | a.pdf | 1 | | x | {STATUS_APPROVED} |\n## Notes | details\nטקסט | עם קו\n")
        self.assertEqual([l.number for l in labels], [1])
        self.assertEqual(problems, [])

    def test_label_row_after_the_table_is_reported_not_dropped(self):
        labels, problems = self.parse(
            f"| 1 | a.pdf | 1 | | x | {STATUS_APPROVED} |\n\n| 2 | a.pdf | 1 | | y | {STATUS_APPROVED} |\n")
        self.assertEqual([l.number for l in labels], [1])
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].source_line, 7)
        self.assertIn("מחוץ לטבלה", problems[0].message)

    def test_missing_table_is_a_file_error(self):
        with self.assertRaises(LabelsFileError):
            parse_labels("# אין כאן טבלה\n", KNOWN)

    def test_delimiter_row_with_wrong_cell_count_is_a_file_error(self):
        text = "| " + " | ".join(COLUMNS) + " |\n|---|---|\n| 1 | a.pdf | 1 | | x | מאושר |\n"
        with self.assertRaises(LabelsFileError) as caught:
            parse_labels(text, KNOWN)
        self.assertIn("2 תאים במקום 6", str(caught.exception))

    def test_missing_delimiter_row_is_a_file_error(self):
        with self.assertRaises(LabelsFileError):
            parse_labels("| " + " | ".join(COLUMNS) + " |\n| 1 | a.pdf | 1 | | x | מאושר |\n", KNOWN)


class RealLabelsFileTest(unittest.TestCase):
    def test_repo_labels_file_parses_cleanly(self):
        known = frozenset(p.name for p in (ROOT / "testset" / "pdfs").glob("*.pdf"))
        labels, problems = parse_labels((ROOT / "testset" / "labels.md").read_text(encoding="utf-8"), known)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(labels), 40)

    def test_rows_with_cells_and_a_real_pipe(self):
        # המרת המפריד: בשורות האלה | היה גבול בין תאים, ובשורה 32 הוא תו אמיתי בעמוד
        known = frozenset(p.name for p in (ROOT / "testset" / "pdfs").glob("*.pdf"))
        labels, _ = parse_labels((ROOT / "testset" / "labels.md").read_text(encoding="utf-8"), known)
        by_number = {label.number: label for label in labels}
        self.assertEqual(sorted(n for n, label in by_number.items() if len(label.expected) > 1), [2, 8, 11, 38, 39, 40])
        self.assertEqual(by_number[38].expected[:3], ("הכנסות ממכירות", "", "366,343"))
        self.assertEqual(by_number[32].expected, ("מאיה קארגי | 058-7999120 | OOHMYWEB.COM",))


if __name__ == "__main__":
    unittest.main()
