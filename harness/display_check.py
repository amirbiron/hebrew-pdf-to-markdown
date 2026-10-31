"""בדיקת התצוגה: האם הפלט, כשמציגים אותו בפסקה עברית, נראה כמו השורה בעמוד.

לכל שורה יש שני דברים: הטקסט שהקורא הוציא (הסדר הלוגי), והאותיות כמו שהן בעמוד,
משמאל לימין (Line.visual). הבדיקה מציגה את הטקסט באלגוריתם התצוגה של Unicode
(UAX #9) ומשווה לסדר שבעמוד, אחרי איחוד רווחים (textdiff.normalize).

אלגוריתם התצוגה כאן הוא python-bidi, שעוטף את unicode-bidi של Servo (Rust): מימוש
עצמאי, שלא חולק קוד עם hebrew_pdf/logical_order.py. כך הבדיקה לא בודקת את עצמה.
רישיון: python-bidi הוא LGPL-3.0, ו-unicode-bidi הוא MIT או Apache-2.0. זו תלות
של מערך הבדיקה בלבד (requirements-dev.txt), לא של הקורא.

ארבעה דברים שהבדיקה לא בודקת, בכוונה:
- איפה יש רווח. ב-Line.visual הרווחים הם אלה שהקורא קבע לפי הפערים בעמוד
  (hebrew_pdf/spacing.py), אותם רווחים שבטקסט. הבדיקה בודקת את הסדר שלהם, לא אם
  הם במקום הנכון: את זה בודקים התיוג והבדיקות של spacing.
- כיוון הפסקה. הטקסט מוצג בכיוון שבו הקורא קרא את השורה (Line.rtl), ולא בכיוון
  שהבדיקה מחשבת לעצמה: עותק שני של הכלל היה יכול להיפרד מהראשון, ואז שורה נכונה
  נכשלת או שורה שגויה עוברת. הכיוון עצמו הוא החלטה ברמת המסמך (logical_order.document_rtl),
  ומשורה אחת אי אפשר לבדוק אותו.
- לאיזה צד פונה סוגר. python-bidi לא מיישם את כלל L4 (מקור: unicode-bidi, src/lib.rs,
  "This does not apply [Rule L3] or [Rule L4]"), כלומר מציג את התו הלוגי בלי שיקוף,
  ואילו בעמוד (Line.visual) התו של סוגר הוא הצורה המצוירת (hebrew_pdf/bracket_shapes.py).
  לכן בהשוואה "(" ו-")" נחשבים אותו תו, וכך גם "[" ו-"]" ו-"{" ו-"}": נבדק המקום של
  כל סוגר, לא הכיוון שלו. הכיוון נבדק מול התיוג, והקורא עצמו מאמת אותו בזמן הבנייה.
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

_SEGMENT_SEPARATOR = "\x1f"
_ANY_DIRECTION = str.maketrans({")": "(", "]": "[", "}": "{"})


def _paragraph_breaks_as_separators(text: str) -> str:
    return "".join(_SEGMENT_SEPARATOR if unicodedata.bidirectional(ch) == "B" else ch for ch in text)


def displayed(text: str, rtl: bool) -> str:
    """הטקסט כמו שאלגוריתם התצוגה מציג אותו, משמאל לימין."""
    return get_display(_paragraph_breaks_as_separators(text), base_dir="R" if rtl else "L")


def displays_like_page(line: Line) -> bool:
    shown = normalize(displayed(line.text, line.rtl)).translate(_ANY_DIRECTION)
    return shown == normalize(_paragraph_breaks_as_separators(line.visual)).translate(_ANY_DIRECTION)
