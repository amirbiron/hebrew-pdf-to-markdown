"""הבנייה של קובצי הבדיקה ממקור ידוע (tools/build_table_pdf.py), ומה שנבנה בפועל בריפו.

- ה-HTML: רשימה פנימית בהזחה של שלושה רווחים (כמו במסמך האפיון) נשארת פנימית, ושורה אחרי תיבת
  ":::" נשארת כותרת. שני אלה נשברו כשה-HTML נבנה אחרת (python-markdown, ותיבה בלי שורה ריקה אחריה).
- כל דף תשובות בריפו זהה למה שהכלי גוזר היום מהמקור שלו: בלי זה דף התשובות והמקור יכולים להיפרד
  בלי שמישהו ישים לב.
- בקבצים שנבנו אף מילה לא נשברת באמצע: כל מזהה (אותיות לטיניות, ספרות וקו תחתון) וכל מילה עברית
  מדף התשובות מופיעים שלמים בשורה אחת בעמוד. בקובץ הטבלאות הקודם (overflow-wrap: anywhere) 174
  מתוך 3,340 נשברו באמצע (נמדד ב-unbroken_words).
"""

import json
import re
import unittest
from pathlib import Path

import pypdfium2 as pdfium

from harness.html_structure import block_to_json, parse
from harness.run import DEFAULT_PDFS, DEFAULT_TRUTH, ROOT
from harness.tables import pdf_names
from hebrew_pdf.chars import page_chars
from hebrew_pdf.lines import group_rows
from tools.build_table_pdf import build_html

SOURCES = ROOT / "testset" / "sources"


def blocks(source: str) -> list[dict]:
    return [block_to_json(block) for block in parse(build_html(source, False, 8.5, "x")).structure]


class BuildHtmlTest(unittest.TestCase):
    def test_a_list_indented_by_three_spaces_is_nested(self):
        out = blocks("1. ראשון\n2. שני:\n   - פנימי\n3. שלישי\n")
        self.assertEqual([(b["level"], b["text"]) for b in out], [(0, "ראשון"), (0, "שני:"), (1, "פנימי"), (0, "שלישי")])

    def test_a_heading_right_after_a_box_stays_a_heading(self):
        out = blocks("::: note\nתיבה\n:::\n## כותרת\n\nפסקה\n")
        self.assertEqual(out, [{"kind": "paragraph", "text": "תיבה"}, {"kind": "heading", "level": 2, "text": "כותרת"},
                               {"kind": "paragraph", "text": "פסקה"}])


class RepoTruthFilesTest(unittest.TestCase):
    def test_every_truth_file_is_what_the_tool_derives_from_its_source(self):
        truth_files = sorted(DEFAULT_TRUTH.glob("*.truth.json"))
        self.assertTrue(truth_files)
        for path in truth_files:
            with self.subTest(truth=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                source = SOURCES / data["source"]
                self.assertEqual(source.stem + ".truth.json", path.name)
                self.assertEqual(data["blocks"], blocks(source.read_text(encoding="utf-8")))


def unbroken_words(pdf: Path, truth: Path) -> tuple[int, list[str]]:
    """(כמה מילים נבדקו, המילים מדף התשובות שלא נמצאו שלמות באף שורה בעמוד).

    שורה בעמוד: האותיות שלה לפי המיקום, משמאל לימין, בלי רווחים. מזהה לטיני נבדק כמו שהוא, ומילה
    עברית הפוכה (עברית מצוירת מימין לשמאל). מזהה שמתחיל או נגמר בקו תחתון לא נבדק: קו תחתון הוא
    תו ניטרלי, ובקצה של מילה בתוך שורה עברית הוא מצויר בצד השני שלה. בלוק קוד לא נבדק (בו השורות
    נשברות בכל מקום, pre-wrap)."""
    data = json.loads(truth.read_text(encoding="utf-8"))
    texts = []
    for block in data["blocks"]:
        if block["kind"] == "table":
            texts += [cell for row in block["rows"] for cell in row]
        elif block["kind"] != "code":
            texts.append(block["text"])
    words = {word for text in texts for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9_]*[A-Za-z0-9]|[א-ת]{2,}", text)}
    lines = []
    with pdfium.PdfDocument(str(pdf)) as document:
        for page in document:
            for row in group_rows(page_chars(page).chars):
                lines.append("".join(c.text for c in sorted(row, key=lambda c: c.x) if c.text.strip()))
    joined = "\n".join(lines)
    return len(words), sorted(w for w in words if (w if w.isascii() else w[::-1]) not in joined)


class NoWordBrokenInTheMiddleTest(unittest.TestCase):
    def test_built_files(self):
        pdfs = [path.name for path in DEFAULT_PDFS.glob("*.pdf")]
        for truth in sorted(DEFAULT_TRUTH.glob("*.truth.json")):
            for name in pdf_names(truth, pdfs):
                with self.subTest(pdf=name):
                    checked, broken = unbroken_words(DEFAULT_PDFS / name, truth)
                    self.assertGreater(checked, 1000)
                    self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
