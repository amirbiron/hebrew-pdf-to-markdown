"""החלקים של השירות שאפשר לבדוק בלי שרת: המגבלות, הגבלת הקצב, סוג הקובץ, ההודעות, תהליך ההמרה, והמקום של סמני
העמודים ב-Markdown (hebrew_pdf/markdown.py, Markdown.page_offsets)."""

import asyncio
import contextlib
import io
import json
import os
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import pypdfium2 as pdfium

from hebrew_pdf import score
from hebrew_pdf.lines import Geometry, Line, PageText
from hebrew_pdf.markdown import PAGE_MARKER, build_markdown
from tests.web_server import PDFS
from web import app as web_app
from web import conversion, limits, messages

MB = limits.MB


def cgroup(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp())
    for name, value in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(value)
    return root


class LimitsTest(unittest.TestCase):
    def test_container_memory(self):
        self.assertEqual(limits.container_memory(cgroup({"memory.max": "536870912\n"})), 512 * MB)
        self.assertIsNone(limits.container_memory(cgroup({"memory.max": "max\n"})))
        self.assertEqual(limits.container_memory(cgroup({"memory/memory.limit_in_bytes": "536870912"})), 512 * MB)
        # "בלי מגבלה" ב-v1 הוא LONG_MAX מעוגל לעמוד, כמו במכונה שבה נכתב השירות
        self.assertIsNone(limits.container_memory(cgroup({"memory/memory.limit_in_bytes": "9223372036854771712"})))
        with self.assertLogs("web.limits", "WARNING"):
            self.assertIsNone(limits.container_memory(cgroup({"memory.max": "lots"})))
        self.assertIsNone(limits.container_memory(cgroup({})))

    def test_slots_from_memory(self):
        # 512MB ב-Render: (512 - 100 - 64) / 194 = 1.8. מקום אחד כולל את תהליך ההמרה, הקובץ אצל השרת והטיפול בתשובה
        self.assertEqual(limits.SLOT_MEMORY, limits.CONVERSION_PHYSICAL + limits.MAX_BYTES + limits.ANSWER_COST)
        self.assertEqual(limits.slots_for(512 * MB), 1)
        self.assertEqual(limits.slots_for(1024 * MB), 4)
        self.assertEqual(limits.slots_for(100 * MB), limits.MIN_SLOTS)
        self.assertEqual(limits.slots_for(64 * 1024 * MB), limits.MAX_SLOTS)

    def test_slots_from_cpu(self):
        # חצי מעבד: 0.5 * 90 / 23.6 = 1.9. שתי המרות של קובץ הטבלאות לא היו מסתיימות בזמן
        self.assertEqual(limits.cpu_slots(0.5), 1)
        self.assertEqual(limits.cpu_slots(1.0), 3)
        self.assertEqual(limits.cpu_slots(0.1), limits.MIN_SLOTS)

    def test_container_cpus(self):
        self.assertEqual(limits.container_cpus(cgroup({"cpu.max": "50000 100000\n"})), 0.5)
        self.assertIsNone(limits.container_cpus(cgroup({"cpu.max": "max 100000\n"})))
        self.assertEqual(limits.container_cpus(cgroup({"cpu/cpu.cfs_quota_us": "200000", "cpu/cpu.cfs_period_us": "100000"})), 2.0)
        self.assertIsNone(limits.container_cpus(cgroup({"cpu/cpu.cfs_quota_us": "-1", "cpu/cpu.cfs_period_us": "100000"})))
        self.assertIsNone(limits.container_cpus(cgroup({})))
        for bad in ("50000", "a b", "50000 0"):
            with self.subTest(bad=bad), self.assertLogs("web.limits", "WARNING"):
                self.assertIsNone(limits.container_cpus(cgroup({"cpu.max": bad})))

    def test_capacity(self):
        both = cgroup({"memory.max": str(2048 * MB), "cpu.max": "50000 100000"})
        # הזיכרון מספיק ל-8, וחצי מעבד ל-1: הקטן מהשניים
        self.assertEqual(limits.capacity({}, both).slots, 1)
        self.assertEqual(limits.capacity({}, cgroup({"memory.max": str(2048 * MB)})).slots, limits.MAX_SLOTS)
        known = cgroup({"memory.max": str(1024 * MB)})
        self.assertEqual(limits.capacity({}, known).slots, 4)
        self.assertEqual(limits.capacity({}, cgroup({"memory.max": "max"})).slots, limits.MIN_SLOTS)
        self.assertEqual(limits.capacity({"HEBREW_PDF_SLOTS": "3"}, known), limits.Capacity(3, "HEBREW_PDF_SLOTS"))
        for bad in ("0", "99", "²", "2.5", "-1", ""):
            with self.subTest(bad=bad), self.assertLogs("web.limits", "ERROR"):
                self.assertEqual(limits.capacity({"HEBREW_PDF_SLOTS": bad}, known).slots, 4)

    def test_seconds(self):
        self.assertEqual(limits.seconds_from({}, "X", 90.0, 0.1, 600), 90.0)
        self.assertEqual(limits.seconds_from({"X": "2"}, "X", 90.0, 0.1, 600), 2.0)
        for bad in ("nan", "inf", "-1", "1000", "abc"):
            with self.subTest(bad=bad), self.assertLogs("web.limits", "ERROR"):
                self.assertEqual(limits.seconds_from({"X": bad}, "X", 90.0, 0.1, 600), 90.0)

    def test_the_heaviest_file_fits_the_memory_cap(self):
        # המדידה שמאחורי CONVERSION_MEMORY (web/measure.py): השיא הווירטואלי בסט, 138.8MB, עם שוליים
        self.assertGreater(limits.CONVERSION_MEMORY, 139 * MB * 1.3)


class RateLimiterTest(unittest.TestCase):
    def test_window(self):
        now = [0.0]
        limiter = web_app.RateLimiter(3, 10.0, clock=lambda: now[0])
        self.assertEqual([limiter.hit("a") for _ in range(3)], [None, None, None])
        self.assertAlmostEqual(limiter.hit("a"), 10.0)
        self.assertIsNone(limiter.hit("b"))
        now[0] = 10.5
        self.assertIsNone(limiter.hit("a"))

    def test_bounded_keys(self):
        now = [0.0]
        limiter = web_app.RateLimiter(1, 10.0, max_keys=3, clock=lambda: now[0])
        for key in "abcdef":
            limiter.hit(key)
        self.assertLessEqual(len(limiter._hits), 3)


class FileTypeTest(unittest.TestCase):
    def test_header_offsets(self):
        self.assertTrue(web_app.is_pdf(b"%PDF-1.7"))
        self.assertTrue(web_app.is_pdf(b" " * 1024 + b"%PDF-1.7"))
        self.assertFalse(web_app.is_pdf(b" " * 1025 + b"%PDF-1.7"))
        self.assertFalse(web_app.is_pdf(b"%PDF"))
        self.assertFalse(web_app.is_pdf(b""))


class MessagesTest(unittest.TestCase):
    def test_every_kind_is_explained(self):
        self.assertEqual(set(messages.REASONS), set(score.REASON_KINDS))
        self.assertEqual(set(messages.NOTES), set(score.NOTE_KINDS))
        self.assertEqual(set(messages.DECISIONS), set(score.DECISIONS))
        self.assertEqual(set(conversion.DECISION_CODES), set(score.DECISIONS))

    def test_every_failure_has_a_message(self):
        for code in conversion.FAILURES:
            with self.subTest(code=code):
                status, text = messages.error(code)
                self.assertGreaterEqual(status, 400)
                self.assertTrue(any("א" <= char <= "ת" for char in text))
                self.assertNotIn("{", text)

    def test_legend_follows_the_decisions(self):
        self.assertEqual([entry["text"] for entry in messages.legend()], list(score.DECISIONS))


class SafeTracebackTest(unittest.TestCase):
    def test_no_message(self):
        try:
            raise KeyError("טקסט מתוך הקובץ שהועלה")
        except KeyError as error:
            line = conversion.safe_traceback(error)
        self.assertIn("KeyError", line)
        self.assertIn("test_web_units.py", line)
        self.assertNotIn("טקסט", line)


class OutcomeTest(unittest.TestCase):
    def test_pages_are_counted_before_the_conversion(self):
        pdf = pdfium.PdfDocument.new()
        for _ in range(3):
            pdf.new_page(100, 100)
        buffer = io.BytesIO()
        pdf.save(buffer)
        with mock.patch.object(conversion, "convert_document", side_effect=AssertionError("ההמרה רצה")) as convert:
            self.assertEqual(conversion.outcome(buffer.getvalue(), max_pages=2), {"error": conversion.TOO_MANY_PAGES})
        convert.assert_not_called()

    def test_a_bug_is_not_a_damaged_file(self):
        # חריגה שאינה PdfiumError עולה מ-outcome, ולא מסומנת כקובץ פגום (child_main הופך אותה ל-INTERNAL)
        data = (PDFS / "doc-2p_weasyprint.pdf").read_bytes()
        with mock.patch.object(conversion, "convert_document", side_effect=TypeError("באג")):
            with self.assertRaises(TypeError):
                conversion.outcome(data, max_pages=10)


class ChildProcessTest(unittest.TestCase):
    """תהליך ההמרה עצמו, דרך conversion.convert, בלי שרת HTTP."""

    @classmethod
    def setUpClass(cls):
        conversion.start_worker_server()

    def run_convert(self, data: bytes, **kwargs) -> dict:
        options = {"max_pages": 100, "timeout": 60, "memory_limit": limits.CONVERSION_MEMORY,
                   "max_answer": limits.MAX_ANSWER, **kwargs}
        return asyncio.run(conversion.convert(data, **options))

    def test_result(self):
        result = self.run_convert((PDFS / "doc-2p_weasyprint.pdf").read_bytes())
        self.assertEqual([page["number"] for page in result["pages"]], [1, 2])
        lines = result["markdown"].split("\n")
        for page in result["pages"]:
            self.assertIn(PAGE_MARKER.format(page["number"]), lines[page["line"]])

    def test_memory_cap_fails_alone(self):
        # תקרה נמוכה מכפי שהדוח הכספי צריך: ההמרה נכשלת בקוד שלה, והקורא מקבל חריגה ולא נתקע
        with self.assertRaises(conversion.ConversionFailed) as caught:
            self.run_convert((PDFS / "financial-report-q2-2025_aspose.pdf").read_bytes(), memory_limit=90 * MB)
        self.assertIn(caught.exception.code, (conversion.TOO_HEAVY, conversion.CRASHED))

    def test_timeout(self):
        with self.assertRaises(conversion.ConversionFailed) as caught:
            self.run_convert((PDFS / "env-vars_weasyprint.pdf").read_bytes(), timeout=0.5)
        self.assertEqual(caught.exception.code, conversion.TIMEOUT)

    def test_an_answer_over_the_cap_is_refused(self):
        # התשובה של הקובץ הזה כ-4KB; תקרה של 1KB עוצרת את הקריאה, והתהליך נהרג
        data = (PDFS / "doc-2p_weasyprint.pdf").read_bytes()
        with self.assertRaises(conversion.ConversionFailed) as caught, self.assertLogs("web.conversion", "WARNING"):
            self.run_convert(data, max_answer=1024)
        self.assertEqual(caught.exception.code, conversion.TOO_HEAVY)
        self.assertEqual(len(self.run_convert(data)["pages"]), 2)

    def test_sending_does_not_block_the_loop(self):
        # 128MB לתהליך שקורא וסופר. בזמן ההחלפה הלולאה ממשיכה לרוץ. בקרה באותה בדיקה: אותו קובץ בארגומנטים של
        # התהליך, כמו בגרסה הקודמת, חוסם את הלולאה בתוך process.start
        data = b"%" * (128 * MB)

        async def longest_gap(work) -> tuple[float, object]:
            gaps, stop = [0.0], asyncio.Event()

            async def tick():
                last = time.perf_counter()
                while not stop.is_set():
                    await asyncio.sleep(0.002)
                    now = time.perf_counter()
                    gaps.append(now - last)
                    last = now

            ticker = asyncio.create_task(tick())
            await asyncio.sleep(0.05)
            try:
                result = await work()
            finally:
                stop.set()
                await ticker
            return max(gaps), result

        async def through_exchange():
            return await conversion.exchange(count_input, data, (), timeout=60, max_answer=1024)

        async def through_arguments():
            process = conversion._CONTEXT.Process(target=len, args=(data,))
            process.start()
            await conversion._stop(process)

        # חימום: ההחלפה הראשונה בתהליך כוללת עבודה חד-פעמית (נמדד: 84ms בראשונה, 5 עד 11 אחריה; הבקרה 290 עד 465)
        asyncio.run(conversion.exchange(count_input, b"x", (), timeout=60, max_answer=1024))
        gap, raw = asyncio.run(longest_gap(through_exchange))
        self.assertEqual(json.loads(raw), {"size": len(data)})
        control, _ = asyncio.run(longest_gap(through_arguments))
        self.assertGreater(control, 0.05, "הבקרה לא חסמה: הבדיקה לא מבדילה בין שתי הדרכים")
        self.assertLess(gap, control / 3, (gap, control))


class DecodeTest(unittest.TestCase):
    """התשובה מהתהליך היא קלט חיצוני: תהליך שמפענח קובץ עוין. כל מבנה לא צפוי הוא CRASHED, לא חריגה בשרת."""

    def code(self, raw: bytes) -> str:
        with self.assertRaises(conversion.ConversionFailed) as caught:
            conversion._decode(raw)
        return caught.exception.code

    def test_broken_answers(self):
        page = {"number": 1, "decision": "ok", "decision_text": "תקין", "reasons": [], "notes": [], "line": 0}
        good = {"result": {"markdown": "x", "pages": [page]}}
        self.assertEqual(conversion._decode(json.dumps(good).encode()), good["result"])
        for raw in (b"", b"{", "\u05d0".encode()[:1], b"[]", b'{"result": 1}', b'{"error": "rm -rf"}', b'{"error": [1]}',
                    json.dumps({"result": {"markdown": "x", "pages": [{**page, "number": 2}]}}).encode(),
                    json.dumps({"result": {"markdown": "x", "pages": [{**page, "decision": "maybe"}]}}).encode(),
                    json.dumps({"result": {"markdown": "x", "pages": [{**page, "reasons": [{"kind": "x", "text": ""}]}]}}).encode(),
                    json.dumps({"result": {"markdown": "x", "pages": [{**page, "line": "0"}]}}).encode()):
            with self.subTest(raw=raw[:60]), self.assertLogs("web.conversion", "WARNING") if raw.startswith(b'{"result') else contextlib.nullcontext():
                self.assertEqual(self.code(raw), conversion.CRASHED)
        self.assertEqual(self.code(b'{"error": "protected"}'), conversion.PROTECTED)


class HostTest(unittest.TestCase):
    def test_empty_host_is_local(self):
        from web.__main__ import host
        self.assertEqual(host({}), "127.0.0.1")
        self.assertEqual(host({"HOST": ""}), "127.0.0.1")
        self.assertEqual(host({"HOST": "  "}), "127.0.0.1")
        self.assertEqual(host({"HOST": "0.0.0.0"}), "0.0.0.0")


class ContrastTest(unittest.TestCase):
    """style.css מבטיח לפחות 4.5:1 (WCAG AA) לכל טקסט על הרקע שלו, בשתי הערכות. החשבון מהערכים בקובץ עצמו."""

    PAIRS = [("text", "bg"), ("text", "surface"), ("muted", "bg"), ("muted", "surface"), ("accent", "surface"),
             ("accent", "bg"), ("accent-text", "accent"), ("ok", "ok-bg"), ("unsure", "unsure-bg"),
             ("rejected", "rejected-bg"), ("ok", "bg"), ("unsure", "bg"), ("rejected", "bg"), ("text", "current")]

    @staticmethod
    def luminance(color: str) -> float:
        def channel(value: int) -> float:
            c = value / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    def test_contrast(self):
        css = (Path(web_app.STATIC_DIR) / "style.css").read_text(encoding="utf-8")
        blocks = re.findall(r":root\s*\{(.*?)\}", css, re.DOTALL)
        self.assertEqual(len(blocks), 2, "ערכה בהירה וערכה כהה")
        for block in blocks:
            tokens = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})", block))
            for fore, back in self.PAIRS:
                with self.subTest(fore=fore, back=back):
                    a, b = sorted((self.luminance(tokens[fore]), self.luminance(tokens[back])), reverse=True)
                    self.assertGreaterEqual((a + 0.05) / (b + 0.05), 4.5)


def count_input(source, answer) -> None:
    """תהליך לבדיקה: קורא את מה שנשלח וסופר, בלי לשמור (conversion.exchange)."""
    size = 0
    while chunk := os.read(source.fileno(), 1 << 16):
        size += len(chunk)
    source.close()
    conversion.write_answer(answer, conversion.encode_answer({"size": size}))


def _line(text: str, baseline: float) -> Line:
    return Line(text, text, True, geometry=Geometry(baseline, 100.0, 300.0, 10.0, 5.0, "Body"))


class PageOffsetsTest(unittest.TestCase):
    def test_marker_text_inside_the_content_is_not_a_marker(self):
        # טקסט מהקובץ שנראה כמו סמן יוצא אחרי ההגנה "\<!-- page 2 -->"; המקום של הסמן האמיתי נרשם בבנייה
        pages = [PageText([_line("שורה עם <!-- page 2 --> בתוכה", 700.0)], 0),
                 PageText([_line("העמוד השני", 700.0)], 0)]
        built = build_markdown(pages)
        self.assertEqual(len(built.page_offsets), 2)
        for number, offset in enumerate(built.page_offsets, 1):
            self.assertTrue(built.text.startswith(PAGE_MARKER.format(number), offset))
        self.assertLess(built.text.find(PAGE_MARKER.format(2)), built.page_offsets[1])

    def test_inside_a_table(self):
        from hebrew_pdf.lines import RowSource
        header, row = ("שם", "ערך"), ("א", "1")

        def table_page(*rows):
            lines = [_line(" ".join(r), 700.0 - 20 * i) for i, r in enumerate(rows)]
            return PageText(lines, 0, table_rows=list(rows), row_sources=[RowSource((i,), 0) for i in range(len(rows))])

        built = build_markdown([table_page(header, row), table_page(header, ("ב", "2"))])
        self.assertTrue(built.text.startswith(PAGE_MARKER.format(2), built.page_offsets[1]))
        self.assertEqual(built.text.count("| --- |"), 1, "הטבלה לא התאחדה, והבדיקה לא בודקת סמן בתוך טבלה")


if __name__ == "__main__":
    unittest.main()
