"""שרת אמיתי של השירות, לבדיקות: python -m web בתהליך נפרד, באותה תצורה שרצה ב-Render (web/__main__.py: uvicorn
עם h11, בלי proxy headers, עובד אחד, וההמרות בתהליכים של forkserver). הבדיקות פונות אליו ב-HTTP אמיתי, כי מה
שנבדק כאן הוא הסדר בין השכבות ומה שקורה לחיבור (TESTING-PATTERNS.md, T1(e)): TestClient לא עובר דרך uvicorn.

משתני הסביבה שבדיקה יכולה לקבוע הם אלה שהשירות עצמו מקבל (web/limits.py): HEBREW_PDF_SLOTS,
HEBREW_PDF_TIMEOUT_SECONDS ו-HEBREW_PDF_UPLOAD_SECONDS. כל השאר כמו בייצור.
"""

import http.client
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDFS = ROOT / "testset" / "pdfs"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def descendants(pid: int) -> set[int]:
    """כל הצאצאים של תהליך, לפי /proc/<pid>/stat (השדה הרביעי הוא ההורה, proc(5))."""
    parents: dict[int, int] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
        except OSError:
            continue  # התהליך נגמר בזמן הסריקה: הוא כבר לא צאצא
        # השם בסוגריים יכול להכיל רווחים, ולכן מפרקים אחרי הסוגר האחרון
        parents[int(entry.name)] = int(stat.rsplit(")", 1)[1].split()[1])
    found: set[int] = set()
    frontier = {pid}
    while frontier:
        children = {child for child, parent in parents.items() if parent in frontier}
        frontier = children - found
        found |= children
    return found


class Server:
    def __init__(self, **env: str):
        self.env = env
        self.port = free_port()
        self.process: subprocess.Popen | None = None
        self.log = tempfile.TemporaryFile()

    def __enter__(self) -> "Server":
        env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(self.port), **self.env}
        for name in ("HEBREW_PDF_SLOTS", "HEBREW_PDF_TIMEOUT_SECONDS", "HEBREW_PDF_UPLOAD_SECONDS"):
            if name not in self.env:
                env.pop(name, None)
        self.process = subprocess.Popen([sys.executable, "-m", "web"], cwd=ROOT, env=env, stdout=self.log,
                                        stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"השרת לא עלה:\n{self.output()}")
            try:
                if self.request("GET", "/healthz")[0] == 200:
                    return self
            except OSError:
                time.sleep(0.1)  # עוד לא מאזין
        raise RuntimeError(f"השרת לא ענה תוך 30 שניות:\n{self.output()}")

    def __exit__(self, *exc) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.log.close()

    def output(self) -> str:
        self.log.seek(0)
        return self.log.read().decode("utf-8", "replace")

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None,
                timeout: float = 120) -> tuple[int, dict, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
        finally:
            connection.close()

    def convert(self, data: bytes, ip: str = "198.51.100.1", headers: dict | None = None,
                timeout: float = 120) -> tuple[int, dict, bytes]:
        """POST /api/convert, כמו שהדף שולח: הקובץ כגוף הבקשה. ip: הכתובת שהבדיקה כותבת ב-CF-Connecting-IP, בתפקיד
        של Cloudflare, כדי שכל בדיקה תספור בהגבלת הקצב לבד."""
        return self.request("POST", "/api/convert", data,
                            {"Content-Type": "application/pdf", "CF-Connecting-IP": ip, **(headers or {})}, timeout)

    def raw(self, head: bytes, body: bytes = b"", wait: float = 5.0) -> tuple[bytes, float, bool]:
        """בקשה ידנית בשקע: head (שורת הבקשה והכותרות, בלי השורה הריקה שבסוף) ו-body. מחזירה את מה שהתקבל, כמה זמן
        עבר עד הבית הראשון של התשובה (או wait כשלא הגיעה תשובה), והאם השרת סגר את החיבור."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=wait) as sock:
            began = time.monotonic()
            sock.sendall(head + b"\r\n\r\n" + body)
            received = b""
            first = None
            closed = False
            try:
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        closed = True
                        break
                    if first is None:
                        first = time.monotonic() - began
                    received += chunk
            except TimeoutError:
                pass  # השרת לא סגר בזמן: מה שהתקבל עד עכשיו הוא התשובה
            return received, first if first is not None else wait, closed
