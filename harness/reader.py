"""הקורא שמערך הבדיקה מריץ. זו נקודת ההחלפה היחידה.

מערך הבדיקה קורא לפונקציה אחת, read_pages, ולא יודע שום דבר על הלוגיקה שמאחוריה.
הלוגיקה עצמה נמצאת בחבילה hebrew_pdf. כדי לבדוק קורא אחר משנים רק את הקובץ הזה:
מייבאים את הבונה האחר ומחזירים ממנו את אותו מבנה.

החוזה: רשימה עם מחרוזת אחת לכל עמוד, לפי סדר העמודים. בתוך עמוד השורות מופרדות
ב-"\\n" בלבד. מערך הבדיקה מפצל רק לפי "\\n" (ראו harness/textdiff.py, split_lines),
כי בקבצים אמיתיים יש תווי בקרה כמו U+001D בתוך שורה.
"""

from pathlib import Path

import pypdfium2 as pdfium

from hebrew_pdf.lines import page_text


def read_pages(pdf_path: Path) -> list[str]:
    """הטקסט של כל עמוד בקובץ, לפי בונה השורות שבחבילה hebrew_pdf.

    PdfDocument נסגר ביציאה מה-with (pypdfium2/_helpers/document.py, __exit__ קורא ל-close),
    ואיטרציה עליו מחזירה את העמודים לפי הסדר (document.py, __iter__).
    """
    with pdfium.PdfDocument(str(pdf_path)) as pdf:
        return [page_text(page) for page in pdf]
