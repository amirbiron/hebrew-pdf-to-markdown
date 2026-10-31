"""בניית ה-Markdown (hebrew_pdf/markdown.py), על עמודים קטנים שנבנים כאן.

כל בדיקה של תוצאה עוברת דרך cmark-gfm (harness/markdown_check.py), המפרסר ש-GitHub מציג בו
Markdown: מה שנבדק הוא מה שהקורא של ה-Markdown יראה, ולא המחרוזת שהבונה כתב.
"""

import unittest

import cmarkgfm

from harness import markdown_check as mc
from hebrew_pdf.lines import Component, Geometry, Line, PageText, RowSource
from hebrew_pdf.markdown import Markdown, build_markdown, escape_text, first_strong

LEFT, RIGHT = 100.0, 500.0  # רוחב המסגרת: 400


def line(text: str, y: float, *, left: float = LEFT, right: float = RIGHT, size: float = 10.0,
         glyph: float = 5.0) -> Line:
    return Line(text, text[::-1], True, geometry=Geometry(y, left, right, size, glyph))


def page(*lines: Line, rows=None, sources=None) -> PageText:
    return PageText(list(lines), 0, table_rows=rows, row_sources=sources, rtl_document=True, width=600.0,
                    height=800.0)


def html(markdown: Markdown) -> mc.ParsedHtml:
    return mc.parse(mc.to_html(markdown.text))


def shown(markdown_text: str) -> str:
    """הטקסט שהמפרסר מציג (בלי תגים ובלי הערות), בלי רווחים בקצוות."""
    return "".join(mc.parse(cmarkgfm.github_flavored_markdown_to_html(markdown_text)).text).strip()


class EscapeTest(unittest.TestCase):
    """טקסט מוצג כטקסט ולא כעיצוב: בתוך שורה, בתחילת פסקה, בכותרת, בפריט ובתא."""

    SAMPLES = ["300,306*", "IG_USER_ID", "__init__", "*לא* מודגש", "`קוד`", "~~מחוק~~", "<b>x</b>",
               "&amp; ו-&", "[קישור](http://x)", "C:\\path\\", "a | b", "# לא כותרת", "> לא ציטוט",
               "-לא פריט", "+לא פריט", "1.5 לא רשימה", "3)לא רשימה", "===", "---", "סוף #",
               "https://amirbiron.github.io/Automation-made-easy/", "www.x.com/a_b", "SECURITY\\_TOKENS.md>`_",
               "<!-- הערה -->", "[ ] משימה"]
    # בתחילת שורה אלה פריטים ברשימה (_marker); בתוך פריט, אותו טקסט צריך להיות טקסט
    ITEM_CONTENTS = ["- לא פריט", "+ לא פריט", "1. לא רשימה", "3) לא רשימה", "[ ] משימה", "# לא כותרת"]

    def test_paragraph(self):
        for text in self.SAMPLES:
            with self.subTest(text=text):
                built = build_markdown([page(line(text, 700))])
                paragraphs = [t for tag, t in html(built).blocks if tag == "p"]
                self.assertEqual(paragraphs, [text])

    def test_list_item_content(self):
        for text in self.ITEM_CONTENTS:
            with self.subTest(text=text):
                built = build_markdown([page(line("• " + text, 700))])
                self.assertEqual([t for tag, t in html(built).blocks if tag == "li"], [text])

    def test_heading(self):
        for text in ["C# ו-F#", "סוף #", "*כוכבית*", "300,306*"]:
            with self.subTest(text=text):
                body = [line("גוף הטקסט עם הרבה מאוד אותיות כדי שיהיה הנפוץ", 600 - 40 * k) for k in range(3)]
                built = build_markdown([page(line(text, 760, size=20.0), *body)])
                self.assertEqual(html(built).headings, [(1, text)])

    def test_table_cell(self):
        for text in self.SAMPLES:
            with self.subTest(text=text):
                rows = [("כותרת", "עמודה"), (text, "x")]
                built = build_markdown([page(line("כותרת עמודה", 700), line("x", 680), rows=rows,
                                             sources=[RowSource((0,), 0), RowSource((1,), 0)])])
                self.assertEqual(html(built).tables, [[("כותרת", "עמודה"), (text, "x")]])

    def test_autolink_text_is_kept_exactly(self):
        # בקישור אוטומטי GFM לא מבטל escapes: בלי _AUTOLINK_START הלוכסנים נשארים גלויים
        text = "https://github.com/a/SECURITY_TOKENS.md>`_"
        self.assertEqual(shown(escape_text(text)), text)


class ParagraphTest(unittest.TestCase):
    def test_wrapped_lines_join_and_a_larger_gap_starts_a_new_paragraph(self):
        built = build_markdown([page(
            line("שורה ראשונה ארוכה שנשברה", 700), line("בגלל רוחב", 685, left=400),
            line("פסקה שנייה מתחילה כאן", 650), line("וממשיכה", 635, left=420))])
        self.assertEqual([t for tag, t in html(built).blocks if tag == "p"],
                         ["שורה ראשונה ארוכה שנשברה בגלל רוחב", "פסקה שנייה מתחילה כאן וממשיכה"])

    def test_short_lines_without_wrapping_stay_apart(self):
        # שום שורה בגוש לא נשברה בגלל רוחב המסגרת (השורה הרחבה בעמוד), ואין במסמך מרווח של שורות
        # בתוך פסקה בגודל הזה: שורות נפרדות
        built = build_markdown([page(line("שורה שקובעת את רוחב המסגרת בעמוד", 750, size=12.0),
                                     line("אחת", 700, left=450), line("שתיים", 685, left=440))])
        self.assertEqual([t for tag, t in html(built).blocks if tag == "p"][-2:], ["אחת", "שתיים"])

    def test_document_line_step_is_used_where_a_block_has_no_wrapped_line(self):
        # הגוש השני הוא שורות בתא צר: אף אחת לא מלאה ביחס למסגרת, והמרווח של המסמך מכריע
        built = build_markdown([page(
            line("פסקה ארוכה שממלאת את המסגרת", 700), line("עד הסוף", 685, left=420),
            line("שורה בתא", 600, left=350, right=500), line("ועוד שורה בתא", 585, left=340, right=500))])
        self.assertIn("שורה בתא ועוד שורה בתא", [t for tag, t in html(built).blocks if tag == "p"])

    def test_size_change_starts_a_new_paragraph(self):
        built = build_markdown([page(line("טקסט רגיל ארוך מאוד שממלא", 700),
                                     line("טקסט קטן", 688, size=8.0))])
        self.assertEqual(len([t for tag, t in html(built).blocks if tag == "p"]), 2)

    def test_components_are_paragraphs_of_their_own(self):
        boxes = Line("תיבה ימנית תיבה שמאלית", "", True, components=(
            Component("תיבה ימנית", "", True, geometry=Geometry(700, 300, 500, 10, 5)),
            Component("תיבה שמאלית", "", True, geometry=Geometry(700, 100, 250, 10, 5))),
            geometry=Geometry(700, 100, 500, 10, 5))
        built = build_markdown([page(boxes)])
        self.assertEqual([t for tag, t in html(built).blocks if tag == "p"], ["תיבה ימנית", "תיבה שמאלית"])


class HeadingTest(unittest.TestCase):
    def test_levels_by_size_from_the_largest(self):
        body = [line("גוף הטקסט עם הרבה מאוד אותיות כדי שיהיה הנפוץ", 600 - 40 * k) for k in range(5)]
        built = build_markdown([page(line("כותרת ראשית", 760, size=20.0), line("כותרת משנה", 720, size=15.0),
                                     line("כמעט בגודל הגוף", 690, size=10.5), *body)])
        parsed = html(built)
        self.assertEqual(parsed.headings, [(1, "כותרת ראשית"), (2, "כותרת משנה")])
        self.assertIn("כמעט בגודל הגוף", [t for tag, t in parsed.blocks if tag == "p"])


class ListTest(unittest.TestCase):
    def build(self, *texts_and_indents):
        lines = [line(text, 700 - 20 * k, right=RIGHT - indent) for k, (text, indent) in enumerate(texts_and_indents)]
        return build_markdown([page(*lines)])

    def test_bullets_and_nesting_by_indentation(self):
        built = self.build(("• אחד", 0), ("◦ פנימי", 20), ("◆ שתיים", 0))
        self.assertIn("- אחד\n  - פנימי\n- שתיים", built.text)
        self.assertEqual(html(built).items, 3)
        self.assertEqual(built.markers, ("•", "◦", "◆"))

    def test_numbers_keep_their_values(self):
        built = self.build(("1. ראשון", 0), ("2. שני", 0), ("4. רביעי", 0))
        rendered = mc.to_html(built.text)
        self.assertIn('<ol start="4">', rendered)  # לא 3: רשימה חדשה, כי GFM ממספר ברצף
        self.assertEqual(html(built).items, 3)

    def test_nested_numbers_that_do_not_start_at_one(self):
        built = self.build(("ב. סעיף", 0), ("2. פנימי", 20), ("3. פנימי", 20))
        parsed = html(built)
        self.assertEqual(parsed.items, 3)  # בלי שורה ריקה, "2." היה ממשיך את הטקסט של "ב."
        self.assertIn('<ol start="2">', mc.to_html(built.text))

    def test_hebrew_letter_stays_in_the_text(self):
        built = self.build(("א. סעיף ראשון", 0))
        self.assertEqual([t for tag, t in html(built).blocks if tag == "li"], ["א. סעיף ראשון"])
        self.assertEqual(built.markers, ())

    def test_a_dash_without_text_is_not_an_item(self):
        built = self.build(("-", 0))
        self.assertEqual(html(built).items, 0)


class TableTest(unittest.TestCase):
    def table_page(self, *rows: tuple[str, ...]) -> PageText:
        lines = [line(" ".join(row), 700 - 20 * k) for k, row in enumerate(rows)]
        return page(*lines, rows=list(rows), sources=[RowSource((k,), 0) for k in range(len(rows))])

    def test_continued_table_with_repeated_header_is_one_table(self):
        built = build_markdown([self.table_page(("שם", "ערך"), ("א", "1")),
                                self.table_page(("שם", "ערך"), ("ב", "2"))])
        parsed = html(built)
        self.assertEqual(parsed.tables, [[("שם", "ערך"), ("א", "1"), ("ב", "2")]])
        self.assertEqual(built.repeated_headers, (("שם", "ערך"),))
        # גבול העמוד בתוך התא הראשון של השורה הראשונה מהעמוד השני, ולא כשורה ששוברת את הטבלה
        self.assertIn("| <!-- page 2 -->ב | 2 |", built.text)
        self.assertEqual(built.text.count("<!-- page 2 -->"), 1)

    def test_rows_with_fewer_cells_are_padded(self):
        built = build_markdown([self.table_page(("א", "ב", "ג"), ("ד",))])
        self.assertEqual(html(built).tables, [[("א", "ב", "ג"), ("ד", "", "")]])


class RunningLinesTest(unittest.TestCase):
    def test_repeated_header_and_page_number_are_dropped(self):
        bodies = {1: "פתיחה", 2: "אמצע המסמך", 3: "סיכום וסוף"}
        pages = [page(line("שם המסמך", 780), line(bodies[n], 400),
                      line(f"עמוד {n} מתוך 3", 20, left=280, right=320)) for n in (1, 2, 3)]
        built = build_markdown(pages)
        self.assertEqual(len(built.dropped), 6)
        self.assertNotIn("שם המסמך", built.text)
        self.assertNotIn("מתוך 3", built.text)

    def test_a_line_on_a_minority_of_pages_stays(self):
        pages = [page(line("שם המסמך" if n == 1 else f"כותרת {n}", 780), line("גוף", 400)) for n in (1, 2, 3)]
        self.assertIn("שם המסמך", build_markdown(pages).text)

    def test_a_single_page_drops_nothing(self):
        self.assertEqual(build_markdown([page(line("שם המסמך", 780))]).dropped, ())


class PageMarkerTest(unittest.TestCase):
    def test_every_page_has_a_marker_in_order(self):
        built = build_markdown([page(line("אחד", 700)), page(), page(line("שלוש", 700))])
        positions = [built.text.index(f"<!-- page {n} -->") for n in (1, 2, 3)]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(shown(built.text).split(), ["אחד", "שלוש"])


class FirstStrongTest(unittest.TestCase):
    def test_first_strong_letter(self):
        self.assertEqual(first_strong("Backend ב-Python"), "L")
        self.assertEqual(first_strong("3. שלב"), "R")
        self.assertIsNone(first_strong("12,345"))


if __name__ == "__main__":
    unittest.main()
