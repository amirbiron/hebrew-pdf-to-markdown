"""הפעלת השירות: python -m web.

- HOST: הכתובת להאזנה. ברירת המחדל 127.0.0.1, כך שהרצה מקומית לא חשופה לרשת; ב-Render מוגדר 0.0.0.0 במפורש
  (render.yaml), כי שם השירות חייב להאזין לכל הכתובות (https://render.com/docs/web-services). השירות ציבורי בכוונה,
  ואין בו ראוט של ניהול או של כתיבה (CRITICAL-PATTERNS.md, K5).
- PORT: ש-Render מגדיר (ברירת המחדל שלו 10000). כאן 8000 כשלא מוגדר.

עובד אחד (workers=1), בכוונה: ההמרות רצות בתהליכים נפרדים (web/conversion.py), והתהליך של השרת רק מחכה להן,
כך שעובד נוסף לא מוסיף יכולת אלא רק מכפיל את הבסיס בזיכרון. ומספר ההמרות במקביל, הגבלת הקצב והעומס נספרים בזיכרון
של התהליך: בשני עובדים כל אחד היה סופר לבד, והמגבלות היו מוכפלות. כמה המרות במקביל נגזר מהזיכרון (web/limits.py).

proxy_headers=False: הכתובת של הלקוח נקראת מ-CF-Connecting-IP (web/app.py, client_address), ולא מ-X-Forwarded-For,
שהלקוח שולט בכתובת הראשונה בו. http="h11" ו-loop="asyncio": התצורה שנבדקה, ולא מה שמותקן במקרה (uvicorn בוחר
httptools ו-uvloop כשהם מותקנים).
"""

import logging
import os
import re

import uvicorn

_PORT = re.compile(r"[0-9]{1,5}")


def _port(raw: str | None) -> int:
    if raw is None:
        return 8000
    if not _PORT.fullmatch(raw.strip()) or not 1 <= int(raw) <= 65535:
        raise SystemExit("PORT לא תקין: צריך מספר בין 1 ל-65535")
    return int(raw)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    uvicorn.run("web.app:app", host=os.environ.get("HOST", "127.0.0.1"), port=_port(os.environ.get("PORT")),
                workers=1, proxy_headers=False, server_header=False, http="h11", loop="asyncio")


if __name__ == "__main__":
    main()
