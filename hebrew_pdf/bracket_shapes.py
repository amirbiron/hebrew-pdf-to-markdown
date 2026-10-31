"""הצורה של סוגר כמו שהוא מצויר בעמוד: נפתח ימינה, כמו "(", או שמאלה, כמו ")".

למה לא לפי התו שבקובץ: בסט הבדיקה התו של הסוגר לא אמין. יש יוצרים ששומרים את התו
של הצורה שנראית, יש ששומרים את התו הלוגי (שמוצג בשיקוף בשורה עברית), ויש ששומרים
את שני הצדדים של אותו זוג כאותו תו, כנראה כי ל-PDF יש מיפוי אחד לכל צורה ציורית
והוא נקבע לפי השימוש הראשון בה. נמדד על 2,456 הסוגריים בסט: ב-Aspose, Google Docs,
WeasyPrint ו-Canva התו והצורה לא מתאימים בכמחצית מהמקרים; רק InDesign ו-Chrome
עקביים. מה שאמין הוא מה שמצויר.

השיטה: מציירים (pypdfium2, PdfPage.render) רק את התיבה של הסוגר, ובודקים לאן הקשת
בולטת. ב-"(" האמצע של הציור שמאלי יותר מהקצוות העליון והתחתון, וב-")" ימני יותר.
אותו דבר נכון ל-"[" (הקו האנכי שמאלי והזיזים יוצאים ימינה) ול-"{".
נבדק מול התיוג: 39 מתוך 39 הסוגריים ב-11 השורות המתויגות שיש בהן סוגריים.
"""

import collections
import math

# צורה נפתחת ימינה, צורה נפתחת שמאלה
FAMILIES = {"(": ("(", ")"), ")": ("(", ")"), "[": ("[", "]"), "]": ("[", "]"), "{": ("{", "}"), "}": ("{", "}")}

_GLYPH_PIXELS = 48.0  # גובה הסוגר בציור, בפיקסלים: מספיק כדי לראות את הקשת
_MARGIN = 0.05  # שוליים סביב התיבה, כחלק מגובה הסוגר, נגד חיתוך של קצוות מוחלקים
_INK_CONTRAST = 60  # הפרש בהירות (מתוך 255) בין דיו לרקע
_MIN_INK_ROWS = 6


def drawn_shape(page, box: tuple[float, float, float, float], text: str) -> str | None:
    """התו שהצורה שלו היא מה שמצויר בעמוד, מאותה משפחה של text ("(" או ")" וכו').

    box: התיבה של התו בעמוד (left, bottom, right, top), כמו מ-get_charbox.
    מחזירה None כשאי אפשר לקבוע: תיבה בלי גובה, ציור בלי דיו שנבדל מהרקע, או ציור
    שבו האמצע והקצוות באותו מקום. הקורא סופר את המקרים האלה לכל עמוד.
    """
    left, bottom, right, top = box
    height = top - bottom
    if not all(math.isfinite(v) for v in box) or height <= 0 or right <= left:
        return None
    page_width, page_height = page.get_size()
    margin = _MARGIN * height
    # crop: כמה לחתוך מכל צד של העמוד (pypdfium2/_helpers/page.py, PdfPage.render)
    crop = (max(0.0, left - margin), max(0.0, bottom - margin),
            max(0.0, page_width - right - margin), max(0.0, page_height - top - margin))
    bitmap = page.render(scale=_GLYPH_PIXELS / height, crop=crop, grayscale=True, may_draw_forms=False)
    try:
        lean = _lean(bitmap)
    finally:
        bitmap.close()
    if lean is None or lean == 0:
        return None
    opens_right, opens_left = FAMILIES[text]
    return opens_right if lean > 0 else opens_left


def _lean(bitmap) -> float | None:
    """הקצוות פחות האמצע, אופקית, כחלק מרוחב הציור: חיובי = הקשת בולטת שמאלה (")".

    None כשאין מספיק דיו. הערכים של הציור מגיעים מ-PDFium, ולכן נבדקים לפני השימוש.
    """
    width, height, stride, channels = bitmap.width, bitmap.height, bitmap.stride, bitmap.n_channels
    if width <= 0 or height <= 0 or channels <= 0 or stride < width * channels:
        return None
    data = bytes(bitmap.buffer)
    if len(data) < stride * height:
        return None
    gray = [[sum(data[y * stride + x * channels:y * stride + (x + 1) * channels]) / channels
             for x in range(width)] for y in range(height)]
    # הרקע: הבהירות הנפוצה ביותר בציור (בצעדים של 8, כדי שהחלקת קצוות לא תפצל אותה)
    background = collections.Counter(int(v) // 8 for row in gray for v in row).most_common(1)[0][0] * 8 + 4
    ink = [[abs(v - background) > _INK_CONTRAST for v in row] for row in gray]
    rows = [y for y in range(height) if any(ink[y])]
    if len(rows) < _MIN_INK_ROWS:
        return None
    first, last = rows[0], rows[-1]
    band = max(1, (last - first + 1) // 5)

    def mean_x(y0: int, y1: int) -> float | None:
        xs = [x for y in range(y0, y1) for x in range(width) if ink[y][x]]
        return sum(xs) / len(xs) if xs else None

    ends = [v for v in (mean_x(first, first + band), mean_x(last + 1 - band, last + 1)) if v is not None]
    middle = mean_x(first + 2 * band, first + 3 * band)
    if middle is None or not ends:
        return None
    return (sum(ends) / len(ends) - middle) / width
