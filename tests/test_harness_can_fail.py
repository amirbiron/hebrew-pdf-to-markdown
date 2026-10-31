"""מערך הבדיקה מסוגל להיכשל: קורא מקולקל בכוונה מוריד בבירור את מספר השורות הזהות.

הקלקול מופעל על הפלט של הקורא האמיתי (harness/reader.py), ולא על הפנים שלו: הוא
הופך כל רצף של אותיות לטיניות וספרות, כמו קורא שלא החזיר רצפי אנגלית ומספרים
לשמאל-לימין. כך הבדיקה נשארת תקפה גם כשהקורא יוחלף בסבב הבא.

הבדיקה רצה על עותק של טבלת התיוג שבו כל השורות מאושרות, כי בטבלה האמיתית רק שורות
שאושרו ביד נספרות.
"""

import dataclasses
import re
import tempfile
import unittest
from pathlib import Path

from harness.labels import STATUSES, STATUS_APPROVED
from harness.reader import read_pages
from harness.run import DEFAULT_LABELS, DEFAULT_PDFS, evaluate, render_report
from hebrew_pdf.lines import PageText

_LATIN_OR_DIGIT_RUN = re.compile(r"[A-Za-z0-9]+")


def _reverse_runs(text: str) -> str:
    return _LATIN_OR_DIGIT_RUN.sub(lambda m: m.group(0)[::-1], text)


def _broken(line):
    """אותה שורה, עם הקלקול בכל מקום שבו יש טקסט לוגי: השורה, כל רכיב, וכל עמודה."""
    return dataclasses.replace(
        line, text=_reverse_runs(line.text),
        components=tuple(dataclasses.replace(c, text=_reverse_runs(c.text)) for c in line.components),
        columns=None if line.columns is None else tuple(_reverse_runs(c) for c in line.columns))


def reversed_ltr_reader(pdf_path: Path) -> list[PageText]:
    return [PageText([_broken(line) for line in p.lines], p.skipped_chars, p.unknown_brackets,
                     [tuple(_reverse_runs(cell) for cell in row) for row in p.rows])
            for p in read_pages(pdf_path)]


def approve_all(labels_text: str) -> str:
    status_cell = re.compile(r"\| (" + "|".join(map(re.escape, STATUSES)) + r") \|$")
    return "\n".join(status_cell.sub(f"| {STATUS_APPROVED} |", line) for line in labels_text.split("\n"))


class HarnessCanFailTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.labels = Path(cls.tmp.name) / "labels.md"
        cls.labels.write_text(approve_all(DEFAULT_LABELS.read_text(encoding="utf-8")), encoding="utf-8")
        cls.real = evaluate(DEFAULT_PDFS, cls.labels)
        cls.broken = evaluate(DEFAULT_PDFS, cls.labels, reader=reversed_ltr_reader)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_all_rows_are_counted_in_the_approved_copy(self):
        self.assertEqual(self.real.problems, [])
        self.assertEqual(self.real.pending, [])
        self.assertGreaterEqual(len(self.real.approved), 40)

    def test_broken_reader_loses_exact_lines(self):
        self.assertGreater(self.real.exact_count, 0)
        # ירידה ברורה: לפחות חצי מהשורות הזהות נשברות (נמדד: 10 ← 3 בטיוטת התיוג הראשונה)
        self.assertLessEqual(self.broken.exact_count, self.real.exact_count // 2)

    def test_broken_reader_increases_distance(self):
        self.assertGreater(self.broken.total_distance, self.real.total_distance * 3 // 2)

    def test_report_is_deterministic(self):
        again = evaluate(DEFAULT_PDFS, self.labels)
        self.assertEqual(render_report(again), render_report(self.real))


if __name__ == "__main__":
    unittest.main()
