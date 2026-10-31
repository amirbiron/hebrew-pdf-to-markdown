"""קריאת האותיות של עמוד מ-pypdfium2, עם המיקום וקו הבסיס של כל אחת."""

import ctypes
import math
from dataclasses import dataclass
from typing import NamedTuple

import pypdfium2.raw as pdfium_raw

from hebrew_pdf.bracket_shapes import FAMILIES, drawn_shape


class Char(NamedTuple):
    text: str  # בסוגר: התו של הצורה שמצוירת בעמוד, לא התו שבקובץ (bracket_shapes.py)
    x: float  # מרכז התיבה, אופקית
    baseline: float  # ה-y של נקודת המוצא של האות (FPDFText_GetCharOrigin)


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
        box = textpage.get_charbox(i)
        center = (box[0] + box[2]) / 2
        if not (math.isfinite(center) and math.isfinite(y.value)):
            skipped += 1
            continue
        if ch in FAMILIES:
            shape = drawn_shape(page, box, ch)
            if shape is None:
                unknown_brackets += 1
            else:
                ch = shape
        chars.append(Char(ch, center, y.value))
    return PageChars(chars, skipped, unknown_brackets)
