"""בדיקת התצוגה: האם הפלט, כשמציגים אותו בפסקה עברית, נראה כמו השורה בעמוד.

לכל שורה יש שני דברים: הטקסט שהקורא הוציא (הסדר הלוגי), והאותיות כמו שהן בעמוד,
משמאל לימין (Line.visual). הבדיקה מציגה את הטקסט באלגוריתם התצוגה של Unicode
(UAX #9) ומשווה לסדר שבעמוד, אחרי איחוד רווחים (textdiff.normalize).

אלגוריתם התצוגה כאן הוא python-bidi, שעוטף את unicode-bidi של Servo (Rust): מימוש
עצמאי, שלא חולק קוד עם hebrew_pdf/logical_order.py. כך הבדיקה לא בודקת את עצמה.
רישיון: python-bidi הוא LGPL-3.0, ו-unicode-bidi הוא MIT או Apache-2.0. זו תלות
של מערך הבדיקה בלבד (requirements-dev.txt), לא של הקורא.

שלושה דברים שהבדיקה לא בודקת, בכוונה:
- כיוון הפסקה. שורה עם עברית מוצגת בפסקה מימין לשמאל ושורה בלי עברית משמאל לימין,
  לפי אותו כלל של הקורא (logical_order.is_rtl). זו החלטה פתוחה במסמך האפיון.
- שיקוף של סוגריים. python-bidi לא מיישם את כלל L4 (מקור: unicode-bidi, src/lib.rs,
  "This does not apply [Rule L3] or [Rule L4]"), כלומר התו נשאר התו. וגם בעמוד התו
  של הסוגר לא בהכרח מתאר את הצורה שרואים (ראו הדוח של הסבב).
- סדר אחד מתוך כמה שנראים זהים. כשלשני סדרים לוגיים יש אותה תצוגה ("1 Onboarding"
  ו-"Onboarding 1"), שניהם עוברים. הבדיקה הכרחית, לא מספיקה.

ועוד התאמה אחת, באותו אופן בשני הצדדים: תו מסוג B (מפריד פסקאות) בתוך שורה הופך
למפריד S. python-bidi פותח בו פסקה חדשה, והקורא מתייחס אליו כמפריד בתוך השורה,
כי השורה היא שורה אחת בעמוד (logical_order.bidi_class).
"""

import unicodedata

from bidi import get_display

from harness.textdiff import normalize
from hebrew_pdf.lines import Line
from hebrew_pdf.logical_order import bidi_class, is_rtl

_SEGMENT_SEPARATOR = "\x1f"


def _paragraph_breaks_as_separators(text: str) -> str:
    return "".join(_SEGMENT_SEPARATOR if unicodedata.bidirectional(ch) == "B" else ch for ch in text)


def displayed(text: str, rtl: bool) -> str:
    """הטקסט כמו שאלגוריתם התצוגה מציג אותו, משמאל לימין."""
    return get_display(_paragraph_breaks_as_separators(text), base_dir="R" if rtl else "L")


def displays_like_page(line: Line) -> bool:
    rtl = is_rtl([bidi_class(ch) for ch in line.visual])
    return normalize(displayed(line.text, rtl)) == normalize(_paragraph_breaks_as_separators(line.visual))
