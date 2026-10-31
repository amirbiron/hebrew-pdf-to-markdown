"""הדוח מציג את הטקסט כמו שהוא: תחביר של Markdown בתוך תא לא מעצב אותו."""

import unittest

from harness.label_order import MISSING, OrderCheck
from harness.labels import STATUS_APPROVED, Label
from harness.run import Evaluation, LabelResult, _candidates, render_report
from harness.textdiff import closest_line, join_cells, normalize
from hebrew_pdf.lines import Component, Line


def report_with_closest_line(closest: str, expected: tuple[str, ...] = ("טקסט נכון",),
                             order: OrderCheck | None = None) -> str:
    label = Label(1, "a.pdf", 1, "", expected, STATUS_APPROVED, 5)
    ev = Evaluation("reader", [], [LabelResult(label, 9, closest)], [], [], [], {1: order} if order else {})
    return render_report(ev)


class CandidatesTest(unittest.TestCase):
    """תיוג של תא אחד נמדד גם מול כל תא בנפרד ("שורה אחת" ב-testset/labels.md)."""

    def test_one_cell_label_matches_one_box_of_the_line(self):
        line = Line("עוזרים לעסק מסמך אפיון", "", True, components=(
            Component("עוזרים לעסק", "", True), Component("מסמך אפיון", "", True)))
        label = Label(21, "a.pdf", 1, "", ("עוזרים לעסק",), STATUS_APPROVED, 5)
        self.assertEqual(closest_line(join_cells(label.expected), _candidates(label, [line])), (0, "עוזרים לעסק"))

    def test_a_label_with_cells_is_measured_against_whole_lines_only(self):
        line = Line("א ב", "", True, components=(Component("א", "", True), Component("ב", "", True)))
        label = Label(2, "a.pdf", 1, "", ("א", "ג"), STATUS_APPROVED, 5)
        self.assertEqual(_candidates(label, [line]), [join_cells(("א", "ב"))])


class ReportCellTest(unittest.TestCase):
    def row(self, closest: str, **kwargs) -> str:
        rows = [line for line in report_with_closest_line(closest, **kwargs).split("\n") if line.startswith("| 1 |")]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_cells_are_shown_one_per_line_like_in_the_labels_file(self):
        row = self.row(normalize(join_cells(("א", "ב"))), expected=("שאלה?", "", "תשובה"))
        self.assertIn("| שאלה? <br>  <br> תשובה |", row)
        self.assertIn("| א <br> ב |", row)

    def test_br_as_text_is_not_a_boundary(self):
        self.assertIn("| a \\<br> b |", self.row("x", expected=("a <br> b",)))

    def test_order_check_result(self):
        self.assertIn("| ✗ חסר בעמוד: GPS |", self.row("x", order=OrderCheck(MISSING, "GPS")))

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
