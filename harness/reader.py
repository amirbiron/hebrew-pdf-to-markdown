"""הקורא שמערך הבדיקה מריץ. זו נקודת ההחלפה היחידה.

מערך הבדיקה קורא לפונקציה אחת, read_pages, ולא יודע שום דבר על הלוגיקה שמאחוריה.
בסבב הבא, כשבונה השורות יוחלף, משנים רק את הקובץ הזה: מייבאים את הבונה החדש
ומחזירים ממנו את אותו מבנה.

החוזה: רשימה עם מחרוזת אחת לכל עמוד, לפי סדר העמודים. בתוך עמוד השורות מופרדות
ב-"\\n" בלבד. מערך הבדיקה מפצל רק לפי "\\n" (ראו harness/textdiff.py, split_lines),
כי בקבצים אמיתיים יש תווי בקרה כמו U+001D בתוך שורה.
"""

from pathlib import Path

import pypdfium2 as pdfium

from prototype import hebrew_pdf_prototype as prototype


def read_pages(pdf_path: Path) -> list[str]:
    """הטקסט של כל עמוד בקובץ, לפי האב-טיפוס.

    PdfDocument נסגר ביציאה מה-with (pypdfium2/_helpers/document.py, __exit__ קורא ל-close),
    ואיטרציה עליו מחזירה את העמודים לפי הסדר (document.py, __iter__).
    """
    with pdfium.PdfDocument(str(pdf_path)) as pdf:
        return [prototype.page_text(page) for page in pdf]
