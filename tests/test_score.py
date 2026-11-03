"""הציון של עמוד (hebrew_pdf/score.py): כל רכיב בנפרד, על קלט שנבנה כאן.

הבדיקות על הקבצים האמיתיים, ועל הכיול, ב-tests/test_score_files.py.
"""

import ctypes
import io
import math
import unittest

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

from hebrew_pdf import score
from hebrew_pdf.chars import _from_codes, is_rotated, unmapped_char
from hebrew_pdf.lines import Component, Line, PageText, read_document
from hebrew_pdf.logical_order import drawn
from hebrew_pdf.spacing import SpaceCounts


def part(text: str, ambiguous: bool = False) -> Component:
    """רכיב שהטקסט שלו נכון: מה שבעמוד הוא בדיוק התצוגה שלו (logical_order.drawn)."""
    return Component(text, "".join(drawn(list(text))[1]), True, ambiguous)


def page(*parts: Component, reference: str | None = None, **fields) -> PageText:
    """עמוד ששורה לכל רכיב. reference: כל התווים של העמוד לפי PDFium; ברירת המחדל: בדיוק התווים של הפלט."""
    lines = [Line(p.text, p.visual, True, p.ambiguous, components=(p,)) for p in parts]
    if reference is None:
        reference = "".join(p.text for p in parts)
    return PageText(lines, 0, reference=reference, **fields)


LONG = "זה משפט ארוך בעברית שנכתב כדי שיהיו בעמוד מספיק מילים לבדיקה"  # 12 מילים


class WilsonTest(unittest.TestCase):
    def test_the_examples_of_the_spec(self):
        # מסמך האפיון, "הציון והסימון": 9 מתוך 9 בערך 0.70, ו-200 מתוך 200 בערך 0.98
        self.assertAlmostEqual(score.wilson_lower(9, 9), 0.70, places=2)
        self.assertAlmostEqual(score.wilson_lower(200, 200), 0.98, places=2)

    def test_more_evidence_more_confidence(self):
        self.assertLess(score.wilson_lower(9, 10), score.wilson_lower(90, 100))

    def test_no_evidence_is_no_confidence(self):
        self.assertEqual(score.wilson_lower(0, 0), 0.0)

    def test_an_impossible_share_is_an_error(self):
        for successes, total in ((5, 3), (-1, 3), (0, -1)):
            with self.subTest(successes=successes, total=total), self.assertRaises(ValueError):
                score.wilson_lower(successes, total)


class FinalLettersTest(unittest.TestCase):
    def test_reversed_words(self):
        for word in ("תוריכממ", "םולש", "בינייםלא"):
            with self.subTest(word=word):
                self.assertTrue(score.final_letter_anomaly(word))

    def test_correct_words_acronyms_and_loanwords(self):
        for word in ("ממכירות", "שלום", 'בע"מ', 'סה"כ', "מע״מ", "וואטסאפ", "טיפ", "צ'אט", "ם"):
            with self.subTest(word=word):
                self.assertFalse(score.final_letter_anomaly(word))


class ReversedNumbersTest(unittest.TestCase):
    def test_reversed(self):
        for text in ("65.432,1", "543,21", "5202", "שנת 6202"):
            with self.subTest(text=text):
                self.assertEqual(score.reversed_numbers(text), 1)

    def test_not_reversed(self):
        # מספרים מעוצבים, שנים, רשימות, כתובות IP ומזהה שלילי: כולם מהסט
        for text in ("1,234.56", "12,345", "2025", "10,8,6,4", "127.0.0.1,10.0.0.1", "-1001,-1002", "3.12"):
            with self.subTest(text=text):
                self.assertEqual(score.reversed_numbers(text), 0)


class UnpairedBracketsTest(unittest.TestCase):
    def test_a_pair_across_two_lines(self):
        self.assertEqual(score.unpaired_brackets(["(זה נפתח", "ונסגר כאן)"]), 0)

    def test_the_google_docs_line_that_passes_the_display_check(self):
        # מסמך האפיון, "נשארו": "מאפס( ₪3.60 :(DALL-E 3 API" עובר את בדיקת התצוגה אבל שגוי במשמעות
        self.assertEqual(score.unpaired_brackets(["● 30 תמונות מאפס (₪3.60 :(DALL-E 3 API"]), 1)

    def test_a_reversed_pair(self):
        self.assertEqual(score.unpaired_brackets([")א("]), 2)

    def test_list_markers_and_smileys_are_not_brackets(self):
        self.assertEqual(score.unpaired_brackets(["1) פריט ראשון", "א) פריט", "וואו, ישר ולעניין :)"]), 0)


class ShowsAsPageTest(unittest.TestCase):
    def test_correct_and_reversed(self):
        good = part("שורה עם Python 3.12 בתוכה (ו-API)")
        self.assertTrue(score.shows_as_page(good))
        self.assertFalse(score.shows_as_page(Component(good.text[::-1], good.visual, True)))

    def test_bracket_direction_is_checked(self):
        good = part("טקסט (בסוגריים) כאן")
        flipped = good.text.replace("(", "#").replace(")", "(").replace("#", ")")
        self.assertFalse(score.shows_as_page(Component(flipped, good.visual, True)))

    def test_a_left_to_right_component_shows_as_it_is(self):
        self.assertTrue(score.shows_as_page(Component("https://example.com/", "https://example.com/", False)))


class PageScoreTest(unittest.TestCase):
    def test_a_decision_needs_a_reason(self):
        reason = score.Reason("display", "שורה אחת שלא מוצגת כמו העמוד")
        with self.assertRaises(ValueError):
            score.PageScore(score.UNSURE, ())
        with self.assertRaises(ValueError):
            score.PageScore(score.OK, (reason,))
        with self.assertRaises(ValueError):
            score.PageScore(score.REJECTED, (reason,))  # סיבה שאינה סיבה לפסילה
        with self.assertRaises(ValueError):
            score.Reason("no_such_kind", "")

    def test_a_clean_long_page_is_ok(self):
        result = score.score_page(page(part(LONG), part(LONG)))
        self.assertEqual((result.decision, result.reasons), (score.OK, ()))


class RejectionTest(unittest.TestCase):
    def test_a_page_without_text(self):
        result = score.score_page(PageText([], 0, reference=""))
        self.assertEqual(result.decision, score.REJECTED)
        self.assertEqual([r.kind for r in result.reasons], ["no_text"])

    def test_a_control_char_in_the_text(self):
        # GPS בפלאייר: U+001D עד U+001F במקום האותיות
        result = score.score_page(page(part(LONG + " \x1d\x1e\x1f")))
        self.assertEqual(result.decision, score.REJECTED)
        self.assertEqual([r.kind for r in result.reasons], ["unmapped"])
        self.assertIn("3 תווים", result.reasons[0].text)

    def test_a_char_pdfium_marks_as_unmapped(self):
        # האימוג'י שיוצא "5" במצגת: תו רגיל, ש-PDFium מסמן כחסר ערך Unicode
        result = score.score_page(page(part(LONG), marked_unmapped=1))
        self.assertEqual(result.decision, score.REJECTED)
        self.assertEqual([r.kind for r in result.reasons], ["unmapped"])

    def test_rotated_text(self):
        result = score.score_page(page(part(LONG), rotated_chars=4))
        self.assertEqual([r.kind for r in result.reasons], ["rotated"])

    def test_which_chars_are_unmapped(self):
        for char in ("\x00", "\x1c", "\x7f", "\x9a", "", "\U000f0000", "�"):
            with self.subTest(char=f"U+{ord(char):04X}"):
                self.assertTrue(unmapped_char(char))
        for char in ("\t", "\n", "\r", "א", "A", "5", "¹", " "):
            with self.subTest(char=f"U+{ord(char):04X}"):
                self.assertFalse(unmapped_char(char))


class PlausibilityTest(unittest.TestCase):
    def test_a_line_that_does_not_show_as_the_page(self):
        good = part(LONG)
        clean = [part(LONG)] * 10  # מספיק מילים, כך שהאותיות הסופיות של השורה ההפוכה לא מפילות את הסבירות
        result = score.score_page(page(Component(LONG[::-1], good.visual, True), *clean, reference=LONG * 11))
        self.assertEqual(result.decision, score.UNSURE)
        self.assertEqual([r.kind for r in result.reasons], ["display"])
        self.assertEqual(result.reasons[0].text, "שורה אחת שלא מוצגת כמו העמוד")

    def test_a_short_page_is_not_a_safe_page(self):
        result = score.score_page(page(part("כותרת קצרה")))
        self.assertEqual(result.decision, score.UNSURE)
        self.assertEqual([r.kind for r in result.reasons], ["short"])
        self.assertIn("2 מילים", result.reasons[0].text)

    def test_the_same_signal_on_a_short_and_a_long_page(self):
        signal = part("1 Onboarding", ambiguous=True)
        short = score.score_page(page(signal, part("כמה מילים בעברית כאן")))
        long = score.score_page(page(signal, *[part(LONG)] * 20))
        self.assertEqual([r.kind for r in short.reasons], ["ambiguous"])
        self.assertIn("בעמוד של 6 מילים", short.reasons[0].text)
        self.assertEqual(long.decision, score.OK)

    def test_what_was_dropped_from_the_markdown_is_not_checked(self):
        # כמו שורת התחתית של המצגת: דו-משמעית, וחוזרת בכל שקופית, ולכן יורדת מה-Markdown
        # סף מפורש: הבדיקה היא על מה שנספר, ולא על הערך של MIN_PLAUSIBLE
        footer = part("OOHMYWEB.COM | 058-7999120", ambiguous=True)
        body = [part("כמה מילים בעברית כאן")] * 3
        kept = score.score_page(page(footer, *body), min_plausible=0.7)
        dropped = score.score_page(page(footer, *body), dropped={(0, 0)}, min_plausible=0.7)
        self.assertIn("ambiguous", [r.kind for r in kept.reasons])
        self.assertEqual(dropped.decision, score.OK)


class CompletenessTest(unittest.TestCase):
    def test_a_missing_and_an_extra_char(self):
        missing = score.score_page(page(part(LONG), part(LONG), reference=LONG * 2 + "א"))
        extra = score.score_page(page(part(LONG), part(LONG + "ב"), reference=LONG * 2))
        self.assertEqual([r.kind for r in missing.reasons], ["missing"])
        self.assertEqual([r.kind for r in extra.reasons], ["extra"])

    def test_a_dot_the_reader_lost(self):
        # PR א׳: נקודה ש"3." איבד אצל הקורא עצמו. בדיקת השלמות של ה-Markdown לא רואה אותה, וזו כן
        line = "3 חדר החלטות (Decision Room) " + LONG
        result = score.score_page(page(part(line), part(LONG), reference=line.replace("3 ", "3. ", 1) + LONG))
        self.assertEqual(result.reasons[0].text, "תו אחד שבעמוד חסר בפלט")

    def test_an_emoji_the_text_api_dropped(self):
        result = score.score_page(page(part(LONG), part(LONG), reference=LONG * 2 + "\U0001F4CC"))
        self.assertEqual(result.reasons[0].text, "תו אחד שבעמוד חסר בפלט (אימוג'י)")

    def test_bracket_direction_and_quote_mirroring_are_not_missing_chars(self):
        text = LONG + " (כאן) “ציטוט”"
        mirrored = LONG + " )כאן( ”ציטוט“"
        self.assertEqual(score.score_page(page(part(text), part(LONG), reference=mirrored + LONG)).decision, score.OK)

    def test_both_chars_of_a_pair_are_counted(self):
        # עד שזה תוקן, מונה שנבנה מחדש כמילון החזיק רק אחד משני התווים של זוג, וההשוואה נכשלה בכל עמוד שבו מספר
        # הפותחים שונה ממספר הסוגרים (למשל "1)" ברשימה)
        self.assertEqual(score._folded("1) א 2) ב (ג)"), score._folded("1( א 2( ב )ג("))
        self.assertEqual(score._folded("()(")["("], 3)
        # עמוד של רשימה: "1)" בתחילת שורה, ולכן יותר סוגרים מפותחים, ו-PDFium משקף אותם
        parts = [part("1) " + LONG), part("2) " + LONG), part(LONG + " (כאן)")]
        mirrored = "".join(p.text for p in parts).translate(str.maketrans("()", ")("))
        self.assertEqual(score.score_page(page(*parts, reference=mirrored)).decision, score.OK)

    def test_no_reference_is_an_error_and_not_a_pass(self):
        with self.assertRaises(ValueError):
            score.score_page(PageText([Line(LONG, LONG[::-1], True)], 0))


class EffortTest(unittest.TestCase):
    def test_many_corrections(self):
        heavy = SpaceCounts(in_file=100, dropped=20, added=10)
        result = score.score_page(_with_spacing(heavy))
        self.assertEqual([r.kind for r in result.reasons], ["effort"])
        self.assertIn("30 מתוך 110", result.reasons[0].text)

    def test_a_short_page_without_corrections_is_not_heavy(self):
        result = score.score_page(_with_spacing(SpaceCounts(in_file=3)))
        self.assertTrue(result.effort.ok(score.MAX_EFFORT))


def _with_spacing(counts: SpaceCounts) -> PageText:
    parts = [part(LONG)] * 20
    lines = [Line(p.text, p.visual, True, components=(p,)) for p in parts]
    lines[0] = Line(parts[0].text, parts[0].visual, True, spacing=counts, components=(parts[0],))
    return PageText(lines, 0, reference="".join(p.text for p in parts))


class ReferenceTest(unittest.TestCase):
    def test_an_emoji_is_one_char_in_either_order(self):
        # PDFium הופך את הסדר של שני החצאים כשהוא הופך רצף מימין לשמאל (נמדד ב-doc-6p_gdocs.pdf)
        self.assertEqual(_from_codes([0xD83D, 0xDCCC]), "\U0001F4CC")
        self.assertEqual(_from_codes([0xDCCC, 0xD83D]), "\U0001F4CC")
        self.assertEqual(_from_codes([0x5D0, 0xDCCC, 0xD83D, 0x5D1]), "א\U0001F4CCב")

    def test_a_lone_half_and_an_impossible_code(self):
        self.assertEqual(_from_codes([0xD83D]), "\ud83d")
        self.assertEqual(_from_codes([0x110000]), "�")


class RotationTest(unittest.TestCase):
    @staticmethod
    def matrix(a, b, c, d):
        m = pdfium_raw.FS_MATRIX()
        m.a, m.b, m.c, m.d = a, b, c, d
        return m

    def test_rotation_and_not_slant(self):
        cos, sin = math.cos(math.radians(3)), math.sin(math.radians(3))
        self.assertTrue(is_rotated(self.matrix(cos, sin, -sin, cos)))  # 3 מעלות
        self.assertTrue(is_rotated(self.matrix(-1, 0, 0, -1)))  # 180 מעלות
        self.assertTrue(is_rotated(self.matrix(0, 1, -1, 0)))  # 90 מעלות
        # אות נטויה מלאכותית של Chrome: c=0.19 ו-b=0. FPDFText_GetCharAngle (atan2(c, a)) הייתה סופרת אותה מסובבת
        self.assertFalse(is_rotated(self.matrix(12, 0, 0.19 * 12, 12)))
        self.assertFalse(is_rotated(self.matrix(12, 0, 0, 12)))

    @staticmethod
    def pdf_with_text(angle: float) -> bytes:
        """PDF עם שתי שורות טקסט, מסובבות ב-angle מעלות (FPDFPageObj_NewTextObj, FPDFText_SetText: public/fpdf_edit.h)."""
        pdf = pdfium.PdfDocument.new()
        page = pdf.new_page(400, 400)
        for text, y in (("Rotated text here", 200), ("Second line", 100)):
            raw = pdfium_raw.FPDFPageObj_NewTextObj(pdf, b"Helvetica", 12.0)
            data = (text + "\0").encode("utf-16-le")
            buffer = ctypes.create_string_buffer(data, len(data))
            if not pdfium_raw.FPDFText_SetText(raw, ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort))):
                raise RuntimeError("FPDFText_SetText failed")
            obj = pdfium.PdfObject(raw, pdf=pdf)
            page.insert_obj(obj)
            obj.transform(pdfium.PdfMatrix().rotate(angle).translate(100, y))
        page.gen_content()
        out = io.BytesIO()
        pdf.save(out)
        return out.getvalue()

    def test_a_rotated_page_through_the_reader(self):
        for angle, rotated in ((0, False), (3, True), (90, True), (180, True)):
            with self.subTest(angle=angle), pdfium.PdfDocument(self.pdf_with_text(angle)) as pdf:
                pages = read_document(pdf)
                result = score.score_page(pages[0])
                self.assertEqual(pages[0].rotated_chars > 0, rotated)
                self.assertEqual(result.decision == score.REJECTED, rotated)
                if angle == 180:
                    # מה שהקורא מוציא מטקסט מסובב: הסיבה שהעמוד נפסל ולא מקבל ציון
                    self.assertEqual(pages[0].lines[0].text, "ereh txet detatoR")


if __name__ == "__main__":
    unittest.main()
