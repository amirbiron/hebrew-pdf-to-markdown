"""הצורה המצוירת של סוגריים בקבצים האמיתיים (hebrew_pdf/bracket_shapes.py).

האמת כאן היא התיוג: הטקסט הנכון, כשמציגים אותו בפסקה עברית ומשקפים סוגר שנשאר
מימין לשמאל (L4), אומר איך כל סוגר בשורה נראה בעמוד. הבדיקה משווה את זה לצורה
שהקורא זיהה מהציור, בכל השורות המתויגות שיש בהן סוגריים.

בקוד שלפני הזיהוי, התו של הסוגר הוא התו שבקובץ, ובחלק מהשורות הוא לא הצורה: גם
בתוך אותה שורה (שורות 1, 18, 24, 33), שני הצדדים של זוג נשמרו כאותו תו.
"""

import unittest

import pypdfium2 as pdfium

from harness.label_order import shown
from harness.labels import STATUS_APPROVED, parse_labels
from harness.run import DEFAULT_LABELS, DEFAULT_PDFS, DEFAULT_TRUTH
from harness.tables import load_truth
from harness.textdiff import closest_line, join_cells, normalize
from hebrew_pdf.lines import read_document

BRACKETS = frozenset("()[]{}")


def shapes(text: str) -> str:
    """רק הסוגריים, לפי הצד שאליו הם נפתחים: < נפתח ימינה ("(", "["), > שמאלה."""
    return "".join("<" if ch in "([{" else ">" for ch in text if ch in BRACKETS)


class DrawnShapesMatchLabelsTest(unittest.TestCase):
    def test_every_bracket_in_the_labeled_rows(self):
        known = frozenset(p.name for p in DEFAULT_PDFS.glob("*.pdf"))
        labels, _ = parse_labels(DEFAULT_LABELS.read_text(encoding="utf-8"), known)
        checked = 0
        for label in labels:
            if label.status != STATUS_APPROVED or not BRACKETS & set("".join(label.expected)):
                continue
            with pdfium.PdfDocument(str(DEFAULT_PDFS / label.file)) as pdf:
                lines = read_document(pdf)[label.page - 1].lines
            _, closest = closest_line(join_cells(label.expected), [join_cells(line.cells) for line in lines])
            line = next(line for line in lines if normalize(join_cells(line.cells)) == closest)
            with self.subTest(label=label.number):
                # כל תא מוצג בנפרד, והתאים מימין לשמאל (harness/label_order.shown)
                self.assertEqual(shapes(line.visual), shapes(shown(label.expected)))
                checked += len(shapes(line.visual))
        self.assertEqual(checked, 39)  # נמדד: 39 סוגריים ב-11 שורות


class AngleBracketsInTableFileTest(unittest.TestCase):
    """< > ו-« » בקובץ הטבלאות, מול דף התשובות (סבב 5).

    לכל תא בדף התשובות שיש בו סוגר זוויתי או מירכאה זוויתית: הרצף של התווים האלה בתא של הקורא,
    לפי סדר הקריאה, הוא הרצף שבדף התשובות. לפני שהצורה נקבעה מהציור: 2 מתוך 10 ("<job_id>"
    יצא ">job_id>"). התא שנשאר הוא של OBS_AI_EXPLAIN_INTERNAL_PORT: כתובת שהיא קטע קוד ש-WeasyPrint
    מציגה כמבודד, והסדר של כל הקטע שגוי ("http://port>/api>:127.0.0.1"), ולכן גם השיקוף (סבב 6).
    """

    def test_angle_brackets_follow_the_truth(self):
        tables = load_truth(DEFAULT_TRUTH / "env-vars_weasyprint.truth.json")
        truth = {normalize(row[0]): row for table in tables for row in table.rows}
        with pdfium.PdfDocument(str(DEFAULT_PDFS / "env-vars_weasyprint.pdf")) as pdf:
            rows = [row for page in read_document(pdf) for row in page.rows]
        by_first: dict[str, list[tuple[str, ...]]] = {}
        for row in rows:
            if row and normalize(row[0]) in truth:
                by_first.setdefault(normalize(row[0]), []).append(row)

        def angles(text: str) -> str:
            return "".join(ch for ch in text if ch in "<>«»")

        matched, wrong = 0, []
        for first, row in truth.items():
            for column, cell in enumerate(row):
                if not angles(cell):
                    continue
                found = [angles(out[column]) for out in by_first.get(first, []) if column < len(out)]
                if angles(cell) in found:
                    matched += 1
                else:
                    wrong.append(first)
        self.assertEqual(wrong, ["OBS_AI_EXPLAIN_INTERNAL_PORT"])
        self.assertEqual(matched, 9)


if __name__ == "__main__":
    unittest.main()
