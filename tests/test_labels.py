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

    def test_escape_round_trip(self):
        samples = ["a | b", "\\", "a\\|b", "x \\ | y", "שאלה? | תשובת הלקוח", "C:\\path\\", "|"]
        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(split_row("| " + escape_cell(text) + " | z |"), [text, "z"])


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
            (1, "a.pdf", 2, "נכון | עוד", STATUS_APPROVED),
            (2, "b.pdf", 1, "נכון", STATUS_PENDING),
        ])
        self.assertEqual(labels[0].source_line, 5)

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

    def test_missing_table_is_a_file_error(self):
        with self.assertRaises(LabelsFileError):
            parse_labels("# אין כאן טבלה\n", KNOWN)

    def test_missing_delimiter_row_is_a_file_error(self):
        with self.assertRaises(LabelsFileError):
            parse_labels("| " + " | ".join(COLUMNS) + " |\n| 1 | a.pdf | 1 | | x | מאושר |\n", KNOWN)


class RealLabelsFileTest(unittest.TestCase):
    def test_repo_labels_file_parses_cleanly(self):
        known = frozenset(p.name for p in (ROOT / "testset" / "pdfs").glob("*.pdf"))
        labels, problems = parse_labels((ROOT / "testset" / "labels.md").read_text(encoding="utf-8"), known)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(labels), 40)


if __name__ == "__main__":
    unittest.main()
