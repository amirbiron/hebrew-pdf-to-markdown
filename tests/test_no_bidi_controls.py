"""אין תווי BiDi בלתי נראים בקבצי הקוד.

הם נכנסים בהעתקה של עברית מדפדפן או מצ'אט, לא נראים בשום עורך, ומפילים את bandit
(B613) ואת ruff (PLE2502). התווים כתובים כאן כ-escape, אחרת הבדיקה הייתה נכשלת על עצמה.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIDI = ("\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2066", "\u2067", "\u2068", "\u2069")
SOURCE_DIRS = ("hebrew_pdf", "prototype", "harness", "tests", "tools")


class NoBidiControlsTest(unittest.TestCase):
    def test_python_sources(self):
        files = [p for d in SOURCE_DIRS for p in sorted((ROOT / d).rglob("*.py"))]
        self.assertTrue(files)
        for path in files:
            text = path.read_text(encoding="utf-8")
            for char in BIDI:
                self.assertNotIn(char, text, f"{path.relative_to(ROOT)}: תו BiDi U+{ord(char):04X}")


if __name__ == "__main__":
    unittest.main()
