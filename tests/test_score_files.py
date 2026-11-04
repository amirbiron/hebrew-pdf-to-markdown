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
from harness.run import DEFAULT_LABELS, DEFAULT_PDFS, DEFAULT_TRUTH, _plausible_how, evaluate
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
        # הערך מעל הדרישה (calibration.chosen_range): הסימנים לבדם תופסים 95% מהעמודים ההפוכים
        self.assertGreater(score.MIN_PLAUSIBLE, self.cal.required_plausible)

    def test_every_form_is_caught(self):
        rows = {(form, intensity): (count, hits) for form, intensity, count, hits in calibration.catch_table(self.cal)}
        for (form, intensity), (count, hits) in rows.items():
            if form in calibration.BLIND:
                continue
            with self.subTest(form=form, intensity=intensity):
                self.assertGreater(count, 0)
                self.assertEqual(hits["היום"], count)
        for form in ("reverse_line", "reverse_ltr", "reverse_letters", "reverse_words", "punct_to_start", "glue"):
            for intensity in ("one", "all"):
                count, hits = rows[(form, intensity)]
                self.assertEqual(hits["תצוגה"], count, (form, intensity))
        self.assertEqual(rows[("drop", "one")][1]["שלמות"], rows[("drop", "one")][0])
        self.assertEqual(rows[("control", "one")][1]["נפסל"], rows[("control", "one")][0])
        for form in calibration.SIGNAL_TARGETS:
            count, hits = rows[(form, "all")]
            self.assertGreaterEqual(hits["סימנים"], calibration.CATCH_SHARE * count, form)

    def test_the_blind_forms_are_blind(self):
        # הצורות של סבב 6ב נמדדות (יש עמודים שהן חלות עליהם), ובדיקת התצוגה והשלמות לא רואות אף אחת מהן: זה מה
        # שהן אמורות למדוד. מה שהציון כן תופס מהן (סימנים, תאים מספריים) מופיע בדוח
        rows = {(form, intensity): (count, hits) for form, intensity, count, hits in calibration.catch_table(self.cal)}
        for form in calibration.BLIND:
            for intensity in ("one", "all"):
                count, hits = rows[(form, intensity)]
                with self.subTest(form=form, intensity=intensity):
                    self.assertGreater(count, 0)
                    self.assertEqual((hits["תצוגה"], hits["שלמות"], hits["נפסל"]), (0, 0, 0))

    def test_the_reader_has_no_near_threshold_count(self):
        # סבב 6ב: הספירה של החלטות קרובות לסף נמדדה, לא הבדילה בין עמודים שגויים לנכונים, וירדה מהקורא
        page = read_pages(DEFAULT_PDFS / "optimization_chrome.pdf")[0]
        self.assertFalse(hasattr(page, "near_decisions"))
        self.assertFalse(hasattr(page.lines[0], "near_spaces"))

    def test_the_new_evidence_marks_no_page_known_to_be_correct(self):
        for rule in calibration.NEW:
            self.assertEqual(self.cal.known_good_flagged[rule], 0, rule)

    def test_crowded_cells_in_the_financial_report(self):
        # כל אחד מ-11 התאים נבדק בגיאומטריה: שני מספרים מרכיבים נפרדים באותה שורה בעמוד, או משתי שורות שונות
        pages = self.ev.scores["financial-report-q2-2025_aspose.pdf"]
        flagged = [i for i, s in enumerate(pages, 1) if "crowded_cells" in kinds(s)]
        self.assertEqual(flagged, [13, 39, 40, 41, 46, 47, 63])
        self.assertEqual(sum(s.plausibility.crowded_cells for s in pages if s.plausibility), 11)
        others = {name: [i for i, s in enumerate(scores, 1) if {"crowded_cells", "digit_groups"} & set(kinds(s))]
                  for name, scores in self.ev.scores.items() if name != "financial-report-q2-2025_aspose.pdf"}
        self.assertEqual({name: found for name, found in others.items() if found}, {})

    def test_short_pages_are_ok_with_a_note(self):
        # עד סבב 6ב: 11 עמודים "לא בטוח" רק כי הם קצרים, ועוד אחד (ספר GPS, עמוד 16) בגלל שורה דו-משמעית אחת ב-10 מילים
        short = sorted((name, i) for name, scores in self.ev.scores.items() for i, s in enumerate(scores, 1)
                       if "short" in [note.kind for note in s.notes])
        self.assertEqual(short, [("doc-4p_weasyprint.pdf", 4)] +
                         [("financial-report-q2-2025_aspose.pdf", i) for i in (1, 3, 28, 52, 64)] +
                         [("gps-book_indesign.pdf", i) for i in (7, 11, 14, 15, 16)] + [("presentation_canva.pdf", 1)])
        for name, i in short:
            self.assertEqual(self.ev.scores[name][i - 1].decision, score.OK, (name, i))

    def test_the_effort_is_a_note(self):
        page = self.ev.scores["presentation_canva.pdf"][6]
        self.assertEqual((page.decision, [note.kind for note in page.notes]), (score.OK, ["effort"]))

    def test_the_threshold_explanation_matches_the_numbers(self):
        # ההסבר בדוח אומר "כולו מעליה" רק כשהטווח באמת כולו מעל הדרישה, ואחרת שהוא מכיל אותה (calibration.chosen_range)
        cal = self.cal
        text = _plausible_how(cal)
        self.assertEqual("כאן הטווח הראשון שכולו מעליה" in text, cal.plausible_choice.low >= cal.required_plausible)
        self.assertIn("מה השתנה בסבב 6ב", text)
        # הטווח של סבב 6ב לפני הבדיקה של הכיסוי: הדרישה 0.747 בתוך הטווח 0.736 עד 0.790
        inside = dataclasses.replace(cal, required_plausible=0.747,
                                     plausible_choice=calibration.Range(0.7361, 0.7901),
                                     plausible_old_choice=calibration.Range(0.7901, 0.8382), old_choice_flags_good=2)
        text = _plausible_how(inside)
        self.assertIn("כאן הטווח שמכיל את הדרישה: 0.736 עד 0.790", text)
        self.assertNotIn("כולו מעליה:", text)
        self.assertIn("הכלל הישן היה בוחר 0.814", text)
        self.assertIn("2 עמודים ידועים כנכונים", text)

    def test_a_sign_of_a_problem_on_a_short_page_marks_no_known_page(self):
        # סבב 6ב: בעמוד קצר סימן לבעיה הוא סיבה. בסט אין עמוד קצר עם סימן כזה (הסימן היחיד בעמוד קצר הוא שורה
        # דו-משמעית, בספר GPS עמוד 16), ולכן הכלל לא מסמן אף עמוד, ידוע כנכון או לא
        flagged = [(name, i) for name, scores in self.ev.scores.items() for i, s in enumerate(scores, 1)
                   if "short" in [n.kind for n in s.notes] and s.reasons]
        self.assertEqual(flagged, [])

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
