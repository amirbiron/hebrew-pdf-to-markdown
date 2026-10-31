"""גבולות בין רכיבים, עמודות של טבלה ואיחוד שורות של טבלה (hebrew_pdf/layout.py, hebrew_pdf/lines.py).

שני חלקים: עמודים קטנים שבנויים ביד, שמראים כל כלל לבד, והשורות האמיתיות שבגללן
הכללים נכתבו (המספר בהערה הוא המספר ב-testset/labels.md).

בעמוד שבנוי ביד: אות ברוחב 5 וגובה 10, ורווח בין מילים 2 (הפער הרגיל, 0.2 מהגובה).
"""

import unittest

from harness.reader import read_pages
from harness.run import DEFAULT_PDFS
from harness.textdiff import normalize
from hebrew_pdf.chars import Char
from hebrew_pdf.layout import COMPONENT_GAP, page_layout, page_line, usual_word_gap
from hebrew_pdf.lines import _line, table_rows
from hebrew_pdf.spacing import space_by_gaps

WIDTH, HEIGHT, WORD = 5.0, 10.0, 2.0
USUAL = WORD / HEIGHT


def chars(segments: list[tuple[float, str]], baseline: float, size: float = 0.0) -> list[Char]:
    """תווים של שורה בעמוד: כל קטע מתחיל ב-x שלו, והתווים שלו לפי הסדר בעמוד משמאל לימין.
    size: גודל האות (Char.size); 0 כמו תו בלי גודל."""
    out = []
    for x, text in segments:
        for ch in text:
            if ch == " ":
                x += WORD
                continue
            out.append(Char(ch, x + WIDTH / 2, baseline, x, x + WIDTH, HEIGHT, size))
            x += WIDTH
    return out


def build(page: list[list[tuple[float, str]]], rtl: bool = False, rules_above: tuple[int, ...] = (),
          sizes: tuple[float, ...] = ()):
    """השורות של עמוד (מלמעלה למטה, 15 נקודות בין שורה לשורה), אחרי חלוקה לרכיבים.

    rules_above: השורות שמעליהן מצויר קו אופקי לרוחב כל העמוד (קו מסגרת של טבלה).
    sizes: גודל האות של כל שורה (Char.size); בלי: 0 לכל השורות.
    """
    sizes = sizes or (0.0,) * len(page)
    spaced = [space_by_gaps(chars(segments, -15.0 * i, size)) for i, (segments, size) in enumerate(zip(page, sizes))]
    lines = [page_line(s.chars) for s in spaced]
    rules = [(-10.0, 400.0, -15.0 * i + 9) for i in rules_above]
    layout = page_layout(lines, USUAL, rules)
    built = [_line(line, layout.boundaries[i], layout.columns[i], rtl, s.counts) for i, (line, s) in
             enumerate(zip(lines, spaced))]
    return built, table_rows(built, layout.tables, lines, rules)


def gap(words: float) -> float:
    """פער של פי words מהפער הרגיל, בנקודות."""
    return words * WORD


class UsualWordGapTest(unittest.TestCase):
    def test_the_most_common_gap_not_the_median(self):
        # בעמוד של טבלה יש יותר פערים בין תאים מאשר בין מילים, אבל הם מפוזרים
        self.assertEqual(usual_word_gap([0.2, 0.2, 0.21, 1.5, 2.0, 3.1, 4.4, 6.0]), 0.2)


class ComponentTest(unittest.TestCase):
    def test_a_gap_of_an_order_of_magnitude_is_a_boundary(self):
        lines, _ = build([[(0, "ab cd"), (24 + gap(COMPONENT_GAP), "ef")]])
        self.assertEqual(lines[0].cells, ("ab cd", "ef"))

    def test_a_wide_gap_in_one_line_only_is_not_a_boundary(self):
        # כמו "הופקה ב-11/05/2026 · בתוקף עד": פער של פי 7, בלי עמודה (שורה 13)
        lines, _ = build([[(0, "ab"), (10 + gap(7), "cd")]])
        self.assertEqual(lines[0].cells, ("ab cd",))

    def test_a_moderate_gap_on_a_column_is_a_boundary(self):
        # השורה העליונה פותחת עמודה (פער של פי 12); בשורה השנייה, באותו מקום, פער של פי 4
        lines, _ = build([[(0, "ab"), (100, "cd")],
                          [(0, "abcdefghijklm"), (65 + gap(4), "xy")]])
        self.assertEqual(lines[1].cells[-1], "xy")
        self.assertEqual(len(lines[1].components), 2)

    def test_a_line_that_crosses_the_column_ends_it(self):
        lines, _ = build([[(0, "ab"), (100, "cd")],
                          [(0, "a long line of words that crosses")],
                          [(0, "abcdefghijklm"), (65 + gap(4), "xy")]])
        self.assertEqual(len(lines[2].components), 1)

    def test_components_are_in_reading_order(self):
        lines, _ = build([[(0, "ab"), (100, "cd")]], rtl=True)
        self.assertEqual(lines[0].cells, ("cd", "ab"))
        lines, _ = build([[(0, "ab"), (100, "cd")]], rtl=False)
        self.assertEqual(lines[0].cells, ("ab", "cd"))


class TableTest(unittest.TestCase):
    def test_an_empty_column_is_an_empty_cell(self):
        # כמו שורות 38-40: עמודת "באור" ריקה ברוב השורות
        lines, _ = build([[(0, "11"), (60, "22"), (120, "note"), (200, "label")],
                          [(0, "33"), (60, "44"), (200, "other")]])
        self.assertEqual(lines[1].cells, ("33", "44", "", "other"))

    def test_a_heading_over_two_columns_does_not_add_columns_to_the_rows(self):
        # כותרת שמרוכזת מעל שתי עמודות יוצרת מסדרונות משלה, בשורות שלה בלבד
        lines, _ = build([[(20, "h1"), (140, "h2")],
                          [(20, "h3"), (140, "h4")],
                          [(0, "11"), (40, "22"), (120, "33"), (160, "44")],
                          [(0, "55"), (40, "66"), (120, "77"), (160, "88")]])
        self.assertEqual(lines[3].cells, ("55", "66", "77", "88"))

    def test_continuation_lines_are_one_row(self):
        _, rows = build([[(0, "c1"), (60, "first part"), (200, "NAME")],
                         [(60, "second")],
                         [(0, "c2"), (60, "next row"), (200, "OTHER")]])
        self.assertEqual(rows, [("c1", "first part second", "NAME"), ("c2", "next row", "OTHER")])

    def test_without_frame_lines_text_in_the_first_column_starts_a_row(self):
        # כמו בדוח הכספי: שורות של שורה אחת, בלי קווים
        _, rows = build([[(0, "c1"), (60, "desc"), (200, "ABCDEFGH")],
                         [(0, "c2"), (60, "next"), (200, "KL")]])
        self.assertEqual(rows, [("c1", "desc", "ABCDEFGH"), ("c2", "next", "KL")])

    def test_frame_lines_decide_where_a_row_starts(self):
        # בשורת ההמשך יש טקסט בעמודה הראשונה, וקו בין שורות הטבלה מראה שזו אותה שורה
        page = [[(0, "c1"), (60, "desc"), (200, "ABCDEFGH")],
                [(60, "more"), (200, "IJ")],
                [(0, "c2"), (60, "a wider one"), (200, "KL")],
                [(0, "c3"), (60, "last"), (200, "MN")]]
        _, rows = build(page, rules_above=(0, 2, 3))
        self.assertEqual(rows, [("c1", "desc more", "ABCDEFGH IJ"), ("c2", "a wider one", "KL"), ("c3", "last", "MN")])

    def test_a_single_word_as_wide_as_its_column_joins_with_a_space(self):
        # עד סבב 5ב מילה אחת שממלאת את רוחב העמודה נחשבה מילה שנשברה באמצע, וחוברה בלי רווח
        # ("descmore"). מחוץ לקובץ הטבלאות הכלל הזה טעה ב-41 מתוך 45 פעמים, והוא ירד
        page = [[(0, "c1"), (60, "desc"), (200, "AB")],
                [(60, "more")],
                [(0, "c2"), (60, "next"), (200, "KL")]]
        _, rows = build(page, rules_above=(0, 2))
        self.assertEqual(rows[0], ("c1", "desc more", "AB"))

    def test_a_frame_line_under_the_header_only_is_not_row_lines(self):
        page = [[(0, "h1"), (60, "head"), (200, "HEAD")],
                [(0, "c2"), (60, "next"), (200, "KL")],
                [(0, "c3"), (60, "last"), (200, "MN")]]
        _, rows = build(page, rules_above=(1,))
        self.assertEqual(len(rows), 3)

    def test_a_break_after_a_hyphen_has_no_space(self):
        _, rows = build([[(0, "c1"), (60, "to-"), (200, "NAME")],
                         [(60, "word")],
                         [(0, "c2"), (60, "next"), (200, "OTHER")]])
        self.assertEqual(rows[0], ("c1", "to-word", "NAME"))


class TableEndTest(unittest.TestCase):
    """איפה טבלה נגמרת (hebrew_pdf/layout.py, סעיף 5): כותרת קצרה בצד ימין לא חוצה את העמודות
    שמשמאלה, והמסדרון של הטבלה ממשיך לתוכה. גודל האות מסיים אותה."""
    TABLES = [[(0, "a1"), (60, "desc"), (200, "N1")],
              [(0, "a2"), (60, "more"), (200, "N2")],
              [(200, "HEAD")],
              [(0, "b1"), (60, "text"), (200, "M1")],
              [(0, "b2"), (60, "last"), (200, "M2")]]

    def test_a_heading_between_two_tables_ends_the_first(self):
        lines, rows = build(self.TABLES, sizes=(10, 10, 20, 10, 10))
        self.assertIsNone(lines[2].columns)
        self.assertEqual(rows, [("a1", "desc", "N1"), ("a2", "more", "N2"), ("HEAD",),
                                ("b1", "text", "M1"), ("b2", "last", "M2")])

    def test_without_a_size_the_heading_is_a_row(self):
        # כך היה עד סבב 5ב בכל גודל: הכותרת נבלעה בטבלה
        lines, _ = build(self.TABLES)
        self.assertIsNotNone(lines[2].columns)

    def test_in_a_framed_table_a_continuation_in_another_size_stays(self):
        # טבלה עם קווי מסגרת בין השורות: שורת המשך בתוך תא, בלי קו מעליה, בגודל אחר (קוד), שייכת לטבלה.
        # הכותרת, שיש קו מעליה (הקו התחתון של הטבלה), מסיימת אותה
        page = [[(0, "a1"), (60, "desc"), (200, "N1")],
                [(60, "code")],
                [(0, "a2"), (60, "more"), (200, "N2")],
                [(200, "HEAD")]]
        lines, rows = build(page, rules_above=(0, 2, 3), sizes=(10, 8, 10, 20))
        self.assertIsNotNone(lines[1].columns)
        self.assertIsNone(lines[3].columns)
        self.assertEqual(rows, [("a1", "desc code", "N1"), ("a2", "more", "N2"), ("HEAD",)])


class RealLinesTest(unittest.TestCase):
    @staticmethod
    def lines(file_name: str, page: int):
        return read_pages(DEFAULT_PDFS / file_name)[page - 1].lines

    def test_separators_inside_a_line_stay_one_component(self):  # שורות 13 ו-5
        cells = [line.cells for line in self.lines("price-quote_weasyprint.pdf", 1)]
        self.assertIn(("הופקה ב-11/05/2026 · בתוקף עד 25/05/2026",), cells)
        cells = [line.cells for line in self.lines("doc-6p_gdocs.pdf", 1)]
        self.assertIn(("1. חיבור פייסבוק (Meta OAuth): המשתמש נכנס למערכת ומבצע FB Connect. ה-Backend",), cells)

    def test_boxes_side_by_side(self):  # שורה 8
        cells = [line.cells for line in self.lines("mentoros-overview_weasyprint.pdf", 1)]
        self.assertIn(("מודולים מרכזיים", "שאלות Deep Dive", "זיכרון ארוך טווח", "שכבות בטיחות"), cells)

    def test_financial_row_with_an_empty_note_column(self):  # שורה 38
        cells = [line.cells for line in self.lines("financial-report-q2-2025_aspose.pdf", 35)]
        self.assertIn(("הכנסות ממכירות", "", "366,343", "300,306*", "178,881", "145,921*", "633,833*"), cells)

    def test_table_row_broken_over_three_lines(self):
        # בעמוד עמודת הרכיב נשברת אחרי הלוכסנים ל-"Bot/WebApp/", "MCP/" ו-"Webserver", והתיאור בשתי שורות
        rows = [tuple(normalize(c) for c in row) for row in read_pages(DEFAULT_PDFS / "env-vars_weasyprint.pdf")[0].rows]
        self.assertIn(("MONGODB_HEARTBEAT_FREQUENCY_MS", "תדירות בדיקת החיים של הדרייבר מול שרתי מונגו (heartbeatFrequencyMS)",
                       "לא", "10000", "20000", "Bot/WebApp/MCP/Webserver"), rows)

    def test_the_table_file_is_a_hebrew_document(self):
        # רוב האותיות בו לטיניות (שמות משתנים), אבל רוב השורות עבריות
        self.assertTrue(all(line.rtl for line in self.lines("env-vars_weasyprint.pdf", 1) if line.text))


if __name__ == "__main__":
    unittest.main()
