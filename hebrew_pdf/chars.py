"""קריאת האותיות של עמוד מ-pypdfium2, עם המיקום וקו הבסיס של כל אחת."""

import ctypes

import pypdfium2.raw as pdfium_raw


def page_chars(page):
    """כל האותיות בעמוד: (תו, מרכז אופקי, קו בסיס).

    חשוב: קו הבסיס ולא תחתית האות. אותיות שיורדות מתחת לשורה (ק ך ן ף ץ)
    נופלות לשורה אחרת אם מקבצים לפי תחתית התיבה.
    """
    textpage = page.get_textpage()
    x = ctypes.c_double()
    y = ctypes.c_double()
    chars = []
    for i in range(textpage.count_chars()):
        ch = textpage.get_text_range(i, 1)
        if not ch or ch in "\r\n":
            continue
        left, _bottom, right, _top = textpage.get_charbox(i)
        pdfium_raw.FPDFText_GetCharOrigin(textpage, i, x, y)
        chars.append((ch, (left + right) / 2, y.value))
    return chars
