"""פיצול לשורות, נרמול רווחים, מרחק תווים, והצגת תווים בלתי נראים."""

import unittest

from harness.textdiff import closest_line, levenshtein, normalize, split_lines, visible


class SplitLinesTest(unittest.TestCase):
    def test_control_chars_do_not_split_a_line(self):
        # כך יוצאת שורה מהפלאייר: GPS לא ממופה ויוצא כ-U+001D..U+001F. splitlines() היה שובר אותה לשלוש.
        page = "מאות חברות בחרו ב \x1d\x1e\x1f לעסקים\nשורה שנייה"
        self.assertEqual(split_lines(page), ["מאות חברות בחרו ב \x1d\x1e\x1f לעסקים", "שורה שנייה"])


class NormalizeTest(unittest.TestCase):
    def test_space_runs_collapse(self):
        self.assertEqual(normalize("  א  ב\u00a0\tג  "), "א ב ג")

    def test_control_chars_are_not_spaces(self):
        self.assertEqual(normalize("ב \x1d\x1e\x1f ל"), "ב \x1d\x1e\x1f ל")

    def test_space_position_still_matters(self):
        self.assertNotEqual(normalize("ומהא יתך"), normalize("ומה איתך"))


class LevenshteinTest(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(levenshtein("", ""), 0)
        self.assertEqual(levenshtein("abc", "abc"), 0)
        self.assertEqual(levenshtein("kitten", "sitting"), 3)
        self.assertEqual(levenshtein("שלום", "שלם"), 1)
        self.assertEqual(levenshtein("", "שלום"), 4)

    def test_symmetric(self):
        self.assertEqual(levenshtein("OSMentor", "MentorOS"), levenshtein("MentorOS", "OSMentor"))

    def test_limit_short_circuits(self):
        self.assertEqual(levenshtein("abcdef", "uvwxyz", limit=2), 3)
        self.assertEqual(levenshtein("abc", "abcdefgh", limit=2), 3)
        self.assertEqual(levenshtein("kitten", "sitting", limit=3), 3)


class ClosestLineTest(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(closest_line("ב  ג", ["א", "ב ג"]), (0, "ב ג"))

    def test_minimum_and_first_on_tie(self):
        self.assertEqual(closest_line("abc", ["xbc", "abx", "zzz"]), (1, "xbc"))

    def test_no_lines(self):
        self.assertEqual(closest_line("שלום", []), (4, ""))


class VisibleTest(unittest.TestCase):
    def test_control_and_format_chars_become_visible(self):
        self.assertEqual(visible("א\x1dב\u200fג\x9a"), "א⟨U+001D⟩ב⟨U+200F⟩ג⟨U+009A⟩")

    def test_regular_text_untouched(self):
        self.assertEqual(visible("שלום (Hello) — 1,234*"), "שלום (Hello) — 1,234*")


if __name__ == "__main__":
    unittest.main()
