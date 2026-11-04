"""צורות ההשחתה של סבב 6ב (harness/calibration.py, BLIND): כל אחת היא כשל שהקורא עוד עושה, וכל שורה אחריה עדיין
מוצגת כמו העמוד. הטסטים בונים כל צורה על עמוד אמיתי ובודקים שהיא עשתה את מה שהיא אומרת, ושבדיקת התצוגה והשלמות
באמת לא רואות אותה: אחרת הטבלה בדוח לא מודדת את הנקודה העיוורת אלא משהו אחר."""

import random
import unittest
from collections import Counter

from harness import calibration
from harness.reader import read_pages
from harness.run import DEFAULT_PDFS
from hebrew_pdf import score
from hebrew_pdf.logical_order import to_logical
from hebrew_pdf.markdown import build_markdown


def form(key: str) -> calibration.Form:
    return next(f for f in calibration.FORMS if f.key == key)


def parts(page) -> list:
    return [part for line in page.lines for part in line.parts]


class BlindFormsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text_page = read_pages(DEFAULT_PDFS / "optimization_chrome.pdf")[0]
        spec = read_pages(DEFAULT_PDFS / "spec_chrome.pdf")
        cls.table_page = next(p for p in spec if sum(s.table is not None for s in p.sources) >= 4)
        cls.dropped = frozenset()

    def assert_blind(self, before, after):
        """כל רכיב מוצג כמו העמוד, ואף תו לא חסר או נוסף."""
        self.assertTrue(all(score.shows_as_page(part) for part in parts(after) if part.visual.strip(" ")))
        self.assertEqual(score._completeness(after).ok, score._completeness(before).ok)

    def test_a_space_that_was_dropped(self):
        page = self.text_page
        after = calibration.corrupt(page, self.dropped, form("drop_space"), "one", random.Random(1))
        changed = [(a, b) for a, b in zip(parts(page), parts(after)) if a.visual != b.visual]
        self.assertEqual(len(changed), 1)
        before_part, after_part = changed[0]
        self.assertEqual(after_part.visual.count(" "), before_part.visual.count(" ") - 1)
        self.assertEqual(after_part.visual.replace(" ", ""), before_part.visual.replace(" ", ""))
        # הטקסט הוא מה שקורא עם ההחלטה הזו היה מוציא: הסדר הלוגי של מה שבעמוד
        self.assertEqual(after_part.text, "".join(to_logical(list(after_part.visual), lambda c: c, True).texts))
        self.assertEqual(after_part.text.count(" "), before_part.text.count(" ") - 1)
        self.assert_blind(page, after)

    def test_a_space_inside_a_word(self):
        page = self.text_page
        after = calibration.corrupt(page, self.dropped, form("split_word"), "all", random.Random(1))
        for a, b in zip(parts(page), parts(after)):
            if a.visual != b.visual:
                self.assertEqual(b.visual.replace(" ", ""), a.visual.replace(" ", ""))
                self.assertEqual(b.visual.count(" "), a.visual.count(" ") + 1)
        self.assert_blind(page, after)

    def test_two_table_rows_merged(self):
        page = self.table_page
        after = calibration.corrupt(page, self.dropped, form("merge_rows"), "one", random.Random(1))
        self.assertEqual(len(after.rows), len(page.rows) - 1)
        self.assertEqual(Counter("".join(cell for row in after.rows for cell in row).replace(" ", "")),
                         Counter("".join(cell for row in page.rows for cell in row).replace(" ", "")))
        self.assertEqual(after.lines, page.lines)
        self.assert_blind(page, after)

    def test_a_cell_in_the_next_column(self):
        page = self.table_page
        after = calibration.corrupt(page, self.dropped, form("shift_cell"), "one", random.Random(1))
        changed = [(a, b) for a, b in zip(page.rows, after.rows) if a != b]
        self.assertEqual(len(changed), 1)
        before_row, after_row = changed[0]
        self.assertEqual(sum(1 for a, b in zip(before_row, after_row) if a != b), 2)
        self.assertEqual("".join(after_row).replace(" ", "").__len__(), "".join(before_row).replace(" ", "").__len__())
        self.assert_blind(page, after)

    def test_two_blocks_interleaved(self):
        page = self.text_page
        after = calibration.corrupt(page, self.dropped, form("interleave"), "one", random.Random(1))
        moved = [k for k, (a, b) in enumerate(zip(page.lines, after.lines)) if a is not b]
        self.assertEqual(len(moved), 2)  # א1 א2 ב1 ב2: האמצעיות מתחלפות
        self.assertEqual(sorted(map(id, page.lines)), sorted(map(id, after.lines)))
        self.assertEqual([row for row, s in zip(after.rows, after.sources) if s.table is None],
                         [line.cells for line in after.lines])
        self.assert_blind(page, after)

    def test_forms_that_do_not_apply_return_none(self):
        # עמוד בלי טבלה: אין שורות טבלה לאחד ואין תא להזיז
        self.assertIsNone(calibration.corrupt(self.text_page, self.dropped, form("merge_rows"), "one", random.Random(1)))
        self.assertIsNone(calibration.corrupt(self.text_page, self.dropped, form("shift_cell"), "one", random.Random(1)))


class DecideTest(unittest.TestCase):
    def test_a_short_page_is_not_flagged_by_the_signals(self):
        out = calibration.Outcome(False, plausible=0.5, words=10)
        self.assertFalse(calibration.decide(out, score.MIN_PLAUSIBLE)["סימנים"])
        self.assertTrue(calibration.decide(calibration.Outcome(False, plausible=0.5, words=40),
                                           score.MIN_PLAUSIBLE)["סימנים"])

    def test_near_decisions_are_evidence_and_not_a_rule(self):
        hits = calibration.decide(calibration.Outcome(False, words=40, near=5), score.MIN_PLAUSIBLE)
        self.assertTrue(hits["קרוב לסף"])
        self.assertFalse(hits["עם הראיות"])

    def test_the_new_evidence_decides(self):
        for field in ("bad_numbers", "crowded"):
            out = calibration.Outcome(False, words=40, **{field: 1})
            hits = calibration.decide(out, score.MIN_PLAUSIBLE)
            self.assertFalse(hits["היום"], field)
            self.assertTrue(hits["עם הראיות"], field)

    def test_the_chosen_range_stays_when_its_middle_is_above_the_requirement(self):
        values = [0.70, 0.74, 0.80, 0.84]
        self.assertEqual(calibration.chosen_range(values, 0.75), calibration.Range(0.74, 0.80))
        # האמצע של הטווח שמכיל את הדרישה מתחתיה: הטווח הבא, כמו הכלל של סבב 6
        self.assertEqual(calibration.chosen_range(values, 0.78), calibration.Range(0.80, 0.84))


if __name__ == "__main__":
    unittest.main()
