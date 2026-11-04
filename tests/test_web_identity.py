"""מקור אחד לתוצאה: על כל 15 הקבצים, מה שהשירות מחזיר דרך הראוט זהה למה שמערך הבדיקה מודד, תו בתו.

מערך הבדיקה קורא את הקובץ מהדיסק (harness/reader.py) ובונה דרך hebrew_pdf.convert.convert_pages, והשירות מקבל את
הקובץ כגוף של בקשת HTTP, פותח אותו מהזיכרון בתהליך נפרד, ובונה דרך convert_document (web/conversion.py). כאן
משווים את שניהם: ה-Markdown, ולכל עמוד ההחלטה, הסיבות וההערות, והשורה שהדף קופץ אליה. השרת רץ בתצורה של הייצור,
עם המגבלות של הייצור (web/limits.py), כך שגם הקובץ האיטי בסט וגם הכבד בזיכרון עוברים בתוכן.
"""

import json
import unittest

from harness.run import DEFAULT_LABELS, DEFAULT_PDFS, evaluate
from hebrew_pdf.markdown import PAGE_MARKER
from tests.web_server import Server
from web.conversion import DECISION_CODES


class RouteMatchesHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ev = evaluate(DEFAULT_PDFS, DEFAULT_LABELS)
        cls.markdown = {m.name: m.text for m in ev.markdown}
        cls.scores = ev.scores
        cls.routed = {}
        with Server() as server:
            for path in sorted(DEFAULT_PDFS.glob("*.pdf")):
                status, headers, body = server.convert(path.read_bytes(), ip="198.51.100.100", timeout=300)
                cls.routed[path.name] = (status, json.loads(body))

    def test_all_files(self):
        self.assertEqual(sorted(self.routed), sorted(self.markdown))
        self.assertEqual(len(self.routed), 15)

    def test_markdown_is_identical(self):
        for name, (status, result) in self.routed.items():
            with self.subTest(name=name):
                self.assertEqual(status, 200)
                self.assertEqual(result["markdown"], self.markdown[name])

    def test_decisions_reasons_and_notes_are_identical(self):
        for name, (_, result) in self.routed.items():
            with self.subTest(name=name):
                expected = [(DECISION_CODES[page.decision], page.decision,
                             [(reason.kind, reason.text) for reason in page.reasons],
                             [(note.kind, note.text) for note in page.notes]) for page in self.scores[name]]
                got = [(page["decision"], page["decision_text"],
                        [(reason["kind"], reason["text"]) for reason in page["reasons"]],
                        [(note["kind"], note["text"]) for note in page["notes"]]) for page in result["pages"]]
                self.assertEqual(got, expected)
                self.assertEqual([page["number"] for page in result["pages"]], list(range(1, len(expected) + 1)))

    def test_every_page_line_is_its_marker(self):
        for name, (_, result) in self.routed.items():
            lines = result["markdown"].split("\n")
            for page in result["pages"]:
                with self.subTest(name=name, page=page["number"]):
                    self.assertIn(PAGE_MARKER.format(page["number"]), lines[page["line"]])

    def test_the_whole_set_through_the_route(self):
        decisions = [page["decision"] for _, result in self.routed.values() for page in result["pages"]]
        # המספרים של הדוח (testset/report.md, "ציון העמודים"): 157 / 22 / 6
        self.assertEqual((decisions.count("ok"), decisions.count("unsure"), decisions.count("rejected")), (157, 22, 6))


if __name__ == "__main__":
    unittest.main()
