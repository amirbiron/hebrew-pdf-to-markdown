"""הציון על הקבצים האמיתיים, המידע שנוסף לקורא בשבילו, והכיול של הספים (סבב 6).

- מה שאמור לצאת על הסט, כבדיקת שפיות (המשימה של סבב 6): הכריכה ועמוד 3 של ספר GPS נפסלים, וכך הפלאייר ושקופית
  23 במצגת; עמודים עם קטעי קוד מבודדים בקובץ הטבלאות לא בטוחים, עם הסיבה; ועוד שתי מציאות שנבדקו בעין: האימוג'י
  שיוצאים "5" ו-"¹" בשקופיות 13 ו-15, והאימוג'י ב-doc-6p_gdocs.pdf (שנעלמו עד סבב 6ב).
- בדיקת התצוגה של החבילה (score.shows_as_page) מסכימה עם זו של מערך הבדיקה (python-bidi, מימוש שלא חולק קוד).
- הכיול: הקבועים ב-hebrew_pdf/score.py הם מה שהכיול בוחר היום, וכל צורת השחתה נתפסת.
"""

import dataclasses
import unittest
from collections import Counter

from harness.display_check import displays_like_page
from harness.reader import read_pages
from harness.run import DEFAULT_LABELS, DEFAULT_PDFS, DEFAULT_TRUTH, evaluate
from harness import calibration
from hebrew_pdf import score
from hebrew_pdf.markdown import build_markdown


def scores_of(name: str) -> tuple[list, list[score.PageScore]]:
    pages = read_pages(DEFAULT_PDFS / name)
    return pages, score.score_document(pages, build_markdown(pages).dropped)


def kinds(page_score: score.PageScore) -> list[str]:
    return [reason.kind for reason in page_score.reasons]


class ExpectedOutcomesTest(unittest.TestCase):
    def test_pages_without_text(self):
        _, scores = scores_of("gps-book_indesign.pdf")
        self.assertEqual([(i, s.decision) for i, s in enumerate(scores, 1) if s.decision == score.REJECTED],
                         [(1, score.REJECTED), (3, score.REJECTED)])
        self.assertEqual(kinds(scores[0]), ["no_text"])

    def test_control_chars_in_the_flyer(self):
        _, scores = scores_of("marketing-flyer_illustrator.pdf")
        self.assertEqual(scores[0].decision, score.REJECTED)
        # GPS (U+001D עד U+001F) פעמיים, וסימן השאלה של "ומה איתך?" (U+001C)
        self.assertEqual(scores[0].reasons[0].text, "7 תווים שלא ממופים בקובץ: במקום האות שבעמוד יוצא תו אחר")

    def test_emoji_without_unicode_in_the_presentation(self):
        pages, scores = scores_of("presentation_canva.pdf")
        rejected = [i for i, s in enumerate(scores, 1) if s.decision == score.REJECTED]
        self.assertEqual(rejected, [13, 15, 23])
        # שקופית 13: האימוג'י יוצא "5", תו רגיל לגמרי, ורק PDFium יודע שאין לו ערך Unicode
        self.assertEqual((pages[12].marked_unmapped, pages[14].marked_unmapped, pages[22].marked_unmapped), (1, 1, 0))

    def test_emoji_that_pdfium_keeps_as_two_halves(self):
        # עד סבב 6ב הקורא דילג על שני החצאים של כל אימוג'י (chars.characters), וכל ששת העמודים יצאו "לא בטוח" כי
        # 26 אימוג'י חסרו בפלט. עכשיו הם בפלט, ונשאר רק עמוד 4, עם השורה שלא מוצגת כמו העמוד
        _, scores = scores_of("doc-6p_gdocs.pdf")
        self.assertEqual([s.decision for s in scores], [score.OK] * 3 + [score.UNSURE] + [score.OK] * 2)
        self.assertEqual(kinds(scores[3]), ["display"])

    def test_isolated_code_in_the_table_file(self):
        _, scores = scores_of("env-vars_weasyprint.pdf")
        with_display = [i for i, s in enumerate(scores, 1) if "display" in kinds(s)]
        self.assertEqual(len(with_display), 12)
        self.assertTrue(all(scores[i - 1].decision == score.UNSURE for i in with_display))

    def test_brackets_the_drawing_reversed(self):
        # Canva שומר בכל סוגר את התו של הצורה המצוירת: בשקופית 7 כל 18 הסוגריים הפוכים לתו שבקובץ
        pages, _ = scores_of("presentation_canva.pdf")
        self.assertEqual((pages[6].brackets_changed, pages[6].brackets), (18, 18))
        # WeasyPrint שומר את התו הלוגי, והצורה בעמוד ברמה מימין לשמאל הפוכה לו: רק 5 מתוך 166 שונים מהקובץ. השוואה
        # לצורה המצוירת במקום לתו שבקובץ הייתה סופרת כאן כמעט את כולם
        pages, _ = scores_of("spec_weasyprint.pdf")
        self.assertEqual((sum(p.brackets_changed for p in pages), sum(p.brackets for p in pages)), (5, 166))


class DisplayCheckAgreesTest(unittest.TestCase):
    """score.shows_as_page (logical_order.drawn) מול harness.display_check (python-bidi): אותה תשובה בכל שורה.
    הבדל אחד מכוון: python-bidi לא משקף סוגריים (L4), והחבילה כן, ולכן החבילה מחמירה ממנו. בסט אין שורה שבה זה
    משנה (נמדד בסבב 6: 0 שורות)."""

    def test_every_line_of_three_files(self):
        for name in ("env-vars_weasyprint.pdf", "spec_chrome.pdf", "doc-6p_gdocs.pdf"):
            with self.subTest(name=name):
                lines = [line for page in read_pages(DEFAULT_PDFS / name) for line in page.lines
                         if line.visual.strip(" ")]
                package = [all(score.shows_as_page(part) for part in line.parts if part.visual.strip(" "))
                           for line in lines]
                self.assertEqual(package, [displays_like_page(line) for line in lines])
                self.assertIn(False, package)  # יש שורות שנכשלות, כך שההסכמה אינה רק על "עובר"


    def test_emoji_in_a_hebrew_line(self):
        # כל רכיב עם אימוג'י ב-doc-6p_gdocs.pdf מוצג כמו העמוד בשתי הבדיקות, ואימוג'י שזז לקצה השני של הרכיב
        # נתפס בשתיהן: הבדיקה מסוגלת להיכשל על אימוג'י, ולא רק לעבור
        parts = [(line, part) for page in read_pages(DEFAULT_PDFS / "doc-6p_gdocs.pdf") for line in page.lines
                 for part in line.parts if any(ord(char) > 0xFFFF for char in part.text)]
        self.assertEqual(len(parts), 26)
        for line, part in parts:
            self.assertTrue(score.shows_as_page(part))
            self.assertTrue(displays_like_page(dataclasses.replace(line, components=(part,))))
            emoji = next(char for char in part.text if ord(char) > 0xFFFF)
            moved = dataclasses.replace(part, text=part.text.replace(emoji, "", 1).strip(" ") + " " + emoji)
            self.assertFalse(score.shows_as_page(moved))
            self.assertFalse(displays_like_page(dataclasses.replace(line, components=(moved,))))


class CalibrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = evaluate(DEFAULT_PDFS, DEFAULT_LABELS, truth_dir=DEFAULT_TRUTH)
        cls.cal = cls.ev.calibration

    def test_the_constants_are_what_the_calibration_chooses(self):
        # כשהקורא משתנה והכיול זז, הטסט הזה נופל, ולא הדוח לבדו
        self.assertAlmostEqual(score.MIN_PLAUSIBLE, self.cal.plausible_choice.middle, delta=0.0005)
        self.assertAlmostEqual(score.MAX_EFFORT, self.cal.effort_choice.middle, delta=0.0005)
        self.assertGreaterEqual(self.cal.plausible_choice.low, self.cal.required_plausible)

    def test_every_form_is_caught(self):
        rows = {(form, intensity): (count, hits) for form, intensity, count, hits in calibration.catch_table(self.cal)}
        for (form, intensity), (count, hits) in rows.items():
            with self.subTest(form=form, intensity=intensity):
                self.assertGreater(count, 0)
                self.assertEqual(hits["כלשהו"], count)
        for form in ("reverse_line", "reverse_ltr", "reverse_letters", "reverse_words", "punct_to_start", "glue"):
            for intensity in ("one", "all"):
                count, hits = rows[(form, intensity)]
                self.assertEqual(hits["תצוגה"], count, (form, intensity))
        self.assertEqual(rows[("drop", "one")][1]["שלמות"], rows[("drop", "one")][0])
        self.assertEqual(rows[("control", "one")][1]["נפסל"], rows[("control", "one")][0])
        for form in calibration.SIGNAL_TARGETS:
            count, hits = rows[(form, "all")]
            self.assertGreaterEqual(hits["סימנים"], calibration.CATCH_SHARE * count, form)

    def test_complete_everywhere(self):
        # עד סבב 6ב: כל ששת העמודים של doc-6p_gdocs.pdf, בגלל האימוג'י שהקורא דילג עליהם
        incomplete = {name: [i for i, s in enumerate(scores, 1) if {"missing", "extra"} & set(kinds(s))]
                      for name, scores in self.ev.scores.items()}
        self.assertEqual({name: pages for name, pages in incomplete.items() if pages}, {})

    def test_most_pages_are_ok(self):
        decisions = Counter(s.decision for scores in self.ev.scores.values() for s in scores)
        self.assertGreater(decisions[score.OK], 0.75 * sum(decisions.values()))


if __name__ == "__main__":
    unittest.main()
