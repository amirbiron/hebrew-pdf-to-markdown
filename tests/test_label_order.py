"""בדיקת הסדר של טבלת התיוג (harness/label_order.py).

שני חלקים: מקרים קטנים שמראים מה הבדיקה תופסת, והתוצאה על טבלת התיוג האמיתית. בטבלה
האמיתית שלוש שורות לא עוברות, וכולן "חסר בעמוד": טקסט שנראה בעמוד ולא קיים בקובץ
(GPS ו-? בפלאייר, אימוג'י במצגת). שורה נוספת שנכשלת, או שורה שהפסיקה להיכשל, מפילות
את הבדיקה.
"""

import unittest

from harness.label_order import (
    MISSING,
    NOT_CHECKED,
    OTHER_ORDER,
    PART_OF_LINE,
    WHOLE_LINE,
    OrderCheck,
    check_label_order,
)
from harness.run import DEFAULT_LABELS, DEFAULT_PDFS, evaluate
from hebrew_pdf.lines import Line


def page(*visuals: str, rtl: bool = True) -> list[Line]:
    """שורות של עמוד, מהתווים כמו שהם בעמוד משמאל לימין. הטקסט הלוגי לא משנה לבדיקה."""
    return [Line("", visual, rtl) for visual in visuals]


class OrderCheckTest(unittest.TestCase):
    def test_correct_order_is_the_whole_line(self):
        self.assertEqual(check_label_order(("שלום Meta, Google עולם",), page("םלוע Meta, Google םולש")),
                         OrderCheck(WHOLE_LINE))

    def test_reversed_english_order_is_caught(self):
        self.assertEqual(check_label_order(("שלום Google, Meta עולם",), page("םלוע Meta, Google םולש")),
                         OrderCheck(OTHER_ORDER))

    def test_spaces_do_not_count(self):
        # הבדיקה היא על הסדר; הרווחים בשורה בעמוד הם של הקורא, לפי הפערים
        self.assertEqual(check_label_order(("ומה איתך",), page("ךתיאה מו")), OrderCheck(WHOLE_LINE))

    def test_part_of_a_line_with_two_columns(self):
        self.assertEqual(check_label_order(("עוזרים לעסק",), page("תושירד ךמסמ   קסעל םירזוע")),
                         OrderCheck(PART_OF_LINE))

    def test_cells_are_laid_right_to_left(self):
        # התא הראשון בסדר הקריאה הוא הימני ביותר, וכל תא מוצג בנפרד
        lines = page("Deep Dive תולאש   םייזכרמ םילודומ")
        self.assertEqual(check_label_order(("מודולים מרכזיים", "שאלות Deep Dive"), lines), OrderCheck(WHOLE_LINE))
        self.assertEqual(check_label_order(("שאלות Deep Dive", "מודולים מרכזיים"), lines), OrderCheck(OTHER_ORDER))

    def test_each_cell_is_shown_on_its_own(self):
        # כשמציגים את שני התאים כפסקה אחת, "FastAPI" ו-"Backend" נצמדים לרצף אנגלי אחד
        # ומתחלפים; כשכל תא מוצג בנפרד, הסדר הוא של העמוד
        lines = page("API תרש   FastAPI + Python 3.12   Backend")
        self.assertEqual(check_label_order(("Backend", "FastAPI + Python 3.12", "שרת API"), lines),
                         OrderCheck(WHOLE_LINE))
        self.assertEqual(check_label_order(("Backend FastAPI + Python 3.12 שרת API",), lines), OrderCheck(OTHER_ORDER))

    def test_bracket_direction_is_checked_not_only_its_place(self):
        # סוגר בצד הלא נכון: כל התווים נמצאים, אבל הצורה אחרי שיקוף (L4) לא מה שמצויר
        lines = page("(םולש)")
        self.assertEqual(check_label_order(("(שלום)",), lines), OrderCheck(WHOLE_LINE))
        self.assertEqual(check_label_order((")שלום(",), lines), OrderCheck(OTHER_ORDER))

    def test_text_that_is_not_in_the_file(self):
        # GPS בפלאייר: בקובץ שלושה תווי בקרה במקום האותיות
        self.assertEqual(check_label_order(("בחרו ב GPS לעסקים",), page("םיקסעל \x1d\x1e\x1f ב ורחב")),
                         OrderCheck(MISSING, "GPS"))

    def test_missing_hebrew_is_reported_in_reading_order(self):
        self.assertEqual(check_label_order(("שלום עולם",), page("םלוע")), OrderCheck(MISSING, "שלום"))

    def test_the_line_with_most_shared_characters_is_used(self):
        lines = page("רחא והשמ", "םלוע Meta, Google םולש", "Meta")
        self.assertEqual(check_label_order(("שלום Meta, Google עולם",), lines), OrderCheck(WHOLE_LINE))

    def test_left_to_right_paragraph_is_not_checked(self):
        self.assertEqual(check_label_order(("Hello world",), page("Hello world", rtl=False)), OrderCheck(NOT_CHECKED))

    def test_empty_page(self):
        self.assertEqual(check_label_order(("שלום",), []), OrderCheck(MISSING, "שלום"))


class RealLabelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = evaluate(DEFAULT_PDFS, DEFAULT_LABELS, truth_dir=None)

    def test_every_label_is_checked_in_every_status(self):
        numbers = [r.label.number for r in self.ev.approved] + [l.number for l in self.ev.pending + self.ev.unclear]
        self.assertEqual(sorted(self.ev.orders), sorted(numbers))
        self.assertGreaterEqual(len(self.ev.orders), 40)

    def test_only_text_missing_from_the_file_fails(self):
        failures = {number: check for number, check in self.ev.orders.items() if not check.ok}
        self.assertEqual(failures, {
            28: OrderCheck(MISSING, "GPS"),
            29: OrderCheck(MISSING, "?"),
            34: OrderCheck(MISSING, "\U0001f4ab"),
        })

    def test_labels_of_one_column_out_of_several_are_part_of_a_line(self):
        # הקורא מדביק לשורה אחת שתי עמודות או תיבות; השורה המתויגת היא אחת מהן
        parts = sorted(number for number, check in self.ev.orders.items() if check.kind == PART_OF_LINE)
        self.assertEqual(parts, [21, 30, 31])


if __name__ == "__main__":
    unittest.main()
