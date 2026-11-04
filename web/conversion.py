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

פרטיות: הקובץ עובר לתהליך בזיכרון (pipe), ולא נכתב לדיסק. בלוג נכתבים רק סוג הכשל ומיקומים בקוד, בלי הודעת
החריגה, כי הודעה יכולה להכיל טקסט מהקובץ (safe_traceback).
"""

import asyncio
import logging
import multiprocessing
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
TOO_HEAVY = "too_heavy"  # ההמרה עברה את תקרת הזיכרון של התהליך (MemoryError)
TIMEOUT = "timeout"  # ההמרה לא הסתיימה בזמן, והתהליך נהרג
CRASHED = "crashed"  # התהליך מת בלי תשובה (למשל PDFium קרס על הקובץ)
INTERNAL = "internal"  # חריגה לא צפויה בקוד שלנו
FAILURES = (DAMAGED, PROTECTED, TOO_MANY_PAGES, TOO_HEAVY, TIMEOUT, CRASHED, INTERNAL)

# ההחלטות של הציון (score.DECISIONS, בעברית) כקודים יציבים לדף: הדף בוחר לפיהם צבע וסמל, ומציג את הטקסט עצמו
DECISION_CODES = {score.OK: "ok", score.UNSURE: "unsure", score.REJECTED: "rejected"}

_CONTEXT = multiprocessing.get_context("forkserver")


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
    ב-Markdown שבה נמצא הסמן שלו.

    השורה ולא המקום בתווים: בפייתון אינדקס הוא תו (code point), וב-JavaScript הוא יחידה של UTF-16, ולכן אימוג'י
    אחד מזיז כל מקום שאחריו באחד. מספר שורה (כמה "\\n" לפני הסמן) זהה בשני הצדדים, כי הדף מפצל רק לפי "\\n".
    ההערות הן רשימה של הערות נפרדות, ולא משפט אחד לעמוד, כדי שהערה שמצביעה על שורה (סבב 7) תיכנס בלי לשנות את המבנה."""
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


def child_main(data: bytes, max_pages: int, memory_limit: int | None, sender) -> None:
    """נקודת הכניסה של התהליך. גבול של תהליך: כל חריגה נתפסת כאן ונשלחת כקוד, כדי שלא תודפס עם ההודעה שלה ל-stderr
    (ברירת המחדל של multiprocessing), ולוג שלה נכתב בלי תוכן. MemoryError הוא תקרת הזיכרון שהוצבה כאן ולא באג,
    ולכן יש לו קוד משלו."""
    try:
        if memory_limit is not None:
            _limit_memory(memory_limit)
        result = outcome(data, max_pages)
    except MemoryError:
        result = {"error": TOO_HEAVY}
    except Exception as error:  # גבול התהליך: כל באג הופך לקוד INTERNAL, עם מיקום בלוג ובלי תוכן
        log.error("conversion failed: %s", safe_traceback(error))
        result = {"error": INTERNAL}
    sender.send(result)
    sender.close()


def _limit_memory(limit: int) -> None:
    """תקרה על הזיכרון הווירטואלי של התהליך (RLIMIT_AS). מעבר לה הקצאה נכשלת: בפייתון כ-MemoryError, וב-PDFium
    כקריסה של התהליך, שמגיעה לשרת כ-CRASHED. כך המרה אחת כבדה מהצפוי נכשלת לבד, ולא מפילה את השירות כולו כשהיא
    עוברת את הזיכרון שלו. מקור: resource.setrlimit (תיעוד הספרייה הסטנדרטית), RLIMIT_AS."""
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


# ---------- בתהליך של השרת ----------

async def convert(data: bytes, *, max_pages: int, timeout: float, memory_limit: int | None) -> dict:
    """ממיר את הקובץ בתהליך חדש ומחזיר את payload. זורקת ConversionFailed (עם קוד מ-FAILURES) בכל כשל; אין ערך
    החזרה שמסמן כשל.

    הזמן נמדד על ההמתנה לתשובה. כשהוא נגמר, התהליך נהרג (SIGKILL) לפני שהפונקציה חוזרת, וגם כשהקורא מבוטל: העבודה
    לא ממשיכה ברקע. ההמתנה היא על ה-pipe ועל ה-sentinel של התהליך דרך לולאת האירועים (add_reader), בלי חוט ובלי
    לחסום את השרת."""
    receiver, sender = _CONTEXT.Pipe(duplex=False)
    process = _CONTEXT.Process(target=child_main, args=(data, max_pages, memory_limit, sender), daemon=True)
    try:
        # start כותב את הקובץ לתהליך החדש ב-pipe, בתוך לולאת האירועים (multiprocessing/popen_forkserver.py, _launch).
        # התהליך קורא אותו מיד, ולכן זה נמשך כמו העתקה בזיכרון של עד MAX_BYTES
        process.start()
    except BaseException:
        receiver.close()
        raise
    finally:
        # לתהליך יש עותק משלו של הקצה הכותב. בלי לסגור את שלנו, תהליך שמת בלי לכתוב לא היה נראה כסוף הקובץ (EOF)
        sender.close()
    try:
        try:
            async with asyncio.timeout(timeout):
                await _readable(receiver.fileno())
        except TimeoutError:
            raise ConversionFailed(TIMEOUT) from None
        try:
            # התהליך כותב את כל התשובה ברצף אחד, ולכן הקריאה מסתיימת מיד. התשובה הגדולה בסט כ-160KB (web/measure.py)
            result = receiver.recv()
        except EOFError:
            raise ConversionFailed(CRASHED) from None
    finally:
        receiver.close()
        await _stop(process)
    return _answer(result)


def _answer(result: dict) -> dict:
    if "error" in result:
        raise ConversionFailed(result["error"])
    return result["result"]


async def _stop(process) -> int | None:
    """הורג את התהליך אם הוא עדיין חי, מחכה שייגמר בלי לחסום את הלולאה, ומחזיר את קוד היציאה שלו. process.sentinel
    נהיה קריא כששרת התהליכים כותב את קוד היציאה (multiprocessing/popen_forkserver.py, poll), ואז join חוזר מיד.

    תהליך שמת בלי תשובה (CRASHED) נרשם בלוג עם קוד היציאה, כי אותו קוד מכסה שני מקרים שונים: תחת תקרת הזיכרון
    PDFium מפיל את התהליך ב-SIGABRT ולא זורק MemoryError (נמדד: הדוח הכספי עם תקרה של 90MB יוצא ב-6-), וקובץ
    שמפיל את PDFium מסיבה אחרת. ההודעה למשתמש מכסה את שניהם (web/messages.py), והקוד בלוג מבדיל."""
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
