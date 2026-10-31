"""הדוח מציג את הטקסט כמו שהוא: תחביר של Markdown בתוך תא לא מעצב אותו."""

import unittest

from harness.labels import STATUS_APPROVED, Label
from harness.run import Evaluation, LabelResult, render_report


def report_with_closest_line(closest: str) -> str:
    label = Label(1, "a.pdf", 1, "", "טקסט נכון", STATUS_APPROVED, 5)
    ev = Evaluation("reader", [], [LabelResult(label, 9, closest)], [], [], [])
    return render_report(ev)


class ReportCellTest(unittest.TestCase):
    def row(self, closest: str) -> str:
        rows = [line for line in report_with_closest_line(closest).split("\n") if line.startswith("| 1 |")]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_markdown_syntax_is_escaped(self):
        row = self.row("סה\"כ *לא* כולל __init__ <b>x</b> [ק](http://x) ~~מ~~ `ק`")
        self.assertIn("\\*לא\\*", row)
        self.assertIn("\\_\\_init\\_\\_", row)
        self.assertIn("\\<b>", row)
        self.assertIn("\\[ק\\]", row)
        self.assertIn("\\~\\~מ\\~\\~", row)
        self.assertIn("\\`ק\\`", row)

    def test_dollar_sign_cannot_open_math(self):
        # GitHub מציג $...$ כנוסחה. מחוץ לנוסחה התיעוד שלו אומר לעטוף את ה-$ ב-span
        row = self.row("שווי $5 ו-$7")
        self.assertIn("שווי <span>$</span>5 ו-<span>$</span>7", row)


if __name__ == "__main__":
    unittest.main()
