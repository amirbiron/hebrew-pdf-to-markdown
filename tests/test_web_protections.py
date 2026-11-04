"""ההגנות של השירות (web/app.py, web/conversion.py), כל אחת מול שרת אמיתי (tests/web_server.py).

כל בדיקה מוכיחה את התכונה ולא רק שחוזרת שגיאה: שהגוף לא נקרא (מול בקרה שבה הוא כן נקרא), שהעבודה באמת נעצרת
(התהליך נעלם), ושבקשות במקביל באמת רצות במקביל.
"""

import http.client
import io
import json
import os
import threading
import time
import unittest

import pypdfium2 as pdfium

from tests.web_server import PDFS, ROOT, Server, descendants
from web import limits

HEAVY = (PDFS / "env-vars_weasyprint.pdf").read_bytes()  # ההמרה האיטית בסט, כ-25 שניות (web/limits.py)
SMALL = (PDFS / "doc-2p_weasyprint.pdf").read_bytes()


def body(response) -> dict:
    return json.loads(response[2])


def blank_pdf(pages: int) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(200, 200)
    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


def status_of(raw: bytes) -> int:
    return int(raw.split(b" ", 2)[1]) if raw.startswith(b"HTTP/1.1 ") else 0


class CheapRejectTest(unittest.TestCase):
    """קובץ גדול מדי נדחה מהכותרות, לפני שנקרא בית אחד מהגוף."""

    @classmethod
    def setUpClass(cls):
        cls.server = Server(HEBREW_PDF_UPLOAD_SECONDS="30").__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def head(self, length: int) -> bytes:
        return (b"POST /api/convert HTTP/1.1\r\nHost: test\r\nContent-Type: application/pdf\r\n"
                b"CF-Connecting-IP: 198.51.100.10\r\nContent-Length: " + str(length).encode())

    def test_too_large_is_answered_without_the_body(self):
        # רק הכותרות נשלחות, בלי גוף בכלל. שרת שהיה קורא את הגוף היה מחכה לו ולא עונה (הבקרה למטה)
        received, first, closed = self.server.raw(self.head(limits.MAX_BYTES + 1), wait=5)
        self.assertEqual(status_of(received), 413)
        self.assertLess(first, 2)
        self.assertIn(b"connection: close", received.lower())
        self.assertTrue(closed, "החיבור נשאר פתוח אחרי הדחייה, והשרת היה ממשיך לקבל את הגוף")
        self.assertEqual(json.loads(received.split(b"\r\n\r\n", 1)[1])["error"], "too_large")

    def test_control_a_body_that_is_read_is_waited_for(self):
        # בקרה: אורך מותר ובלי גוף. כאן השרת קורא את הגוף, ולכן לא עונה עד שהזמן לקריאה נגמר
        received, first, _ = self.server.raw(self.head(1000), wait=2)
        self.assertEqual(received, b"")
        self.assertEqual(first, 2)

    def test_exactly_the_limit_is_read(self):
        received, first, _ = self.server.raw(self.head(limits.MAX_BYTES), wait=2)
        self.assertEqual(received, b"", "גודל שווה למגבלה אמור להיקרא, ולא להידחות")

    def test_chunked_or_missing_length_is_refused_from_the_headers(self):
        # בלי אורך מוצהר, או עם Transfer-Encoding (אז האורך לא אומר כלום): 411 מהכותרות
        start = b"POST /api/convert HTTP/1.1\r\nHost: test\r\nCF-Connecting-IP: 198.51.100.11"
        for head in (start + b"\r\nTransfer-Encoding: chunked", start):
            with self.subTest(head=head[-30:]):
                received, first, closed = self.server.raw(head, wait=5)
                self.assertEqual(status_of(received), 411)
                self.assertLess(first, 2)
                self.assertTrue(closed)

    def test_a_malformed_length_never_reaches_the_app(self):
        # אורך שאינו מספר נדחה כבר ב-h11, ב-400, לפני השירות (נמדד: uvicorn 0.54 עם h11)
        received, first, closed = self.server.raw(b"POST /api/convert HTTP/1.1\r\nHost: test\r\nContent-Length: 12abc",
                                                  wait=5)
        self.assertEqual(status_of(received), 400)
        self.assertLess(first, 2)
        self.assertTrue(closed)

    def test_the_health_route_ignores_a_declared_body(self):
        received, _, _ = self.server.raw(b"GET /healthz HTTP/1.1\r\nHost: test\r\nConnection: close\r\n"
                                         b"Content-Length: " + str(limits.MAX_BYTES * 10).encode(), wait=5)
        self.assertEqual(status_of(received), 200)


class UploadDeadlineTest(unittest.TestCase):
    def test_a_trickling_upload_is_cut(self):
        with Server(HEBREW_PDF_UPLOAD_SECONDS="1") as server:
            head = (b"POST /api/convert HTTP/1.1\r\nHost: test\r\nCF-Connecting-IP: 198.51.100.12\r\n"
                    b"Content-Length: 1000")
            received, first, closed = server.raw(head, b"%PDF-1.7\n", wait=5)
            self.assertEqual(status_of(received), 408)
            self.assertLess(first, 3)
            self.assertTrue(closed)


class FileTypeTest(unittest.TestCase):
    """סוג הקובץ לפי התוכן, ולא לפי Content-Type; קובץ פגום, מוגן בסיסמה, ויותר מדי עמודים."""

    @classmethod
    def setUpClass(cls):
        cls.server = Server().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def test_content_decides_not_the_declared_type(self):
        as_text = self.server.convert(SMALL, ip="198.51.100.20", headers={"Content-Type": "text/plain"})
        self.assertEqual(as_text[0], 200)
        not_pdf = self.server.convert("זה טקסט ולא PDF".encode(), ip="198.51.100.20")
        self.assertEqual((not_pdf[0], body(not_pdf)["error"]), (415, "not_pdf"))

    def test_header_offset_as_in_pdfium(self):
        # PDFium פותח קובץ שהכותרת שלו מתחילה במקום 1024 ולא במקום 1025 (נמדד, web/app.py)
        ok = self.server.convert(b" " * 1024 + SMALL, ip="198.51.100.21")
        self.assertEqual(ok[0], 200)
        late = self.server.convert(b" " * 1025 + SMALL, ip="198.51.100.21")
        self.assertEqual(body(late)["error"], "not_pdf")

    def test_damaged(self):
        response = self.server.convert(b"%PDF-1.7\n" + bytes(range(256)) * 20, ip="198.51.100.22")
        self.assertEqual((response[0], body(response)["error"]), (422, "damaged"))

    def test_password(self):
        response = self.server.convert((ROOT / "tests" / "fixtures" / "protected.pdf").read_bytes(), ip="198.51.100.23")
        self.assertEqual((response[0], body(response)["error"]), (422, "protected"))
        self.assertIn("סיסמה", body(response)["message"])

    def test_too_many_pages(self):
        response = self.server.convert(blank_pdf(limits.MAX_PAGES + 1), ip="198.51.100.24")
        self.assertEqual((response[0], body(response)["error"]), (422, "too_many_pages"))
        self.assertIn(str(limits.MAX_PAGES), body(response)["message"])
        at_limit = self.server.convert(blank_pdf(limits.MAX_PAGES), ip="198.51.100.24")
        self.assertEqual(at_limit[0], 200)
        self.assertEqual(len(body(at_limit)["pages"]), limits.MAX_PAGES)

    def test_error_messages_are_hebrew_and_generic(self):
        response = self.server.convert(b"%PDF-1.7\n garbage", ip="198.51.100.25")
        message = body(response)["message"]
        self.assertTrue(any("א" <= char <= "ת" for char in message))
        for technical in ("Pdfium", "PDFium", "Error", "Traceback", "err_code"):
            self.assertNotIn(technical, message)


class TimeoutStopsTheWorkTest(unittest.TestCase):
    """כשהזמן נגמר התהליך של ההמרה נהרג, ולא רק מפסיקים לחכות לו."""

    def test_the_conversion_process_is_gone(self):
        with Server(HEBREW_PDF_TIMEOUT_SECONDS="2") as server:
            baseline = descendants(server.process.pid)  # שרת התהליכים ו-resource_tracker
            results = []
            worker = threading.Thread(target=lambda: results.append(server.convert(HEAVY, ip="198.51.100.30")))
            began = time.monotonic()
            worker.start()
            # בזמן ההמרה יש צאצא נוסף: כך הבדיקה שאחרי לא מתקיימת סתם
            during = set()
            while worker.is_alive() and not during:
                during = descendants(server.process.pid) - baseline
                time.sleep(0.05)
            self.assertTrue(during, "לא נראה תהליך של המרה בזמן ההמרה")
            worker.join(30)
            elapsed = time.monotonic() - began
            response = results[0]
            self.assertEqual((response[0], body(response)["error"]), (422, "timeout"))
            self.assertLess(elapsed, 10, "ההמרה האיטית לוקחת כ-25 שניות: התשובה הגיעה רק כשהיא נגמרה")
            self.assertEqual(descendants(server.process.pid) - baseline, set(),
                             "התהליך של ההמרה עדיין חי אחרי שהזמן נגמר")
            for pid in during:
                self.assertFalse(os.path.exists(f"/proc/{pid}"), f"התהליך {pid} עדיין קיים")
            # והשרת ממשיך לעבוד: המקום שהתפנה משמש את הבקשה הבאה
            self.assertEqual(server.convert(SMALL, ip="198.51.100.30")[0], 200)


class ConcurrencyTest(unittest.TestCase):
    """כשכל המקומות להמרה תפוסים, בקשה נוספת מקבלת מיד 503 בעברית, ולא נכנסת לתור."""

    def test_parallel_requests(self):
        with Server(HEBREW_PDF_SLOTS="1", HEBREW_PDF_TIMEOUT_SECONDS="8") as server:
            barrier = threading.Barrier(3)
            results: list[tuple[float, tuple]] = []
            lock = threading.Lock()
            began = time.monotonic()

            def send(index: int):
                barrier.wait()
                response = server.convert(HEAVY, ip=f"198.51.100.4{index}")
                with lock:
                    results.append((time.monotonic() - began, response))

            threads = [threading.Thread(target=send, args=(i,)) for i in range(3)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(60)
            outcomes = sorted((response[0], body(response)["error"]) for _, response in results)
            self.assertEqual(outcomes, [(422, "timeout"), (503, "busy"), (503, "busy")])
            busy_times = [elapsed for elapsed, response in results if response[0] == 503]
            winner_time = next(elapsed for elapsed, response in results if response[0] == 422)
            # הדחיות הגיעו בזמן שההמרה הראשונה עוד רצה: הבקשות באמת רצו במקביל
            self.assertTrue(all(elapsed < winner_time - 2 for elapsed in busy_times), (busy_times, winner_time))
            busy = next(response for _, response in results if response[0] == 503)
            self.assertIn("retry-after", busy[1])
            self.assertIn("עמוס", body(busy)["message"])
            # המקום התפנה
            self.assertEqual(server.convert(SMALL, ip="198.51.100.49")[0], 200)


class RateLimitTest(unittest.TestCase):
    """הגבלת קצב לפי הכתובת ש-Cloudflare כותב (CF-Connecting-IP), בבקשות במקביל, ובלי ש-X-Forwarded-For משנה משהו."""

    @classmethod
    def setUpClass(cls):
        cls.server = Server().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def test_parallel_requests_from_one_address(self):
        extra = 10
        statuses = []
        lock = threading.Lock()
        barrier = threading.Barrier(limits.RATE_LIMIT + extra)

        def send(index: int):
            barrier.wait()
            # כל בקשה עם X-Forwarded-For אחר: לקוח שמנסה להיראות כמו הרבה כתובות
            response = self.server.convert(b"x", ip="203.0.113.7", headers={"X-Forwarded-For": f"10.0.0.{index}"})
            with lock:
                statuses.append(response[0])

        threads = [threading.Thread(target=send, args=(i,)) for i in range(limits.RATE_LIMIT + extra)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        self.assertEqual(statuses.count(429), extra)
        self.assertEqual(statuses.count(415), limits.RATE_LIMIT)
        limited = self.server.convert(b"x", ip="203.0.113.7")
        self.assertEqual(limited[0], 429)
        self.assertGreater(int(limited[1]["retry-after"]), 0)
        self.assertIn("דקות", body(limited)["message"])
        # כתובת אחרת לא מושפעת
        self.assertEqual(self.server.convert(b"x", ip="203.0.113.8")[0], 415)

    def test_the_health_route_is_not_limited(self):
        for _ in range(limits.RATE_LIMIT + 5):
            self.assertEqual(self.server.request("GET", "/healthz", headers={"CF-Connecting-IP": "203.0.113.9"})[0], 200)


class HeadersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None, None, None)

    def test_csp_on_every_response(self):
        from web.app import CSP
        for path in ("/", "/static/app.js", "/static/style.css", "/static/icon.svg", "/healthz", "/nothing"):
            with self.subTest(path=path):
                status, headers, _ = self.server.request("GET", path)
                self.assertEqual(headers.get("content-security-policy"), CSP)
                self.assertEqual(headers.get("x-content-type-options"), "nosniff")

    def test_one_csp_header_only(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=10)
        connection.request("GET", "/")
        response = connection.getresponse()
        self.assertEqual(len([v for k, v in response.getheaders() if k.lower() == "content-security-policy"]), 1)
        connection.close()

    def test_results_are_not_cached(self):
        status, headers, _ = self.server.convert(SMALL, ip="198.51.100.60")
        self.assertEqual((status, headers.get("cache-control")), (200, "no-store"))

    def test_no_framework_pages(self):
        for path in ("/docs", "/redoc", "/openapi.json", "/static/../app.py", "/static/index.html"):
            with self.subTest(path=path):
                self.assertEqual(self.server.request("GET", path)[0], 404)

    def test_the_page_shows_the_limits_the_server_enforces(self):
        page = self.server.request("GET", "/")[2].decode("utf-8")
        self.assertIn(f"עד {limits.MAX_BYTES // limits.MB} מגה-בייט, ועד {limits.MAX_PAGES} עמודים", page)
        self.assertIn(f'data-max-bytes="{limits.MAX_BYTES}"', page)
        self.assertNotIn("{{", page)


if __name__ == "__main__":
    unittest.main()
