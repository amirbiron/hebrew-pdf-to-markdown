"""הקורא שמערך הבדיקה מריץ. זו נקודת ההחלפה היחידה.

מערך הבדיקה קורא לפונקציה אחת, read_pages, ולא יודע שום דבר על הלוגיקה שמאחוריה.
הלוגיקה עצמה נמצאת בחבילה hebrew_pdf. כדי לבדוק קורא אחר משנים רק את הקובץ הזה:
מייבאים את הבונה האחר ומחזירים ממנו את אותו מבנה.

החוזה: רשימה עם PageText אחד לכל עמוד, לפי סדר העמודים: הטקסט, ומספר האותיות
שדולגו כי אין להן מיקום על הדף. בתוך הטקסט השורות מופרדות ב-"\\n" בלבד. מערך הבדיקה מפצל רק לפי "\\n" (ראו harness/textdiff.py, split_lines),
כי בקבצים אמיתיים יש תווי בקרה כמו U+001D בתוך שורה.
"""

from pathlib import Path

import pypdfium2 as pdfium

from hebrew_pdf.lines import PageText, read_page


def read_pages(pdf_path: Path) -> list[PageText]:
    """הטקסט של כל עמוד בקובץ, לפי בונה השורות שבחבילה hebrew_pdf, עם מספר האותיות שדולגו.

    PdfDocument נסגר ביציאה מה-with (pypdfium2/_helpers/document.py, __exit__ קורא ל-close),
    ואיטרציה עליו מחזירה את העמודים לפי הסדר (document.py, __iter__).
    """
    with pdfium.PdfDocument(str(pdf_path)) as pdf:
        return [read_page(page) for page in pdf]
