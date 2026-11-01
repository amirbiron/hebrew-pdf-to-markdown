"""הפירוק של HTML למבנה (harness/html_structure.py), שמשמש את שני הצדדים של מדידת המבנה."""

import unittest

import cmarkgfm

from harness.html_structure import HtmlBlock, block_to_json, parse, visible_text


def structure(markdown_text: str) -> list[HtmlBlock]:
    return parse(cmarkgfm.github_flavored_markdown_to_html(markdown_text)).structure


class StructureTest(unittest.TestCase):
    def test_blocks_in_order(self):
        blocks = structure("# כותרת\n\nפסקה עם `קוד` ו**מודגש**\n\n## משנה\n\n| א | ב |\n|---|---|\n| 1 | 2 |\n")
        self.assertEqual(blocks, [HtmlBlock("heading", "כותרת", 1), HtmlBlock("paragraph", "פסקה עם קוד ומודגש"),
                                  HtmlBlock("heading", "משנה", 2), HtmlBlock("table", rows=(("א", "ב"), ("1", "2")))])

    def test_inline_tags_do_not_add_spaces(self):
        # "ל-" ואחריו קטע קוד: אין רווח ביניהם בעמוד, ואסור שיתווסף
        self.assertEqual(structure("ל-`MongoDB` וגם **מו**דגש\n"), [HtmlBlock("paragraph", "ל-MongoDB וגם מודגש")])

    def test_nested_items_have_their_depth_and_own_text(self):
        blocks = structure("1. ראשון\n   - פנימי א\n   - פנימי ב\n2. שני\n\n   עם פסקה שנייה\n")
        self.assertEqual(blocks, [HtmlBlock("item", "ראשון", 0), HtmlBlock("item", "פנימי א", 1),
                                  HtmlBlock("item", "פנימי ב", 1), HtmlBlock("item", "שני עם פסקה שנייה", 0)])

    def test_quote_depth(self):
        self.assertEqual(structure("> ציטוט\n>\n> > פנימי\n\nאחרי\n"),
                         [HtmlBlock("paragraph", "ציטוט", quote=1), HtmlBlock("paragraph", "פנימי", quote=2),
                          HtmlBlock("paragraph", "אחרי")])

    def test_code_block_keeps_its_lines(self):
        self.assertEqual(structure("```\na = 1\nb  =  2\n```\n"), [HtmlBlock("code", "a = 1\nb = 2")])

    def test_what_is_not_shown_is_not_text(self):
        page = parse('<html><head><title>כותרת הדף</title><style>p { color: red; }</style></head>'
                     '<body><!-- page 1 --><p>טקסט</p></body></html>')
        self.assertEqual(page.structure, [HtmlBlock("paragraph", "טקסט")])
        self.assertEqual("".join(page.text), "טקסט")

    def test_blocks_inside_what_is_not_shown_are_not_blocks(self):
        # תוכן של template לא מוצג בעמוד, גם כשיש בו כותרת, פסקה ורשימה: אסור שיהיו בדף התשובות בלוקים ריקים
        page = parse("<template><h2>סודי</h2><p>גם</p><ul><li>פריט</li></ul><table><tr><td>א</td></tr></table>"
                     "</template><p>גלוי</p>")
        self.assertEqual(page.structure, [HtmlBlock("paragraph", "גלוי")])
        self.assertEqual((page.headings, page.items, page.blocks, page.tables), ([], 0, [("p", "גלוי")], []))

    def test_text_outside_any_block_is_one_paragraph(self):
        self.assertEqual(parse("<div>טקסט <b>מודגש</b> חופשי</div><p>פסקה</p>").structure,
                         [HtmlBlock("paragraph", "טקסט מודגש חופשי"), HtmlBlock("paragraph", "פסקה")])

    def test_visible_text(self):
        self.assertEqual(visible_text(" שני\u200f  רווחים\n"), "שני רווחים")

    def test_json_keeps_only_what_the_kind_means(self):
        self.assertEqual(block_to_json(HtmlBlock("paragraph", "א")), {"kind": "paragraph", "text": "א"})
        self.assertEqual(block_to_json(HtmlBlock("item", "א", 0, 2)), {"kind": "item", "level": 0, "text": "א", "quote": 2})
        self.assertEqual(block_to_json(HtmlBlock("table", rows=(("א",),))), {"kind": "table", "rows": [["א"]]})


if __name__ == "__main__":
    unittest.main()
