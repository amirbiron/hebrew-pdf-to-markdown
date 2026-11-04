"""המגבלות של השירות, ומאיפה כל אחת נגזרת.

המדידה שמאחורי המספרים: python -m web.measure (web/measure.py), על כל 15 הקבצים בסט, בתהליך המרה כמו בשירות.
נמדד ב-2026-11-04, על המכונה שבה נכתב השירות (4 ליבות, Python 3.13). הטבלה המלאה ב-web/README.md. השורות שקובעות:

- זיכרון: הדוח הכספי (66 עמודים) הגיע לשיא של 110.3MB פיזי ו-138.8MB וירטואלי, והמצגת (24 עמודים, 2.97MB) ל-109.4MB
  ו-136.3MB. הפער בין וירטואלי לפיזי קבוע, כ-28MB, בכל הקבצים. תהליך המרה שעוד לא התחיל מחזיק כ-22MB, רובם משותפים
  עם שרת התהליכים.
- זמן: קובץ הטבלאות (26 עמודים) הוא האיטי, 24.75 שניות, ולא הדוח הכספי (9.15). 90% מהזמן שלו ב-hebrew_pdf/layout.py,
  _distinct (נמדד ב-cProfile). כל שאר הקבצים מתחת ל-1.1 שניות.

המספרים של Render: התוכנית 0.5c-512mb (בעבר starter) היא 0.5 מעבד ו-512MB, ו-free היא 0.1 מעבד ו-512MB
(https://render.com/docs/compute-plans). מול Cloudflare, שעומד לפני כל שירות ב-Render, בקשה שלא נענתה תוך 125 שניות
נכשלת ב-524 (https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/;
בגרסאות קודמות של הדף 100 שניות).
"""

import logging
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("web.limits")

MB = 1024 * 1024

# הקובץ הגדול בסט הוא 2.97MB (המצגת). פי 3, ומעוגל למעלה
MAX_BYTES = 10 * MB
# הקובץ הארוך בסט הוא 66 עמודים (הדוח הכספי). פי 1.5
MAX_PAGES = 100
# הזמן להמרה אחת, מהרגע שהקובץ נקרא. ההמרה האיטית בסט: 24.75 שניות כאן. ב-Render, עם חצי מעבד, היא צפויה לכ-50
# שניות לבד, ויותר כשעוד המרה רצה במקביל (הן חולקות את המעבד). המקסימום הוא מתחת ל-100 שניות, הגבול של Cloudflare
# בגרסה הישנה של הדף, כדי שהמשתמש יקבל את ההודעה שלנו ולא שגיאה של Cloudflare. זה ערך זמני: הערך הסופי נקבע
# מהזמנים ש-Render רושם בלוג לכל המרה (web/app.py)
TIMEOUT_SECONDS = 90.0
# הזמן לקבל את הקובץ מהדפדפן. ל-uvicorn אין מגבלה כזו על גוף הבקשה (bugbot-rules/wait-without-own-deadline.md):
# בלעדיה לקוח שמטפטף בתים מחזיק את השרת כמה שירצה. 10MB ב-60 שניות הם כ-1.4Mbps
UPLOAD_SECONDS = 60.0
# תקרת הזיכרון הווירטואלי של כל תהליך המרה (RLIMIT_AS, web/conversion.py). השיא הווירטואלי בסט 138.8MB, ועם שוליים
# של כ-40% ל-192MB. המרה שצריכה יותר נכשלת לבד, בהודעה שהקובץ מורכב מדי, ולא מפילה את השירות
CONVERSION_MEMORY = 192 * MB
# מה שתהליך המרה יכול לתפוס בזיכרון הפיזי לכל היותר: התקרה פחות החלק הווירטואלי שלא מגיע לזיכרון (כ-28MB בכל
# הקבצים). לא מנכים את מה שמשותף עם שרת התהליכים, כך שהחישוב שמרני
CONVERSION_PHYSICAL = CONVERSION_MEMORY - 28 * MB
# מה שהשירות מחזיק בלי המרה שרצה: התהליך של השרת (שיא של 56.2MB, אחרי המרה של הדוח הכספי ובניית התשובה שלו), שרת
# התהליכים (28.0MB) ו-resource_tracker (14.6MB), שיא פיזי (VmHWM) של כל אחד. 98.8MB, מעוגל ל-100. נמדד על השרת האמיתי
# (python -m web), 2026-11-04
BASELINE = 100 * MB
# שוליים מעל הכול, לגוף הבקשות שבדרך ולתשובות (כל קובץ עד MAX_BYTES, ותשובה עד כ-160KB בסט)
MARGIN = 64 * MB
# כמה קבצים נקראים במקביל מהדפדפנים, לכל המרה שיכולה לרוץ: כל אחד עד MAX_BYTES בזיכרון של השרת
UPLOADS_PER_SLOT = 2
# רצפה ותקרה לכמה המרות במקביל. התקרה: מעבר לה המעבד הוא הצוואר, וזה כבר החלטה ולא חשבון
MIN_SLOTS = 1
MAX_SLOTS = 8
# הגבלת קצב לכל כתובת: כמה המרות בחלון. נדיב מספיק להעלות את כל 15 הקבצים של הסט ברצף
RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 600.0

# מעל זה ב-memory.limit_in_bytes (cgroup v1) פירושו "בלי מגבלה": שם הערך הוא LONG_MAX מעוגל לעמוד
# (bugbot-rules/host-metric-in-container.md), למשל 9223372036854771712
_UNLIMITED_V1 = 2 ** 60
# ספרות ASCII בלבד: str.isdigit מקבל גם "²", ו-int זורק עליו
_DIGITS = re.compile(r"[0-9]{1,20}")


def container_memory(root: Path = Path("/sys/fs/cgroup")) -> int | None:
    """מגבלת הזיכרון של הקונטיינר, בבתים, מ-cgroup: memory.max ב-v2 ("max" הוא בלי מגבלה), ו-memory/memory.limit_in_bytes
    ב-v1. None כשאין מגבלה או שאי אפשר לקרוא אותה."""
    v2 = root / "memory.max"
    v1 = root / "memory" / "memory.limit_in_bytes"
    for path in (v2, v1):
        try:
            value = path.read_text().strip()
        except OSError:
            continue  # הקובץ לא קיים בגרסה הזו של cgroup: עוברים לגרסה השנייה
        if value == "max":
            return None
        if not _DIGITS.fullmatch(value):
            log.warning("ערך לא מוכר במגבלת הזיכרון של cgroup (%s)", path)
            return None
        number = int(value)
        return None if number >= _UNLIMITED_V1 else number
    return None


def slots_for(memory: int) -> int:
    """כמה המרות נכנסות במקביל בזיכרון של השירות: (המגבלה - הבסיס - שוליים) / מה שהמרה אחת תופסת, בין הרצפה לתקרה."""
    fit = (memory - BASELINE - MARGIN) // CONVERSION_PHYSICAL
    return max(MIN_SLOTS, min(MAX_SLOTS, fit))


@dataclass(frozen=True)
class Capacity:
    slots: int
    source: str  # מאיפה נגזר המספר, לשורת הלוג בעלייה


def capacity(environ=os.environ, root: Path = Path("/sys/fs/cgroup")) -> Capacity:
    """כמה המרות במקביל. HEBREW_PDF_SLOTS קובע ידנית (מספר שלם בין MIN_SLOTS ל-MAX_SLOTS); אחרת מהזיכרון של
    הקונטיינר; וכשהוא לא ידוע, הרצפה: מאגר צר מדי הוא איטיות שרואים, ורחב מדי הוא OOM של כל השירות."""
    override = environ.get("HEBREW_PDF_SLOTS")
    if override is not None:
        value = override.strip()
        if _DIGITS.fullmatch(value) and MIN_SLOTS <= int(value) <= MAX_SLOTS:
            return Capacity(int(value), "HEBREW_PDF_SLOTS")
        log.error("HEBREW_PDF_SLOTS לא תקין (צריך מספר שלם בין %d ל-%d); המספר נגזר מהזיכרון", MIN_SLOTS, MAX_SLOTS)
    memory = container_memory(root)
    if memory is None:
        return Capacity(MIN_SLOTS, "מגבלת הזיכרון של הקונטיינר לא ידועה, ולכן הרצפה")
    return Capacity(slots_for(memory), f"מגבלת זיכרון {memory // MB}MB מ-cgroup")


def seconds_from(environ, name: str, default: float, low: float, high: float) -> float:
    """מספר שניות ממשתנה סביבה (לבדיקות ולכוונון אחרי מדידה ב-Render), סופי ובטווח; אחרת ברירת המחדל, עם לוג."""
    raw = environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or not low <= value <= high:
        log.error("%s לא תקין (צריך מספר בין %s ל-%s); נשאר %s", name, low, high, default)
        return default
    return value
