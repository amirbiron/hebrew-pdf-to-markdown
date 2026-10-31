"""הריווח לפי הפער בעמוד (hebrew_pdf/spacing.py), על שורות בנויות.

כל שורה כאן בנויה ממחרוזת שמתארת את העמוד משמאל לימין: כל אות ברוחב 2 ובגובה H,
"|" הוא פער בין מילים בלי תו רווח בקובץ, "_" הוא תו רווח בקובץ בלי שום פער (כמו
"ומהא יתך" בפלאייר), ו-"~" הוא תו רווח בקובץ עם פער (רווח רגיל). מה שנבדק הוא התווים
שיוצאים, בסדר שבעמוד, ואילו רווחים ירדו או נוספו.
"""

import unittest

from harness.textdiff import _SPACE_RUN
from hebrew_pdf.chars import Char
from hebrew_pdf.spacing import HALF_SPACE, SpaceCounts, is_space, space_by_gaps

H = 10.0  # גובה התיבה של כל אות: חצי רווח הוא HALF_SPACE * H, כלומר 1
WIDTH = 2.0


def page_row(spec: str, word_gap: float = 3.0, tracking: float = 0.0) -> list[Char]:
    """תווים של שורה לפי התיאור (ראו למעלה). tracking: ריווח אותיות, אחרי כל אות."""
    row: list[Char] = []
    x = 0.0
    for ch in spec:
        if ch == "|":
            x += word_gap
        elif ch == "_":
            row.append(Char(" ", x, 0.0, x, x, 0.0))
        elif ch == "~":
            row.append(Char(" ", x + word_gap / 2, 0.0, x, x + word_gap, H))
            x += word_gap
        else:
            row.append(Char(ch, x + WIDTH / 2, 0.0, x, x + WIDTH, H))
            x += WIDTH + tracking
    return row


def shown(spec: str, **kwargs) -> tuple[str, SpaceCounts]:
    spaced = space_by_gaps(page_row(spec, **kwargs))
    return "".join(c.text for c in spaced.chars), spaced.counts


class FileSpacesTest(unittest.TestCase):
    def test_file_space_without_a_gap_is_dropped(self):
        self.assertEqual(shown("ab_cd"), ("abcd", SpaceCounts(in_file=1, dropped=1)))

    def test_gap_without_a_file_space_gets_a_space(self):
        self.assertEqual(shown("ab|cd"), ("ab cd", SpaceCounts(added=1)))

    def test_file_space_with_a_gap_stays(self):
        self.assertEqual(shown("ab~cd"), ("ab cd", SpaceCounts(in_file=1)))

    def test_space_on_the_wrong_side_of_a_bracket_moves(self):
        # Google Docs: תו הרווח צמוד לסוגר מצד אחד, והפער בצד השני (שורה 1)
        self.assertEqual(shown("ab_)|cd"), ("ab) cd", SpaceCounts(in_file=1, dropped=1, added=1)))

    def test_spaces_at_the_edges_are_dropped(self):
        self.assertEqual(shown("~~ab~~"), ("ab", SpaceCounts()))


class UsualGapTest(unittest.TestCase):
    def test_letter_spaced_heading(self):
        # WeasyPrint: ריווח אותיות 1.5 ותו רווח ברוחב אפס בין כל שתי אותיות (שורה 12)
        text, counts = shown("a_b_c|d_e_f", tracking=1.5)
        self.assertEqual(text, "abc def")
        self.assertEqual(counts, SpaceCounts(in_file=4, dropped=4, added=1))

    def test_line_without_two_adjacent_letters_has_no_letter_spacing(self):
        # "2 / 8": כל הפערים בין מילים. חציון של כל הפערים היה פער בין מילים, וכל הרווחים
        # היו נעלמים
        self.assertEqual(shown("8|/|2")[0], "8 / 2")
        self.assertEqual(shown("-|10|-")[0], "- 10 -")

    def test_digits_are_not_letters(self):
        # בתוך מספר הפער 0, אבל הוא לא מעיד על הפער בין אותיות
        self.assertEqual(shown("ab|1|2|3", tracking=0.0)[0], "ab 1 2 3")

    def test_lower_median_when_half_the_letter_pairs_are_word_gaps(self):
        # "We R AI": שני זוגות בתוך מילה (פער 0) ושניים בין מילים. החציון הרגיל, הממוצע
        # של 0 ו-1.8, היה מעלה את הסף ל-1.9, מעל הפער בין המילים
        self.assertEqual(shown("We|R|AI", word_gap=1.8)[0], "We R AI")

    def test_threshold_is_half_a_space_above_the_usual_gap(self):
        half = HALF_SPACE * H
        self.assertEqual(shown("ab|cd", word_gap=half * 0.9)[0], "abcd")
        self.assertEqual(shown("ab|cd", word_gap=half * 1.1)[0], "ab cd")


class GeometryTest(unittest.TestCase):
    def test_gap_is_measured_from_everything_on_the_left(self):
        # תיבה רחבה (w) שמכסה את התיבה שאחריה (i): הפער ל-c נמדד מהקצה הימני של w, 0,
        # ולא מ-i, 3
        row = [Char("x", 1.0, 0.0, 0.0, 2.0, H), Char("y", 3.0, 0.0, 2.0, 4.0, H), Char("w", 6.0, 0.0, 4.0, 10.0, H),
               Char("i", 6.5, 0.0, 6.0, 7.0, H), Char("c", 11.0, 0.0, 10.0, 12.0, H), Char("d", 13.0, 0.0, 12.0, 14.0, H)]
        self.assertEqual("".join(c.text for c in space_by_gaps(row).chars), "xywicd")

    def test_overlapping_letters_all_along_the_line(self):
        # Chrome: התיבות הרופפות של האותיות חופפות לאורך כל השורה (הפער הרגיל שלילי, נמדד
        # 0.25- מהגובה). הסף יחסי לפער הזה, ולכן הפער בין המילים עדיין נמצא
        self.assertEqual(shown("abc|def", tracking=-2.5, word_gap=2.5)[0], "abc def")

    def test_row_without_any_height_keeps_the_file_spaces(self):
        row = [Char(ch, float(x), 0.0, float(x), float(x), 0.0) for x, ch in enumerate("ab cd")]
        spaced = space_by_gaps(row)
        self.assertEqual("".join(c.text for c in spaced.chars), "ab cd")
        self.assertEqual(spaced.counts, SpaceCounts(in_file=1))


class IsSpaceTest(unittest.TestCase):
    def test_control_characters_are_not_spaces(self):
        # בפלאייר אלה אותיות שמופו בטעות (GPS, ה-? של "ומה איתך?")
        for ch in "\x1c\x1d\x1e\x1f":
            self.assertFalse(is_space(ch))

    def test_no_break_space_is_a_space(self):
        self.assertTrue(is_space(" "))

    def test_same_definition_as_the_harness(self):
        # מערך הבדיקה מגדיר רווח בעצמו (harness/textdiff.py), כדי לא לחלוק קוד עם הקורא.
        # שני העותקים חייבים להסכים על כל תו
        disagree = [hex(cp) for cp in range(0x110000)
                    if is_space(chr(cp)) != bool(_SPACE_RUN.fullmatch(chr(cp)))]
        self.assertEqual(disagree, [])


if __name__ == "__main__":
    unittest.main()
