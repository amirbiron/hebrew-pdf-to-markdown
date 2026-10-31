"""הסדר הלוגי של שורה, מהאותיות שלה לפי מיקומן בעמוד (hebrew_pdf/logical_order.py).

הקלט של כל בדיקה נבנה מהתצוגה של הטקסט הנכון: python-bidi (מימוש עצמאי של UAX #9)
מציג את הטקסט הלוגי בפסקה עברית, והתוצאה, משמאל לימין, היא השורה "בעמוד". הקורא
צריך להחזיר ממנה את הטקסט הלוגי. python-bidi לא משקף סוגריים (כלל L4), ובעמוד
סוגר הוא הצורה המצוירת, ולכן סוגר ברמה אי-זוגית מתהפך לפי הרמות של הקורא; הסדר
עצמו נבדק מול python-bidi בכל בנייה. המקרים בנויים לפי השורות המתויגות שנכשלו
באב-טיפוס (המספרים בהערות הם מספרי השורות ב-testset/labels.md), ולפי מקרים מכל
הסט שבדיקת התצוגה מצאה.
"""

import unittest

from bidi import get_display

from hebrew_pdf.chars import Char
from hebrew_pdf.lines import Line, build_line
from hebrew_pdf.logical_order import drawn as drawn_texts


def drawn(logical: str) -> str:
    """השורה כמו שהיא מצוירת בעמוד, משמאל לימין: הסדר של אלגוריתם התצוגה, וסוגר
    ברמה מימין לשמאל בצורה ההפוכה (L4). הסדר נבדק כאן מול python-bidi."""
    order, texts = drawn_texts(list(logical))
    assert "".join(logical[i] for i in order) == get_display(logical, base_dir="R")
    return "".join(texts)


def page_line(logical: str) -> Line:
    """השורה כמו שהקורא היה רואה אותה בעמוד: כל תו במקום שלו, משמאל לימין."""
    return build_line([Char(ch, float(x), 0.0) for x, ch in enumerate(drawn(logical))])


class MixedRunsTest(unittest.TestCase):
    def assert_round_trip(self, logical: str):
        line = page_line(logical)
        self.assertEqual(line.text, logical)
        return line

    def test_english_list_with_commas(self):  # שורה 18
        self.assert_round_trip("תקלות שמקורן בצד שלישי (Meta, Telegram, Google, ספקי תשתית), שאינן בשליטת החברה.")

    def test_comma_between_english_names(self):  # שורה 19
        self.assert_round_trip("כל מה שצריך להכין לפני שמתחילים — Meta, Google Drive ו-Sheets")

    def test_arrow_between_english_phrases(self):  # שורה 20
        self.assert_round_trip("IG_USER_ID — נמצא ב-Business Settings ← Instagram Accounts.")

    def test_period_after_english_at_end_of_sentence(self):  # שורה 6
        self.assert_round_trip("שומר את ה-Access Token המאובטח ב-Supabase DB.")

    def test_percent_sign_stays_with_its_number(self):  # שורה 27
        self.assert_round_trip("אנו מתגאים במעל 90% הצלחה")

    def test_plus_between_english_words_and_version(self):  # שורה 11, תא אחד
        self.assert_round_trip("חבילת FastAPI + Python 3.12 בצד השרת")

    def test_number_that_opens_a_bracket_is_not_glued_to_english_on_its_left(self):
        # doc-2p עמוד 1: בקריאה משמאל לימין ה-360 נצמד ל-credentials. רק הבדיקה של
        # זוגות הסוגריים (N0) מראה שהקריאה הזו לא מוצגת כמו העמוד
        self.assert_round_trip("ספק וואטסאפ (360dialog / Twilio) — credentials.")

    def test_list_number_before_english_heading(self):
        # בתוכן העניינים של mentoros: "Onboarding .1" מוצג זהה, והטיפוגרפיה מכריעה
        self.assert_round_trip("1. Onboarding אישי")

    def test_label_and_value_after_colon(self):
        # doc-6p עמוד 2: "₪0.20 :Database" מוצג זהה, והטיפוגרפיה מכריעה
        self.assert_round_trip("30 העלאות תמונות ואחסון ב-Database: ₪0.20")

    def test_version_after_english_name_inside_hebrew(self):
        line = self.assert_round_trip("השתמשנו ב-Python 3.12 לפרויקט")
        # "ב-3.12 Python" מוצג זהה; ברירת המחדל הכריעה, והשורה מסומנת
        self.assertTrue(line.ambiguous)

    def test_plain_hebrew_line_is_not_ambiguous(self):
        line = self.assert_round_trip("הופקה ב-11/05/2026 · בתוקף עד 25/05/2026")
        self.assertFalse(line.ambiguous)


class BracketsTest(unittest.TestCase):
    """סוגר בעמוד הוא הצורה המצוירת; הקורא מחזיר את התו הלוגי (ההיפוך של L4)."""

    def assert_round_trip(self, logical: str):
        line = page_line(logical)
        self.assertEqual(line.text, logical)
        return line

    def test_hebrew_in_brackets(self):  # שורה 26
        self.assert_round_trip("אנו חברה לניהול עסקים פרטיים (קטנים ובינוניים). מתמחים באבחון,")

    def test_number_in_brackets(self):  # שורה 37, בלי בעיית הרווח
        self.assert_round_trip("רב בריח (08) תעשיות בע\"מ")

    def test_english_in_brackets_before_question_mark(self):  # שורה 24
        self.assert_round_trip("או בעלות בחברה (equity)? ההבדל עצום")

    def test_opening_bracket_whose_pair_is_on_another_line(self):  # שורה 3
        self.assert_round_trip("(לדוגמה: סינון לידים, קביעת פגישות, תמיכה טכנית,")

    def test_negative_numbers_in_a_row(self):  # שורה 39, בלי גבולות התאים
        self.assert_round_trip("הוצאות (הכנסות) אחרות (189) (5,203) (139) 18 (9,995)*")

    def test_nested_brackets(self):
        self.assert_round_trip("ראו [נספח (ב) בסוף] לפני החתימה")

    def test_english_in_brackets_after_english_word_is_ambiguous(self):
        # "Meta (OAuth)" ו-"(OAuth) Meta" מוצגים זהה; ברירת המחדל: הסוגריים עם האנגלית שמשמאלם
        self.assertEqual(drawn("אבג Meta (OAuth) דהו"), drawn("אבג (OAuth) Meta דהו"))
        line = self.assert_round_trip("אבג Meta (OAuth) דהו")
        self.assertTrue(line.ambiguous)


class AmbiguousReadingTest(unittest.TestCase):
    def test_both_readings_of_a_badge_number_look_the_same(self):
        # שורה 9: "1 Onboarding" ו-"Onboarding 1" מוצגים זהה לגמרי
        self.assertEqual(get_display("1 Onboarding אישי", base_dir="R"),
                         get_display("Onboarding 1 אישי", base_dir="R"))
        line = page_line("1 Onboarding אישי")
        self.assertTrue(line.ambiguous)
        # ברירת המחדל: המספר שייך למילה האנגלית שמשמאלו
        self.assertEqual(line.text, "Onboarding 1 אישי")


class LineEdgesTest(unittest.TestCase):
    def test_control_character_at_the_edge_is_kept(self):
        # בפלאייר ה-? של "ומה איתך?" ממופה ל-U+001C, שנמצא בקצה השמאלי של השורה.
        # str.strip() מחשיב אותו רווח ומחק אותו; אות שנמחקת בשקט היא כשל שלמות.
        visual = "\x1c" + get_display("ומה איתך", base_dir="R")
        line = build_line([Char(ch, float(x), 0.0) for x, ch in enumerate(visual)])
        self.assertIn("\x1c", line.text)

    def test_spaces_at_the_edges_are_removed(self):
        line = build_line([Char(ch, float(x), 0.0) for x, ch in enumerate("  םולש  ")])
        self.assertEqual(line.text, "שלום")


class LeftToRightLineTest(unittest.TestCase):
    def test_line_without_hebrew_keeps_page_order(self):
        # כיוון של שורה בלי עברית הוא החלטה פתוחה במסמך האפיון; כאן משמאל לימין
        row = [Char(ch, float(x), 0.0) for x, ch in enumerate("/https://example.com")]
        self.assertEqual(build_line(row).text, "/https://example.com")


if __name__ == "__main__":
    unittest.main()
