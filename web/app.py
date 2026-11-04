"""השירות: דף אחד בעברית, וראוט אחד שממיר PDF ל-Markdown עם החלטה, סיבות והערות לכל עמוד.

הדפים שנגישים בלי התחברות, כולם (השירות ציבורי בכוונה, ואין בו שום פעולת ניהול או כתיבה):
    GET  /               הדף (web/static/index.html)
    GET  /static/<שם>    הקבצים של הדף: app.js, style.css, icon.svg, ותו לא
    GET  /healthz        בדיקת הדופק של Render
    POST /api/convert    גוף הבקשה הוא הקובץ עצמו (application/pdf), לא טופס
ו-FastAPI לא מגיש את /docs, /redoc ו-/openapi.json (docs_url=None וכו'): הם דפים ציבוריים נוספים, שטוענים סקריפט
ממקור חיצוני.

למה הקובץ נשלח כגוף הבקשה ולא כטופס (multipart): ב-Starlette קובץ בטופס שגדול מ-1MB נכתב לקובץ זמני בדיסק
(starlette/formparsers.py, MultiPartParser.spool_max_size ו-SpooledTemporaryFile). כאן הקובץ נשאר בזיכרון בלבד,
ו-python-multipart לא נדרש.

הסדר בראוט, מהזול ליקר, וכל שלב דוחה לפני הבא (bugbot-rules/body-read-outside-cheap-reject.md):
1. הגבלת קצב לפי הכתובת (client_address). לא נקרא שום בית מהגוף.
2. אורך מוצהר: בלי Content-Length, או עם Transfer-Encoding לידו (אז האורך לא אומר כלום), נדחה ב-411; מעל
   MAX_BYTES נדחה ב-413. מהכותרות בלבד, ועם Connection: close, כי הגוף לא נקרא.
3. עומס: כשכל המקומות להמרה תפוסים, או שכבר יש יותר מדי קבצים בדרך, 503 מיד, ולא תור שגדל.
4. קריאת הגוף, עד האורך המוצהר ובתוך UPLOAD_SECONDS.
5. סוג הקובץ לפי התוכן: הכותרת %PDF- עד מקום 1024, כמו ש-PDFium מחפש אותה (נמדד על pypdfium2 5.13: הכותרת
   במקום 1024 נפתחת, במקום 1025 לא). לא לפי השם ולא לפי Content-Type, שהדפדפן קובע.
6. ההמרה, בתהליך נפרד, עם זמן ותקרת זיכרון (web/conversion.py). מספר העמודים נבדק שם מיד אחרי הפתיחה.

פרטיות: הקובץ לא נשמר, ובלוג אין שום דבר ממנו: לא שם (השם לא מגיע לשרת בכלל; הדף גוזר ממנו את שם ההורדה
בעצמו), לא טקסט ולא קטעים מה-Markdown. בלוג: קוד התוצאה, גודל בבתים, מספר עמודים וזמן.
"""

import asyncio
import ipaddress
import logging
import math
import os
import re
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.requests import ClientDisconnect

from web import conversion, limits, messages

log = logging.getLogger("web.app")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# הכתובת של הלקוח: Cloudflare, שעומד לפני כל שירות ציבורי ב-Render, כותב את הכותרת הזו בכל בקשה ודורס את מה שהלקוח
# שלח. X-Forwarded-For לא: Cloudflare מוסיף לו ולא מחליף, ולכן הכתובת הראשונה בו היא מה שהלקוח כתב
# (https://render.com/articles/host-pocketbase-on-render, הסעיף על CF-Connecting-IP). ולכן גם uvicorn רץ בלי
# proxy_headers (web/__main__.py): ב-forwarded_allow_ips="*" הוא לוקח את הכתובת השמאלית ב-X-Forwarded-For
# (uvicorn/middleware/proxy_headers.py, get_trusted_client_address)
CLIENT_IP_HEADER = "cf-connecting-ip"

# הכותרות שכל תשובה מקבלת, אם ה-handler לא קבע אחרת (SecurityHeaders). ה-CSP: הדף לא טוען כלום ממקור חיצוני.
# default-src 'none': כל סוג משאב שלא מותר כאן במפורש חסום. מה שהדף כן צריך: סקריפט, סגנון ואייקון מהשירות עצמו,
#   ו-fetch לראוט של ההמרה. משאב חדש מקבל היתר כאן, להנחיה שלו בלבד.
# form-action 'none': בדף אין טופס שנשלח; הקובץ נשלח ב-fetch. טופס שיתווסף יקבל 'self' בתשובה של הדף שלו בלבד.
# frame-ancestors 'none': אין הטמעה של הדף באתר אחר. אם CodeBot יטמיע אותו, ההיתר יינתן בתשובה של הדף.
# base-uri 'none': לדף אין <base>.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}

_DIGITS = re.compile(r"[0-9]{1,20}")
_PDF_HEADER = b"%PDF-"
_PDF_HEADER_LAST_OFFSET = 1024


def is_pdf(data: bytes) -> bool:
    """הכותרת %PDF- מתחילה במקום 0 עד 1024 בקובץ (ראו בראש הקובץ, שלב 5)."""
    return data.find(_PDF_HEADER, 0, _PDF_HEADER_LAST_OFFSET + len(_PDF_HEADER)) != -1


class SecurityHeaders:
    """מוסיף את SECURITY_HEADERS לכל תשובה, רק כשהכותרת חסרה: ה-handler רץ קודם, ומה שהוא קבע נשאר
    (BY-STACK/browser-policy.md, B1). ASGI טהור ולא BaseHTTPMiddleware: הוא לא נוגע בגוף הבקשה."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers += [(name.encode(), value.encode()) for name, value in SECURITY_HEADERS.items()
                            if name.encode() not in present]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RateLimiter:
    """חלון נע לכל מפתח (כתובת): עד limit בקשות ב-window שניות. בזיכרון של התהליך, ולכן השירות רץ בעובד אחד
    (web/__main__.py). מספר המפתחות חסום ב-max_keys: כשהוא מלא יורדים קודם מפתחות שכל הבקשות שלהם כבר מחוץ לחלון,
    ואחר כך הישן ביותר, כך שהזיכרון חסום גם מול הרבה כתובות."""

    def __init__(self, limit: int, window: float, max_keys: int = 50_000, clock=time.monotonic):
        self.limit, self.window, self.max_keys, self.clock = limit, window, max_keys, clock
        self._hits: OrderedDict[str, deque] = OrderedDict()

    def hit(self, key: str) -> float | None:
        """רושם בקשה. None: מותרת. אחרת: כמה שניות עד שתתפנה בקשה בחלון (לכותרת Retry-After)."""
        now = self.clock()
        times = self._hits.get(key)
        if times is None:
            if len(self._hits) >= self.max_keys:
                self._evict(now)
            times = self._hits[key] = deque()
        while times and times[0] <= now - self.window:
            times.popleft()
        if len(times) >= self.limit:
            return times[0] + self.window - now
        times.append(now)
        self._hits.move_to_end(key)
        return None

    def _evict(self, now: float) -> None:
        for key in [key for key, times in self._hits.items() if not times or times[-1] <= now - self.window]:
            del self._hits[key]
        while len(self._hits) >= self.max_keys:
            self._hits.popitem(last=False)


class Slots:
    """מקומות פנויים. בלולאת אירועים אחת אין await בין הבדיקה לתפיסה, ולכן אין מרוץ בין בקשות."""

    def __init__(self, size: int):
        self.size = size
        self.used = 0

    def free(self) -> bool:
        return self.used < self.size

    def take(self) -> bool:
        if not self.free():
            return False
        self.used += 1
        return True

    def give(self) -> None:
        if self.used <= 0:
            raise RuntimeError("שחרור של מקום שלא נתפס")
        self.used -= 1


_missing_header_logged = False


def client_address(request: Request) -> str:
    """הכתובת של הלקוח להגבלת הקצב (CLIENT_IP_HEADER). כשהכותרת חסרה או לא כתובת, הכתובת של מי שהתחבר: ב-Render זו
    הכתובת של הפרוקסי, ואז כל המשתמשים חולקים מגבלה אחת. זה מחמיר ולא מקל, ונרשם בלוג פעם אחת."""
    global _missing_header_logged
    value = request.headers.get(CLIENT_IP_HEADER)
    if value is not None:
        try:
            return str(ipaddress.ip_address(value.strip()))
        except ValueError:
            pass  # כתובת לא תקינה בכותרת: כמו כותרת חסרה, למטה
    if not _missing_header_logged:
        _missing_header_logged = True
        log.warning("אין כתובת תקינה ב-%s; הגבלת הקצב לפי הכתובת שהתחברה", CLIENT_IP_HEADER)
    return request.client.host if request.client else "unknown"


def failure(code: str, *, close: bool = False, retry_after: float | None = None) -> JSONResponse:
    """תשובת שגיאה: הקוד וההודעה בעברית (web/messages.py). close: הגוף לא נקרא, והחיבור נסגר אחרי התשובה, כדי
    שהשרת לא ימשיך לקבל את שאר הקובץ."""
    status, text = messages.error(code)
    headers = {"cache-control": "no-store"}
    if close:
        headers["connection"] = "close"
    if retry_after is not None:
        headers["retry-after"] = str(max(1, math.ceil(retry_after)))
    return JSONResponse({"error": code, "message": text}, status_code=status, headers=headers)


class _BadUpload(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def read_body(request: Request, length: int, deadline: float) -> bytes:
    """הגוף, בדיוק length בתים, בתוך deadline שניות לכל הקריאה (ולא לכל חלק: לקוח שמטפטף בית לפני כל דדליין היה
    עובר דדליין לחלק). _BadUpload: upload_timeout כשהזמן נגמר, bad_request כשהגוף קצר או ארוך מהמוצהר או שהלקוח
    התנתק."""
    chunks: list[bytes] = []
    received = 0
    try:
        async with asyncio.timeout(deadline):
            async for chunk in request.stream():
                received += len(chunk)
                if received > length:
                    raise _BadUpload("bad_request")
                chunks.append(chunk)
    except TimeoutError:
        raise _BadUpload("upload_timeout") from None
    except ClientDisconnect:
        raise _BadUpload("bad_request") from None
    if received != length:
        raise _BadUpload("bad_request")
    return b"".join(chunks)


def _page(path: Path) -> bytes:
    """index.html, עם המגבלות עצמן במקום הסימנים: אותו מקור שהשרת אוכף (web/limits.py), ולא עותק בדף."""
    text = path.read_text(encoding="utf-8")
    for name, value in (("{{MAX_MB}}", limits.MAX_BYTES // limits.MB), ("{{MAX_PAGES}}", limits.MAX_PAGES),
                        ("{{MAX_BYTES}}", limits.MAX_BYTES)):
        if name not in text:
            raise RuntimeError(f"{path.name}: חסר {name}")
        text = text.replace(name, str(value))
    return text.encode("utf-8")


STATIC_TYPES = {"app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8",
                "icon.svg": "image/svg+xml"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    environ = os.environ
    capacity = limits.capacity(environ)
    app.state.slots = Slots(capacity.slots)
    app.state.uploads = Slots(capacity.slots * limits.UPLOADS_PER_SLOT)
    app.state.timeout = limits.seconds_from(environ, "HEBREW_PDF_TIMEOUT_SECONDS", limits.TIMEOUT_SECONDS, 0.1, 600)
    app.state.upload_timeout = limits.seconds_from(environ, "HEBREW_PDF_UPLOAD_SECONDS", limits.UPLOAD_SECONDS, 0.1, 600)
    app.state.limiter = RateLimiter(limits.RATE_LIMIT, limits.RATE_WINDOW_SECONDS)
    app.state.index = _page(STATIC_DIR / "index.html")
    app.state.static = {name: (STATIC_DIR / name).read_bytes() for name in STATIC_TYPES}
    conversion.start_worker_server()
    # שורת הקיבולת קוראת את מה שהותקן, ולא מחשבת מחדש (RECURRING-PATTERNS.md, R6)
    log.info("המרות במקביל: %d (%s); קבצים בדרך: %d; זמן להמרה: %ss; תקרת זיכרון להמרה: %dMB",
             app.state.slots.size, capacity.source, app.state.uploads.size, app.state.timeout,
             limits.CONVERSION_MEMORY // limits.MB)
    yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(SecurityHeaders)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/")
async def index(request: Request):
    return Response(request.app.state.index, media_type="text/html; charset=utf-8",
                    headers={"cache-control": "no-cache"})


@app.get("/static/{name}")
async def static(name: str, request: Request):
    content = request.app.state.static.get(name)
    if content is None:
        return Response(status_code=404)
    return Response(content, media_type=STATIC_TYPES[name], headers={"cache-control": "no-cache"})


@app.post("/api/convert")
async def convert(request: Request):
    state = request.app.state
    wait = state.limiter.hit(client_address(request))
    if wait is not None:
        return failure("rate_limited", close=True, retry_after=wait)
    declared = request.headers.get("content-length")
    if "transfer-encoding" in request.headers or declared is None or not _DIGITS.fullmatch(declared):
        return failure("length_required", close=True)
    length = int(declared)
    if length > limits.MAX_BYTES:
        return failure("too_large", close=True)
    if not state.slots.free() or not state.uploads.take():
        return failure("busy", close=True, retry_after=30)
    try:
        data = await read_body(request, length, state.upload_timeout)
    except _BadUpload as bad:
        return failure(bad.code, close=True)
    finally:
        state.uploads.give()
    if not is_pdf(data):
        return failure("not_pdf")
    if not state.slots.take():
        return failure("busy", retry_after=30)
    started = time.monotonic()
    try:
        result = await conversion.convert(data, max_pages=limits.MAX_PAGES, timeout=state.timeout,
                                          memory_limit=limits.CONVERSION_MEMORY)
    except conversion.ConversionFailed as failed:
        log.info("המרה: %s, %d בתים, %.1f שניות", failed.code, length, time.monotonic() - started)
        return failure(failed.code)
    finally:
        state.slots.give()
    log.info("המרה: ok, %d בתים, %d עמודים, %.1f שניות", length, len(result["pages"]), time.monotonic() - started)
    return JSONResponse(messages.explained(result), headers={"cache-control": "no-store"})
