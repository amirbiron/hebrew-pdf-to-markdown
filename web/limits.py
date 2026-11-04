"""המגבלות של השירות, ומאיפה כל אחת נגזרת.

המדידה שמאחורי המספרים: python -m web.measure (web/measure.py), על כל 15 הקבצים בסט, בתהליך המרה כמו בשירות.
נמדד ב-2026-11-04, על המכונה שבה נכתב השירות (4 ליבות, Python 3.13). הטבלה המלאה ב-web/README.md. השורות שקובעות:

- זיכרון: הדוח הכספי (66 עמודים) הגיע לשיא של 110.3MB פיזי ו-138.8MB וירטואלי, והמצגת (24 עמודים, 2.97MB) ל-109.4MB
  ו-136.3MB. הפער בין וירטואלי לפיזי קבוע, כ-28MB, בכל הקבצים. תהליך המרה שעוד לא התחיל מחזיק כ-22MB, רובם משותפים
  עם שרת התהליכים.
- זמן: קובץ הטבלאות (26 עמודים) הוא האיטי, 23.6 שניות של מעבד (24.75 בזמן שעבר במדידה הראשונה), ולא הדוח הכספי
  (כ-10). 90% מהזמן שלו ב-hebrew_pdf/layout.py, _distinct (נמדד ב-cProfile). כל שאר הקבצים מתחת ל-1.5 שניות.

כמה המרות במקביל (capacity): מה שנכנס בזיכרון, וגם מה שהמעבד מספיק לסיים בזמן, הקטן מהשניים. הזיכרון לבדו לא מספיק:
הזמן להמרה נמדד בשעון, והמרות במקביל חולקות את המעבד. בחצי מעבד שתי המרות של קובץ הטבלאות צריכות כ-95 שניות כל
אחת, כלומר שתיהן היו נעצרות ב-90 שניות, והעבודה של שתיהן הייתה הולכת לאיבוד. המכסה נקראת מ-cgroup, ולא ממספר
המעבדים של המארח (bugbot-rules/host-metric-in-container.md).

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
# התשובה של המרה, מהתהליך לשרת (JSON). הגדולה בסט 171KB (הדוח הכספי, 66 עמודים), והעמוד הצפוף ביותר בסט 6.3KB
# (נמדד מהתשובות של כל 15 הקבצים). MAX_PAGES עמודים צפופים כאלה הם כ-630KB; פי 6, ומעוגל, 4MB. מעבר לזה התהליך נהרג
# והמשתמש מקבל "מורכב מדי" (web/conversion.py, exchange): קובץ PDF דחוס יכול להפוך להרבה יותר טקסט מהגודל שלו
MAX_ANSWER = 4 * MB
# הזמן להמרה אחת, מהרגע שהקובץ נקרא. ההמרה האיטית בסט: 23.6 שניות מעבד כאן. ב-Render, עם חצי מעבד, היא צפויה לכ-50
# שניות לבד (בהנחה שליבה שם מהירה כמו כאן; לא נמדד). המקסימום הוא מתחת ל-100 שניות, הגבול של Cloudflare בגרסה
# הישנה של הדף, כדי שהמשתמש יקבל את ההודעה שלנו ולא שגיאה של Cloudflare. זה ערך זמני: הערך הסופי נקבע מהזמנים
# ש-Render רושם בלוג לכל המרה (web/app.py)
TIMEOUT_SECONDS = 90.0
# זמן המעבד של ההמרה האיטית בסט (קובץ הטבלאות), web/measure.py, 2026-11-04. מולו נגזר כמה המרות המעבד מספיק לסיים
# בזמן (cpu_slots)
SLOWEST_CPU_SECONDS = 23.6
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
# מה שהשרת מחזיק כדי לטפל בתשובה אחת: פענוח ה-JSON, הוספת ההסברים ובניית התשובה ל-HTTP. נמדד ב-tracemalloc על
# התשובה של הדוח הכספי: פי 4.9 מגודל התשובה. פי 5 מהתשובה הגדולה שמותרת
ANSWER_COST = 5 * MAX_ANSWER
# מה שמקום אחד להמרה עולה בזיכרון: התהליך של ההמרה, הקובץ אצל השרת (נקרא ישר לחוצץ בגודל המוצהר, ונשאר עד סוף
# ההמרה; web/app.py, read_body), והטיפול בתשובה. המקום נתפס לפני קריאת הקובץ, כך שאין קבצים בדרך מעבר למקומות
SLOT_MEMORY = CONVERSION_PHYSICAL + MAX_BYTES + ANSWER_COST
# שוליים מעל הכול: מה שלא נספר לכל מקום (חיבורים פתוחים, הלוג, והפיצול של הזיכרון בפייתון)
MARGIN = 64 * MB
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
    """כמה המרות נכנסות במקביל בזיכרון של השירות: (המגבלה - הבסיס - שוליים) / מה שמקום אחד עולה, בין הרצפה לתקרה."""
    fit = (memory - BASELINE - MARGIN) // SLOT_MEMORY
    return max(MIN_SLOTS, min(MAX_SLOTS, fit))


def cpu_slots(cpus: float) -> int:
    """כמה המרות יכולות לחלוק cpus מעבדים, כך שגם ההמרה האיטית בסט מקבלת מספיק מעבד להסתיים בזמן להמרה, בין הרצפה
    לתקרה."""
    fit = math.floor(cpus * TIMEOUT_SECONDS / SLOWEST_CPU_SECONDS)
    return max(MIN_SLOTS, min(MAX_SLOTS, fit))


def container_cpus(root: Path = Path("/sys/fs/cgroup")) -> float | None:
    """מכסת המעבד של הקונטיינר, במעבדים, מ-cgroup: cpu.max ב-v2 ("max" הוא בלי מכסה), ו-cpu/cpu.cfs_quota_us חלקי
    cpu/cpu.cfs_period_us ב-v1 (1- הוא בלי מכסה). None כשאין מכסה או שאי אפשר לקרוא אותה."""
    try:
        quota, period = (root / "cpu.max").read_text().split()
    except OSError:
        try:
            quota = (root / "cpu" / "cpu.cfs_quota_us").read_text().strip()
            period = (root / "cpu" / "cpu.cfs_period_us").read_text().strip()
        except OSError:
            return None  # אין cgroup של מעבד שאפשר לקרוא: אין מכסה ידועה
    except ValueError:
        log.warning("ערך לא מוכר במכסת המעבד של cgroup")
        return None
    if quota in ("max", "-1"):
        return None
    if not (_DIGITS.fullmatch(quota) and _DIGITS.fullmatch(period)) or int(period) == 0:
        log.warning("ערך לא מוכר במכסת המעבד של cgroup")
        return None
    return int(quota) / int(period)


@dataclass(frozen=True)
class Capacity:
    slots: int
    source: str  # מאיפה נגזר המספר, לשורת הלוג בעלייה


def capacity(environ=os.environ, root: Path = Path("/sys/fs/cgroup")) -> Capacity:
    """כמה המרות במקביל. HEBREW_PDF_SLOTS קובע ידנית (מספר שלם בין MIN_SLOTS ל-MAX_SLOTS); אחרת הקטן מבין מה
    שנכנס בזיכרון של הקונטיינר ומה שמכסת המעבד שלו מספיקה (בלי מכסה: הזיכרון לבד); וכשהזיכרון לא ידוע, הרצפה:
    מאגר צר מדי הוא איטיות שרואים, ורחב מדי הוא OOM של כל השירות."""
    override = environ.get("HEBREW_PDF_SLOTS")
    if override is not None:
        value = override.strip()
        if _DIGITS.fullmatch(value) and MIN_SLOTS <= int(value) <= MAX_SLOTS:
            return Capacity(int(value), "HEBREW_PDF_SLOTS")
        log.error("HEBREW_PDF_SLOTS לא תקין (צריך מספר שלם בין %d ל-%d); המספר נגזר מהקונטיינר", MIN_SLOTS, MAX_SLOTS)
    memory = container_memory(root)
    if memory is None:
        return Capacity(MIN_SLOTS, "מגבלת הזיכרון של הקונטיינר לא ידועה, ולכן הרצפה")
    by_memory = slots_for(memory)
    cpus = container_cpus(root)
    if cpus is None:
        return Capacity(by_memory, f"זיכרון {memory // MB}MB מ-cgroup ({by_memory}); בלי מכסת מעבד")
    by_cpu = cpu_slots(cpus)
    return Capacity(min(by_memory, by_cpu), f"זיכרון {memory // MB}MB ({by_memory}) ומעבד {cpus:g} ({by_cpu}) מ-cgroup")


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
