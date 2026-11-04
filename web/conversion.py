"""המרה של קובץ אחד, בתהליך נפרד שאפשר להרוג.

למה תהליך ולא חוט: ההמרה היא עבודת CPU בקוד C (PDFium) ובפייתון. חוט אי אפשר לעצור מבחוץ, ו-asyncio.wait_for רק
מפסיק לחכות לו: העבודה ממשיכה לאכול מעבד וזיכרון עד שהיא נגמרת. תהליך נהרג ב-SIGKILL, ומערכת ההפעלה משחררת את
כל הזיכרון שלו, כולל מה ש-PDFium הקצה ושום קוד פייתון לא שחרר. ובדרך יש עוד שני רווחים: קובץ עוין שמפיל את
PDFium מפיל רק את התהליך של ההמרה ולא את השרת, והזיכרון של כל המרה חוזר למערכת כשהתהליך נגמר, כך שהשרת לא
מצטבר בגודל מבקשה לבקשה.

למה תהליך חדש לכל המרה ולא מאגר קבוע: מאגר (ProcessPoolExecutor) לא נותן להרוג משימה אחת, רק את כל המאגר, ותהליך
שנשאר חי בין בקשות משאיר את הזיכרון של ההמרה הקודמת אצלו.

שיטת ההפעלה forkserver: תהליך שרת נפרד מתחיל פעם אחת, מייבא מראש את pypdfium2 ואת החבילה (start_worker_server,
set_forkserver_preload), וכל המרה היא fork שלו. כך תהליך חדש עולה במילישניות ולא מייבא הכול מחדש, והוא לא יורש
את לולאת האירועים ואת החוטים של השרת, כמו ש-fork ישיר מהשרת היה יורש. מקור: multiprocessing/forkserver.py
(ensure_running מפעיל את השרת ומייבא את _preload_modules בתוכו; main מייבא אותם; _serve_one מריץ כל תהליך ב-fork).

התקשורת עם התהליך (exchange): שני pipes, אחד לקובץ ואחד לתשובה. multiprocessing רק מעביר אותם לתהליך; את הכתיבה
והקריאה עושה לולאת האירועים, בחלקים ובלי לחסום, וכל ההחלפה (שליחת הקובץ, ההמרה וקבלת התשובה) בתוך הזמן להמרה.
- הקובץ לא עובר בארגומנטים של התהליך: שם multiprocessing כותב אותו ל-pipe ברצף אחד בתוך process.start, כלומר בתוך
  לולאת האירועים, וכל בקשה אחרת מחכה להעתקה (multiprocessing/popen_forkserver.py, _launch).
- התשובה נקראת עד תקרה (limits.MAX_ANSWER): קובץ PDF דחוס יכול להפוך להרבה יותר טקסט מהגודל שלו, ומה שהתהליך כותב
  מגיע לזיכרון של השרת, שאין עליו RLIMIT_AS. מעבר לתקרה הקריאה נעצרת והתהליך נהרג.
- התשובה היא JSON ולא pickle: התהליך הזה מפענח קובץ עוין, ותהליך שהקובץ השתלט עליו (פגיעות ב-PDFium) היה יכול
  לשלוח pickle שמריץ קוד בשרת. JSON הוא נתונים בלבד, והמבנה שלו נבדק לפני שמשתמשים בו (_decode, U3).

פרטיות: הקובץ עובר לתהליך בזיכרון (pipe), ולא נכתב לדיסק. בלוג נכתבים רק סוג הכשל ומיקומים בקוד, בלי הודעת
החריגה, כי הודעה יכולה להכיל טקסט מהקובץ (safe_traceback).
"""

import asyncio
import json
import logging
import multiprocessing
import os
import traceback
from multiprocessing import forkserver

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

from hebrew_pdf.convert import Conversion, convert_document
from hebrew_pdf import score

log = logging.getLogger("web.conversion")

# קודי התוצאה של המרה שנכשלה. הם עוברים בין התהליכים, ומהם נגזרות ההודעה בעברית וקוד ה-HTTP (web/messages.py)
DAMAGED = "damaged"  # PDFium לא הצליח לפתוח או לקרוא את הקובץ
PROTECTED = "protected"  # הקובץ מוצפן בסיסמה, או בשיטת הגנה ש-PDFium לא תומך בה
TOO_MANY_PAGES = "too_many_pages"
TOO_HEAVY = "too_heavy"  # ההמרה עברה את תקרת הזיכרון של התהליך (MemoryError), או שהתשובה גדולה מהתקרה
TIMEOUT = "timeout"  # ההמרה לא הסתיימה בזמן, והתהליך נהרג
CRASHED = "crashed"  # התהליך מת בלי תשובה תקינה (למשל PDFium קרס על הקובץ)
INTERNAL = "internal"  # חריגה לא צפויה בקוד שלנו
FAILURES = (DAMAGED, PROTECTED, TOO_MANY_PAGES, TOO_HEAVY, TIMEOUT, CRASHED, INTERNAL)

# ההחלטות של הציון (score.DECISIONS, בעברית) כקודים יציבים לדף: הדף בוחר לפיהם צבע וסמל, ומציג את הטקסט עצמו
DECISION_CODES = {score.OK: "ok", score.UNSURE: "unsure", score.REJECTED: "rejected"}

_CONTEXT = multiprocessing.get_context("forkserver")
# גודל חלק בכתיבה לתהליך ובקריאה ממנו: כגודל ה-pipe בלינוקס (pipe(7)), וכסף בקרת הזרימה של asyncio (64KB,
# asyncio/transports.py, _FlowControlMixin)
_CHUNK = 64 * 1024


class ConversionFailed(Exception):
    """ההמרה לא החזירה תוצאה. code: אחד מ-FAILURES."""

    def __init__(self, code: str):
        if code not in FAILURES:
            raise ValueError(f"קוד כשל לא מוכר: {code}")
        super().__init__(code)
        self.code = code


def start_worker_server() -> None:
    """מפעיל את שרת התהליכים ומייבא בו את המודול הזה (ואיתו pypdfium2 והחבילה), כדי שההמרה הראשונה לא תשלם על
    זה. נקרא פעם אחת בעליית השירות (web/app.py, lifespan). בלי הקריאה הזו השרת עולה בהמרה הראשונה, בלי ייבוא מראש."""
    _CONTEXT.set_forkserver_preload([__name__])
    forkserver.ensure_running()


# ---------- בתוך התהליך של ההמרה ----------

def safe_traceback(error: BaseException) -> str:
    """סוג החריגה והמיקומים בקוד (קובץ, שורה, פונקציה), בלי ההודעה שלה ובלי ערכים: הודעה של חריגה יכולה להכיל
    טקסט מהקובץ שהמשתמש העלה (bugbot-rules/pii-in-logs.md). מספיק כדי למצוא את הבאג, ולא מספיק כדי לשחזר תוכן."""
    frames = traceback.extract_tb(error.__traceback__)
    where = " <- ".join(f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno} {frame.name}" for frame in reversed(frames))
    return f"{type(error).__name__} at {where or 'unknown'}"


def payload(conversion: Conversion) -> dict:
    """התוצאה כמבנה שעובר בין התהליכים ונשלח לדף כ-JSON: ה-Markdown, ולכל עמוד ההחלטה, הסיבות, ההערות, והשורה
    ב-Markdown שבה נמצא הסמן שלו. המבנה נבדק בשרת לפני שמשתמשים בו (valid_result).

    השורה ולא המקום בתווים: בפייתון אינדקס הוא תו (code point), וב-JavaScript הוא יחידה של UTF-16, ולכן אימוג'י
    אחד מזיז כל מקום שאחריו באחד. מספר שורה (כמה "\\n" לפני הסמן) זהה בשני הצדדים, כי הדף מפצל רק לפי "\\n".
    ההערות הן רשימה של הערות נפרדות, ולא משפט אחד לעמוד."""
    text = conversion.markdown.text
    pages = []
    for number, (page_score, offset) in enumerate(zip(conversion.scores, conversion.markdown.page_offsets, strict=True), 1):
        pages.append({
            "number": number,
            "decision": DECISION_CODES[page_score.decision],
            "decision_text": page_score.decision,
            "reasons": [{"kind": reason.kind, "text": reason.text} for reason in page_score.reasons],
            "notes": [{"kind": note.kind, "text": note.text} for note in page_score.notes],
            "line": text.count("\n", 0, offset),
        })
    return {"markdown": text, "pages": pages}


def outcome(data: bytes, max_pages: int) -> dict:
    """פותח את הקובץ, בודק את מספר העמודים לפני ההמרה, וממיר. {"result": payload} או {"error": קוד}.

    PdfiumError בפתיחה: err_code הוא FPDF_GetLastError (pypdfium2/_helpers/document.py, _open_pdf). סיסמה או שיטת
    הגנה שלא נתמכת (FPDF_ERR_PASSWORD, FPDF_ERR_SECURITY) הם קובץ מוגן; כל השאר, וגם מסמך בלי עמודים, פגום.
    PdfiumError בזמן הקריאה עצמה הוא עמוד ש-PDFium לא הצליח לקרוא, כלומר גם הוא קובץ פגום. כל חריגה אחרת עולה:
    היא באג אצלנו ולא תכונה של הקובץ (child_main)."""
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        protected = error.err_code in (pdfium_raw.FPDF_ERR_PASSWORD, pdfium_raw.FPDF_ERR_SECURITY)
        return {"error": PROTECTED if protected else DAMAGED}
    with pdf:
        if len(pdf) > max_pages:
            return {"error": TOO_MANY_PAGES}
        try:
            conversion = convert_document(pdf)
        except pdfium.PdfiumError:
            return {"error": DAMAGED}
    return {"result": payload(conversion)}


def read_input(source) -> bytes:
    """הקובץ מהשרת, עד סוף ה-pipe (השרת סוגר אותו אחרי הבית האחרון)."""
    parts = []
    while chunk := os.read(source.fileno(), _CHUNK):
        parts.append(chunk)
    source.close()
    return b"".join(parts)


def encode_answer(result: dict) -> bytes:
    return json.dumps(result, ensure_ascii=False).encode("utf-8")


def write_answer(answer, encoded: bytes) -> None:
    """התשובה לשרת, ואחריה סוף ה-pipe. השרת שהפסיק לקרוא (התשובה גדולה מהתקרה, או שהזמן נגמר וההרג בדרך) הוא
    BrokenPipeError כאן: אין למי לענות, והתהליך פשוט נגמר."""
    view = memoryview(encoded)
    try:
        while view:
            view = view[os.write(answer.fileno(), view):]
    except BrokenPipeError:
        pass  # השרת סגר את הקריאה בכוונה (ראו למעלה), ואת הכשל עצמו הוא כבר רשם
    finally:
        answer.close()


def child_main(source, answer, max_pages: int, memory_limit: int | None) -> None:
    """נקודת הכניסה של התהליך. גבול של תהליך: כל חריגה נתפסת כאן ונשלחת כקוד, כדי שלא תודפס עם ההודעה שלה ל-stderr
    (ברירת המחדל של multiprocessing), ולוג שלה נכתב בלי תוכן. MemoryError הוא תקרת הזיכרון שהוצבה כאן ולא באג,
    ולכן יש לו קוד משלו. התקרה מוצבת לפני קריאת הקובץ, כך שגם הקובץ וגם קידוד התשובה בתוכה."""
    try:
        if memory_limit is not None:
            _limit_memory(memory_limit)
        encoded = encode_answer(outcome(read_input(source), max_pages))
    except MemoryError:
        encoded = encode_answer({"error": TOO_HEAVY})
    except Exception as error:  # גבול התהליך: כל באג הופך לקוד INTERNAL, עם מיקום בלוג ובלי תוכן
        log.error("conversion failed: %s", safe_traceback(error))
        encoded = encode_answer({"error": INTERNAL})
    write_answer(answer, encoded)


def _limit_memory(limit: int) -> None:
    """תקרה על הזיכרון הווירטואלי של התהליך (RLIMIT_AS). מעבר לה הקצאה נכשלת: בפייתון כ-MemoryError, וב-PDFium
    כקריסה של התהליך, שמגיעה לשרת כ-CRASHED. כך המרה אחת כבדה מהצפוי נכשלת לבד, ולא מפילה את השירות כולו כשהיא
    עוברת את הזיכרון שלו. מקור: resource.setrlimit (תיעוד הספרייה הסטנדרטית), RLIMIT_AS."""
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


# ---------- בתהליך של השרת ----------

async def convert(data, *, max_pages: int, timeout: float, memory_limit: int | None, max_answer: int) -> dict:
    """ממיר את הקובץ (bytes או bytearray) בתהליך חדש ומחזיר את payload. זורקת ConversionFailed (עם קוד מ-FAILURES)
    בכל כשל; אין ערך החזרה שמסמן כשל.

    הזמן חל על כל ההחלפה: שליחת הקובץ, ההמרה וקבלת התשובה. כשהוא נגמר, או כשהתשובה עוברת את max_answer, התהליך
    נהרג (SIGKILL) לפני שהפונקציה חוזרת, וגם כשהקורא מבוטל: העבודה לא ממשיכה ברקע."""
    raw = await exchange(child_main, data, (max_pages, memory_limit), timeout=timeout, max_answer=max_answer)
    return _decode(raw)


async def exchange(target, data, args: tuple, *, timeout: float, max_answer: int) -> bytes:
    """מריץ את target(source, answer, *args) בתהליך חדש, שולח לו את data, ומחזיר את מה שהוא כתב, עד max_answer בתים.
    משמש גם את המדידה (web/measure.py), כדי שתמדוד את אותו מסלול."""
    child_reads, to_child = _CONTEXT.Pipe(duplex=False)
    from_child, child_writes = _CONTEXT.Pipe(duplex=False)
    process = _CONTEXT.Process(target=target, args=(child_reads, child_writes, *args), daemon=True)
    try:
        process.start()
    except BaseException:
        to_child.close()
        from_child.close()
        raise
    finally:
        # לתהליך יש עותקים משלו. בלי לסגור את שלנו, הוא לא היה רואה את סוף הקובץ, ותהליך שמת לא היה נראה כסוף התשובה
        child_reads.close()
        child_writes.close()
    loop = asyncio.get_running_loop()
    writing, sender = await loop.connect_write_pipe(lambda: _Sender(loop), _own(to_child, "wb"))
    reading, receiver = await loop.connect_read_pipe(lambda: _Receiver(loop, max_answer), _own(from_child, "rb"))
    try:
        async with asyncio.timeout(timeout):
            await _send(writing, sender, data)
            raw = await receiver.done
    except TimeoutError:
        raise ConversionFailed(TIMEOUT) from None
    finally:
        # כל תעבורה סוגרת את הקובץ שלה, ורק אם היא עוד לא נסגרת: קריאה שנייה הייתה מגיעה ל-pipe שכבר נסגר
        # (asyncio/unix_events.py, _call_connection_lost). בכתיבה abort, שזורק את מה שעוד בתור; לקריאה יש רק close
        if not writing.is_closing():
            writing.abort()
        if not reading.is_closing():
            reading.close()
        await _stop(process)
    if raw is None:
        log.warning("התשובה של תהליך ההמרה גדולה מ-%d בתים", max_answer)
        raise ConversionFailed(TOO_HEAVY)
    return raw


def _own(connection, mode: str):
    """הקצה של ה-pipe כקובץ שלנו, ללולאת האירועים: עותק של ה-fd, והחיבור של multiprocessing נסגר."""
    fd = os.dup(connection.fileno())
    connection.close()
    return os.fdopen(fd, mode, buffering=0)


class _Sender(asyncio.Protocol):
    """בקרת הזרימה של הכתיבה לתהליך: התעבורה קוראת ל-pause_writing כשיש בתור יותר מ-64KB, ול-resume_writing כשהוא
    מתרוקן (asyncio/transports.py, _FlowControlMixin). כך בתור יש חלק אחד או שניים, ולא עותק של הקובץ כולו."""

    def __init__(self, loop):
        self._loop = loop
        self._resumed: asyncio.Future | None = None
        self.lost = False
        self.closed = loop.create_future()

    def pause_writing(self):
        self._resumed = self._loop.create_future()

    def resume_writing(self):
        self._wake()

    def connection_lost(self, exc):
        # התהליך סגר את הצד שלו או מת. זה לא כשל של השליחה: מה שקרה לו נראה בתשובה (_Receiver, _decode)
        self.lost = True
        self._wake()
        if not self.closed.done():
            self.closed.set_result(None)

    def _wake(self):
        if self._resumed is not None and not self._resumed.done():
            self._resumed.set_result(None)
        self._resumed = None

    async def writable(self) -> bool:
        if self._resumed is not None:
            await self._resumed
        return not self.lost


async def _send(transport, sender: _Sender, data) -> None:
    view = memoryview(data)
    for start in range(0, len(view), _CHUNK):
        if not await sender.writable():
            break
        transport.write(view[start:start + _CHUNK])
    transport.close()  # נסגר אחרי שהתור נשלח, והתהליך רואה את סוף הקובץ
    await sender.closed


class _Receiver(asyncio.Protocol):
    """אוסף את התשובה עד התקרה. מעבר לה מפסיק לקבל וסוגר, והתוצאה None."""

    def __init__(self, loop, limit: int):
        self.limit = limit
        self.size = 0
        self.parts: list[bytes] = []
        self.done = loop.create_future()

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.size += len(data)
        if self.size > self.limit:
            self.parts.clear()
            if not self.done.done():
                self.done.set_result(None)
            self.transport.close()
            return
        self.parts.append(data)

    def connection_lost(self, exc):
        # סוף ה-pipe: התהליך סיים לכתוב, או מת באמצע. תשובה חלקית תיכשל בפענוח (_decode)
        if not self.done.done():
            self.done.set_result(b"".join(self.parts))


def _decode(raw: bytes) -> dict:
    """התשובה של התהליך, אחרי בדיקה של המבנה. תהליך שמת בלי לכתוב (תשובה ריקה), או באמצע (JSON חלקי), או תשובה
    שהמבנה שלה לא תקין, הם CRASHED. הפענוח רץ בלולאת האירועים, והוא חסום בגודל: עד limits.MAX_ANSWER."""
    if not raw:
        raise ConversionFailed(CRASHED)
    try:
        answer = json.loads(raw)
    except ValueError:  # כולל UnicodeDecodeError: תשובה שנקטעה באמצע תו
        raise ConversionFailed(CRASHED) from None
    if not isinstance(answer, dict):
        raise ConversionFailed(CRASHED)
    if "error" in answer:
        code = answer["error"]
        raise ConversionFailed(code if isinstance(code, str) and code in FAILURES else CRASHED)
    result = answer.get("result")
    if not valid_result(result):
        log.warning("תשובה לא תקינה מתהליך ההמרה")
        raise ConversionFailed(CRASHED)
    return result


def valid_result(result) -> bool:
    """המבנה של payload, שדה שדה: מה שהשרת ניגש אליו (web/messages.py, explained) ומה שהדף מציג."""
    if not isinstance(result, dict) or not isinstance(result.get("markdown"), str):
        return False
    pages = result.get("pages")
    if not isinstance(pages, list):
        return False
    codes = set(DECISION_CODES.values())
    for number, page in enumerate(pages, 1):
        if not (isinstance(page, dict) and page.get("number") == number and isinstance(page.get("line"), int)
                and isinstance(page.get("decision"), str) and page["decision"] in codes
                and isinstance(page.get("decision_text"), str)
                and _entries(page.get("reasons"), score.REASON_KINDS) and _entries(page.get("notes"), score.NOTE_KINDS)):
            return False
    return True


def _entries(entries, kinds: dict) -> bool:
    return isinstance(entries, list) and all(
        isinstance(entry, dict) and isinstance(entry.get("kind"), str) and entry["kind"] in kinds
        and isinstance(entry.get("text"), str) for entry in entries)


async def _stop(process) -> int | None:
    """הורג את התהליך אם הוא עדיין חי, מחכה שייגמר בלי לחסום את הלולאה, ומחזיר את קוד היציאה שלו. process.sentinel
    נהיה קריא כששרת התהליכים כותב את קוד היציאה (multiprocessing/popen_forkserver.py, poll), ואז join חוזר מיד.

    תהליך שמת מעצמו בקוד שאינו 0 נרשם בלוג עם הקוד, כי CRASHED מכסה שני מקרים שונים: תחת תקרת הזיכרון PDFium מפיל
    את התהליך ב-SIGABRT ולא זורק MemoryError (נמדד: הדוח הכספי עם תקרה של 90MB יוצא ב-6-), וקובץ שמפיל את PDFium
    מסיבה אחרת. ההודעה למשתמש מכסה את שניהם (web/messages.py), והקוד בלוג מבדיל."""
    killed = process.is_alive()
    if killed:
        process.kill()
    await _readable(process.sentinel)
    process.join()
    exitcode = process.exitcode
    process.close()
    if not killed and exitcode not in (0, None):
        log.warning("תהליך ההמרה מת בקוד יציאה %s", exitcode)
    return exitcode


async def _readable(fd: int) -> None:
    loop = asyncio.get_running_loop()
    ready = loop.create_future()
    loop.add_reader(fd, _set_ready, ready)
    try:
        await ready
    finally:
        loop.remove_reader(fd)


def _set_ready(ready: asyncio.Future) -> None:
    if not ready.done():
        ready.set_result(None)
