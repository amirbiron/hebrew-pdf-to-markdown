"""קריאת האותיות של עמוד מ-pypdfium2, עם המיקום וקו הבסיס של כל אחת."""

import ctypes
import math
from dataclasses import dataclass
from typing import NamedTuple

import pypdfium2.raw as pdfium_raw

from hebrew_pdf.bracket_shapes import FAMILIES, drawn_shape


# שני גדלים של אות "שווים" כשהיחס ביניהם עד 1.02: הגודל מגיע מהקובץ (גודל הגופן כפול המטריצה),
# וגדלים של אותו סגנון שווים בו עד כדי עיגול. בדיקת רגישות (סבב 5, כל הסט): מ-1.005 עד 1.05 מספר
# הכותרות משתנה בעד 6 מתוך 276, והפסקאות בעד 3. משמש את הכותרות (markdown.py) ואת הסוף של טבלה (layout.py)
SAME_SIZE = 1.02


def same_size(a: float, b: float) -> bool:
    """שני גדלים של אות שווים (SAME_SIZE)."""
    return max(a, b) <= min(a, b) * SAME_SIZE


class Char(NamedTuple):
    text: str  # בסוגר: התו של הצורה שמצוירת בעמוד, לא התו שבקובץ (bracket_shapes.py)
    x: float  # מרכז התיבה, אופקית
    baseline: float  # ה-y של נקודת המוצא של האות (FPDFText_GetCharOrigin)
    # התיבה הרופפת (FPDFText_GetLooseCharBox): משמאל ומימין לפי רוחב ההתקדמות של האות,
    # ובגובה לפי תיבת הגופן. ממנה נמדדים הפערים בין אותיות (spacing.py)
    left: float
    right: float
    height: float
    # גודל האות בעמוד (em): גודל הגופן כפול קנה המידה של המטריצה, בכיוון שניצב לשורה (font_size).
    # 0: אין גודל (רווח שהקורא הוסיף, spacing.py). למה לא height: היא תיבת הגופן, ובגופן אחר
    # באותו גודל היא אחרת (נמדד ב-Canva: em 14 בשלושה גופנים, ותיבה של 18.9 עד 19.6)
    size: float = 0.0


@dataclass(frozen=True)
class PageChars:
    chars: list[Char]
    # אותיות שדולגו כי אין להן מיקום שאפשר להשתמש בו: FPDFText_GetCharOrigin נכשלה,
    # או שהמיקום או התיבה אינם מספר סופי. המספר הזה ייכנס לציון של העמוד.
    skipped: int
    # סוגריים שלא הצלחנו לקבוע את הצורה שלהם מהציור; נשאר בהם התו שבקובץ
    unknown_brackets: int = 0


def page_chars(page) -> PageChars:
    """כל האותיות בעמוד, ומספר האותיות שדולגו כי אין להן מיקום.

    חשוב: קו הבסיס ולא תחתית האות. אותיות שיורדות מתחת לשורה (ק ך ן ף ץ)
    נופלות לשורה אחרת אם מקבצים לפי תחתית התיבה.

    כשל של FPDFText_GetCharOrigin לא עובר בשקט. לפי public/fpdf_text.h ב-PDFium:
    "Whether the call succeeded. If false, x and y are unchanged" — כלומר בלי בדיקה
    האות מקבלת את המיקום של האות הקודמת. במקרה כזה האות מדולגת ונספרת ב-skipped.
    אין מיקום חלופי מהתיבה: ב-fpdfsdk/fpdf_text.cpp שתי הפונקציות נכשלות באותו תנאי
    בדיוק (GetTextPageForValidIndex), ותחתית התיבה היא בדיוק קו השורה הלא נכון
    לאותיות היורדות. (נמדד על סט הבדיקה: 0 כשלים מתוך 159,741 אותיות.)
    """
    textpage = page.get_textpage()
    x = ctypes.c_double()
    y = ctypes.c_double()
    matrix = pdfium_raw.FS_MATRIX()
    chars = []
    skipped = unknown_brackets = 0
    for i in range(textpage.count_chars()):
        ch = textpage.get_text_range(i, 1)
        if not ch or ch in "\r\n":
            continue
        if not pdfium_raw.FPDFText_GetCharOrigin(textpage, i, x, y):
            skipped += 1
            continue
        # get_charbox זורקת PdfiumError בכשל (pypdfium2/_helpers/textpage.py), ואחרי
        # GetCharOrigin מוצלחת היא לא יכולה להיכשל: אותו תנאי, והמצביעים לא ריקים.
        # כך גם התיבה הרופפת (loose=True, FPDFText_GetLooseCharBox ב-fpdfsdk/fpdf_text.cpp).
        box = textpage.get_charbox(i)
        center = (box[0] + box[2]) / 2
        # התיבה הרופפת: משמאל = נקודת המוצא, מימין = המוצא ועוד רוחב ההתקדמות של האות,
        # ולמעלה ולמטה = תיבת הגופן (GetLooseBounds ב-core/fpdftext/cpdf_textpage.cpp).
        # כשאין לאות תיבה בכלל (תיבה ריקה, למשל רווח ש-PDFium הוסיף) היא ריקה גם כאן.
        loose_left, loose_bottom, loose_right, loose_top = textpage.get_charbox(i, loose=True)
        size = font_size(textpage, i, matrix)
        if not all(math.isfinite(v) for v in (center, y.value, loose_left, loose_bottom, loose_right, loose_top, size)):
            skipped += 1
            continue
        if ch in FAMILIES:
            shape = drawn_shape(page, box, ch)
            if shape is None:
                unknown_brackets += 1
            else:
                ch = shape
        chars.append(Char(ch, center, y.value, loose_left, loose_right, loose_top - loose_bottom, size))
    return PageChars(chars, skipped, unknown_brackets)


def font_size(textpage, index: int, matrix: "pdfium_raw.FS_MATRIX") -> float:
    """גודל האות בעמוד: הגובה של ריבוע ה-em, בנקודות של העמוד, בניצב לכיוון השורה.

    FPDFText_GetFontSize מחזיר את הגודל מפקודת הגופן בלבד (GetFontSize ב-core/fpdftext/cpdf_textpage.cpp:
    text_object->GetFontSize()), בלי מטריצת הטקסט. ב-InDesign וב-Illustrator הוא 1 לכל האותיות, והגודל
    כולו במטריצה. FPDFText_GetMatrix מחזיר את המטריצה האפקטיבית של האות (public/fpdf_text.h: "the
    effective transformation matrix"; ב-CharInfo זו מטריצת הטקסט כפול מטריצת הטופס). הגובה בניצב לשורה
    הוא |a·d − b·c| / |(a, b)|: בלי סיבוב והטיה זה |d|, ובהטיה של אות נטויה מלאכותית (Chrome, c=0.19)
    הוא לא גדל כמו אורך העמודה (c, d).

    שתי הקריאות נכשלות רק באינדקס או בעמוד לא תקינים (GetTextPageForValidIndex ב-fpdfsdk/fpdf_text.cpp),
    וזה בדיוק התנאי של FPDFText_GetCharOrigin שכבר הצליחה לאותו אינדקס. בכל זאת: כשל במטריצה מחזיר
    NaN, והאות נספרת כמדולגת כמו כל ערך לא סופי (page_chars), ולא מקבלת גודל ממציא.
    """
    if not pdfium_raw.FPDFText_GetMatrix(textpage, index, matrix):
        return math.nan
    a, b, c, d = matrix.a, matrix.b, matrix.c, matrix.d
    axis = math.hypot(a, b)
    if axis == 0:
        return math.nan
    return pdfium_raw.FPDFText_GetFontSize(textpage, index) * abs(a * d - b * c) / axis
