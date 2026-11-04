"""קריאת האותיות של עמוד מ-pypdfium2, עם המיקום וקו הבסיס של כל אחת."""

import ctypes
import math
import re
import statistics
import unicodedata
from collections.abc import Iterable, Sequence
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


def size_of(chars: Iterable["Char"]) -> float:
    """הגודל של קבוצת אותיות (שורה, רכיב): החציון של Char.size באותיות שיש להן גודל, 0 כשאין כאלה. החציון
    התחתון (statistics.median_low) ולא הממוצע של שני האמצעיים: הגודל הוא תמיד גודל של אחת האותיות. בשורה
    שחציה בגודל 13 וחציה ב-17 (כותרת ב-doc-6p_gdocs.pdf, 25 ו-25 עם האימוג'י) הממוצע הוא 15, גודל שאין
    לאף אות בעמוד, והוא היה נספר כקבוצת גודל חדשה של כותרות ומזיז את הרמה של כל הכותרות שמתחתיה
    (markdown._Sizes). משמש את הגיאומטריה של שורה ורכיב (lines.geometry_of) ואת השורה בעמוד
    (layout.PageLine.size), כך ששתיהן מודדות אותו גודל."""
    sizes = [c.size for c in chars if c.size > 0]
    return statistics.median_low(sizes) if sizes else 0.0


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
    # שם הגופן שהאות מצוירת בו (font_name), בלי תג התת-קבוצה. "": לא ידוע (או רווח שהקורא הוסיף)
    font: str = ""
    # בסוגר שהצורה שלו נקבעה מהציור: התו שבקובץ (file_bracket), כדי שהציון יידע אם הציור שינה אותו
    # (score.py, "מאמץ תיקון"). "" בכל תו אחר
    source: str = ""


@dataclass(frozen=True)
class PageChars:
    chars: list[Char]
    # אותיות שדולגו כי אין להן מיקום שאפשר להשתמש בו: FPDFText_GetCharOrigin נכשלה,
    # או שהמיקום או התיבה אינם מספר סופי. המספר הזה ייכנס לציון של העמוד.
    skipped: int
    # סוגריים שלא הצלחנו לקבוע את הצורה שלהם מהציור; נשאר בהם התו שבקובץ
    unknown_brackets: int = 0
    # מכאן: מידע לציון של העמוד (score.py), שלא משנה את הטקסט.
    # סוגריים שהצורה שלהם נקבעה מהציור (המכנה של "סוגריים שתוקנו", lines.Component.brackets_changed)
    brackets: int = 0
    # תווים שאין להם ערך Unicode בקובץ לפי PDFium עצמו, ונראים כתווים רגילים (page_reference)
    marked_unmapped: int = 0
    # תווים שהשורה שלהם אינה אופקית משמאל לימין (is_rotated)
    rotated: int = 0
    # כל התווים של העמוד לפי הרשימה של PDFium, בלי מה ש-PDFium הוסיף (page_reference). None: לא נקרא
    reference: str | None = None


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
    skipped = unknown_brackets = brackets = rotated = 0
    mirrored = mirrored_by_pdfium(textpage, document_r2l(page.pdf))
    reference, unmapped = page_reference(textpage)
    codes = [pdfium_raw.FPDFText_GetUnicode(textpage, i) for i in range(textpage.count_chars())]
    for indices, ch in characters(codes):
        if ch in "\r\n":
            continue
        i = indices[0]
        if ch in _UNICODE_UNMIRRORED and i in mirrored:
            ch = _UNICODE_UNMIRRORED[ch]  # מבטלים את השיקוף של PDFium (mirrored_by_pdfium)
        # תו של שני חצאים (אימוג'י, characters): PDFium נותן לשניהם את אותו CharInfo, כלומר אותה נקודת מוצא
        # ואותן תיבות (ProcessTextObjectItems ב-core/fpdftext/cpdf_textpage.cpp: "for (wchar_t c : unicode)
        # { charinfo.set_unicode(c); ... temp_char_list_.push_back(charinfo); }", נמדד: 26 מתוך 26). לכן המיקום
        # של התו נגזר משניהם: התיבות הן האיחוד, וקו הבסיס הוא הממוצע, ושניהם מצטמצמים לערך המשותף. כשל באחד
        # מהם הוא כשל של התו: הוא מדולג ונספר פעם אחת
        origins = []
        for index in indices:
            if not pdfium_raw.FPDFText_GetCharOrigin(textpage, index, x, y):
                break
            origins.append(y.value)
        if len(origins) < len(indices):
            skipped += 1
            continue
        # get_charbox זורקת PdfiumError בכשל (pypdfium2/_helpers/textpage.py), ואחרי
        # GetCharOrigin מוצלחת היא לא יכולה להיכשל: אותו תנאי, והמצביעים לא ריקים.
        # כך גם התיבה הרופפת (loose=True, FPDFText_GetLooseCharBox ב-fpdfsdk/fpdf_text.cpp).
        box = _union(textpage.get_charbox(index) for index in indices)
        center = (box[0] + box[2]) / 2
        # התיבה הרופפת: משמאל = נקודת המוצא, מימין = המוצא ועוד רוחב ההתקדמות של האות,
        # ולמעלה ולמטה = תיבת הגופן (GetLooseBounds ב-core/fpdftext/cpdf_textpage.cpp).
        # כשאין לאות תיבה בכלל (תיבה ריקה, למשל רווח ש-PDFium הוסיף) היא ריקה גם כאן.
        loose_left, loose_bottom, loose_right, loose_top = _union(textpage.get_charbox(index, loose=True)
                                                                  for index in indices)
        baseline = sum(origins) / len(origins)
        # הגודל, הגופן והמטריצה של החצי הראשון: לשני החצאים אותו CharInfo, כלומר אותה מטריצה ואותו אובייקט טקסט
        size = font_size(textpage, i, matrix)
        if not all(math.isfinite(v) for v in (center, baseline, loose_left, loose_bottom, loose_right, loose_top, size)):
            skipped += 1
            continue
        # המטריצה מולאה ב-font_size, והגודל סופי, כלומר הקריאה הצליחה והציר (a, b) אינו אפס
        rotated += is_rotated(matrix)
        source = ""
        if ch in FAMILIES:
            brackets += 1
            shape = drawn_shape(page, box, ch)
            if shape is None:
                unknown_brackets += 1
            else:
                source = file_bracket(ch, i in mirrored)
                ch = shape
        chars.append(Char(ch, center, baseline, loose_left, loose_right, loose_top - loose_bottom, size,
                          font_name(textpage, i), source))
    return PageChars(chars, skipped, unknown_brackets, brackets, unmapped, rotated, reference)


def _union(boxes: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """האיחוד של תיבות (left, bottom, right, top), כמו ש-get_charbox מחזירה אותן."""
    lefts, bottoms, rights, tops = zip(*boxes)
    return min(lefts), min(bottoms), max(rights), max(tops)


# טקסט מסובב: השורה של האות אינה אופקית משמאל לימין כש-|sin θ| של כיוון השורה גדול מזה (ההתייעצות על מדידה,
# סעיף 2.4: "|sin θ| > 0.01 ⇒ לא מטפלים, מסמנים"). בסט אין אף אות מסובבת (נמדד בסבב 6, כל 15 הקבצים), ולכן
# התוצאה על הסט זהה לכל ערך בין 0 ל-1, והערך נשאר זה של ההתייעצות
ROTATION_SIN = 0.01


def is_rotated(matrix: "pdfium_raw.FS_MATRIX") -> bool:
    """האם האות מצוירת בשורה שאינה אופקית משמאל לימין, לפי המטריצה האפקטיבית שלה (FPDFText_GetMatrix).

    כיוון השורה הוא העמודה (a, b) של המטריצה: x' = a·x + c·y + e, y' = b·x + d·y + f (PDF 1.7, סעיף 8.3.4).
    מסובבת: |b| גדול מ-ROTATION_SIN מאורך הציר, או a שלילי (השורה פונה שמאלה, למשל סיבוב של 180 מעלות).
    לא FPDFText_GetCharAngle: הוא מחשב atan2(c, a) (fpdfsdk/fpdf_text.cpp, ב-PDFium עד a8432342), כלומר לפי
    ההטיה ולא לפי כיוון השורה, ואות נטויה מלאכותית של Chrome (c=0.19, b=0) הייתה נספרת אצלו מסובבת.
    הקורא מסדר אותיות לפי x ומקבץ לפי קו הבסיס, ובשורה מסובבת אף אחד מהם לא נכון."""
    axis = math.hypot(matrix.a, matrix.b)
    return axis == 0 or abs(matrix.b) > ROTATION_SIN * axis or matrix.a < 0


def file_bracket(char: str, mirrored: bool) -> str:
    """התו של סוגר כמו שהוא בקובץ: מה ש-PDFium החזיר (char), בלי השיקוף שלו (mirrored_by_pdfium), באותו
    אופן שבו הקורא מבטל את השיקוף של המירכאות. השיקוף של PDFium הוא לפי bracket_shapes.PAIRS."""
    if not mirrored:
        return char
    opens_right, opens_left = FAMILIES[char]
    return opens_left if char == opens_right else opens_right


def unmapped_char(char: str) -> bool:
    """תו שאינו אות אמיתית: תו בקרה (U+0000 עד U+001F ו-U+007F עד U+009F, הקטגוריה Cc) חוץ מטאב ושבירת שורה,
    אזור השימוש הפרטי (Co, כל שלושת האזורים), או U+FFFD. מסמך האפיון, "פסילה מיידית": בסט כך יוצאות אותיות
    שאין להן מיפוי (GPS בפלאייר, U+001D עד U+001F), ובדיקה של U+FFFD בלבד הייתה מפספסת את כולן."""
    if char in "\t\n\r":
        return False
    kind = unicodedata.category(char)
    return kind in ("Cc", "Co") or char == "�"


def page_reference(textpage) -> tuple[str, int]:
    """כל התווים של העמוד לפי הרשימה של PDFium, ומספר התווים שאין להם ערך Unicode בקובץ ונראים כתווים רגילים.

    הרשימה: FPDFText_GetUnicode לכל אינדקס, חוץ ממה ש-PDFium הוסיף בעצמו (FPDFText_IsGenerated: רווחים
    ושבירות שורה), כתווים (characters). זה הטקסט שמולו נמדדת השלמות של הפלט (score.py). אותו מקור ואותה
    המרה לתווים כמו הקורא (page_chars), כך שאין שני עותקים של הכלל שיכולים להיפרד.

    "לא ממופה": FPDFText_HasUnicodeMapError. לפי core/fpdftext/cpdf_textpage.cpp, כשלגופן אין ערך Unicode
    לקוד של התו, PDFium מכניס את הקוד עצמו כתו ומסמן אותו kNotUnicode. כך האימוג'י במצגת יוצא "5" בשקופית
    13 ו-"¹" בשקופית 15: תווים שנראים רגילים, ושום בדיקה של התו עצמו לא תתפוס. נספרים כאן רק אלה שאינם תו
    לא ממופה בעצמם (unmapped_char), כי את אלה הציון סופר מהפלט, וכך תו לא נספר פעמיים. הערך -1 (שגיאה, רק
    באינדקס או בעמוד לא תקינים) הוא U+FFFD (characters), כלומר תו לא ממופה בפלט: כשל לא עובר בשקט כתו תקין."""
    indices = [i for i in range(textpage.count_chars()) if pdfium_raw.FPDFText_IsGenerated(textpage, i) != 1]
    text: list[str] = []
    unmapped = 0
    for positions, char in characters([pdfium_raw.FPDFText_GetUnicode(textpage, i) for i in indices]):
        text.append(char)
        if not unmapped_char(char) and any(pdfium_raw.FPDFText_HasUnicodeMapError(textpage, indices[k]) != 0
                                           for k in positions):
            unmapped += 1
    return "".join(text), unmapped


def characters(codes: Sequence[int]) -> list[tuple[tuple[int, ...], str]]:
    """הקודים של PDFium (FPDFText_GetUnicode, אחד לכל אינדקס) כתווים: לכל תו, המקומות שלו ברשימת הקודים, והתו.

    PDFium שומר תו שמחוץ ל-BMP (אימוג'י) כשני אינדקסים, שני החצאים של זוג UTF-16 (surrogates): הוא קורא את
    מפת התווים של הגופן (ToUnicode) ארבע ספרות הקסדצימליות לכל wchar_t (CPDF_ToUnicodeMap::StringToWideString
    ב-core/fpdfapi/font/cpdf_tounicodemap.cpp), ונותן לכל wchar_t אינדקס משלו. הסדר של שני החצאים תלוי בכיוון:
    בטבלה של PDFium החצאים הם ON, ניטרליים (core/fxcrt/fx_ucddata.inc, U+D800 עד U+DFFF), ולכן ברצף שהוא
    עובר מימין לשמאל, למשל אחרי אות עברית, הוא מעביר אותם בסדר הפוך, החצי הנמוך לפני הגבוה (CloseTempLine ב-
    core/fpdftext/cpdf_textpage.cpp), וברצף משמאל לימין בסדר הרגיל. לכן זוג סמוך מתחבר בשני הסדרים (בסט: 26
    זוגות ב-doc-6p_gdocs.pdf, כולם נמוך לפני גבוה).

    חצי בלי זוג, וקוד מחוץ לטווח של Unicode (-1, שגיאה), הם U+FFFD: אין להם תו, ובפלט הם תו לא ממופה
    (unmapped_char) ולא נעלמים. לפני כן הקורא קרא כל אינדקס דרך FPDFText_GetText (get_text_range), שמחזיר
    UCS-2, ו-pypdfium2 מפענח אותו עם errors="ignore" (pypdfium2/_helpers/textpage.py): חצי בודד אינו UTF-16
    תקין, ולכן נעלם בשקט, ואיתו האימוג'י. בכל שאר 267,760 האינדקסים בסט שתי הדרכים מחזירות אותו תו (נמדד בסבב 6ב)."""
    out: list[tuple[tuple[int, ...], str]] = []
    k = 0
    while k < len(codes):
        pair = sorted(codes[k:k + 2])
        if len(pair) == 2 and 0xD800 <= pair[0] <= 0xDBFF and 0xDC00 <= pair[1] <= 0xDFFF:
            high, low = pair
            out.append(((k, k + 1), chr(0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00))))
            k += 2
            continue
        code = codes[k]
        valid = 0 <= code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF
        out.append(((k,), chr(code) if valid else "�"))
        k += 1
    return out


# תג של תת-קבוצת גופן: שש אותיות לטיניות גדולות ו-"+" לפני שם הגופן (PDF 1.7, סעיף 9.6.4, Font Subsets).
# אותו גופן שהוטמע פעמיים בתת-קבוצות שונות מקבל תגים שונים, ובלי להוריד אותו הוא היה נראה כשני גופנים
_SUBSET_TAG = re.compile(r"[A-Z]{6}\+")


def font_name(textpage, index: int) -> str:
    """שם הגופן של האות (FPDFText_GetFontInfo), בלי תג התת-קבוצה; "" כשהקריאה נכשלה.

    לפי public/fpdf_text.h: הערך המוחזר הוא האורך של השם כולל ה-NUL בסוף, בבייטים, ו-0 בכשל; ורק כשהוא
    לא גדול מאורך החוצץ, החוצץ מקבל את השם (UTF-8). לכן קודם שואלים את האורך ואז קוראים. (FPDFText_GetFontWeight
    לא בשימוש: הוא מחזיר 400 גם לגופן מודגש ב-WeasyPrint; markdown.py.) ב-Chrome השם ריק לכל האותיות."""
    length = pdfium_raw.FPDFText_GetFontInfo(textpage, index, None, 0, None)
    if length <= 0:
        return ""
    buffer = ctypes.create_string_buffer(length)
    if pdfium_raw.FPDFText_GetFontInfo(textpage, index, buffer, length, None) != length:
        return ""
    name = buffer.value.decode("utf-8", errors="replace")
    return name[7:] if _SUBSET_TAG.match(name) else name


# התווים ש-PDFium משקף (GetMirrorChar, core/fxcrt/fx_unicode.cpp, kFXTextLayoutBidiMirror) ו-Unicode לא
# מגדיר כמשתקפים (Bidi_Mirrored=No): מתוך 366 הערכים בטבלה של PDFium, רק ארבע המירכאות האלה (נבדק מול
# unicodedata.mirrored, Unicode 15.1). כל אחת והתו שהיא הופכת אליו. שאר התווים בטבלה הם סוגריים שהצורה
# שלהם נקבעת מהציור (bracket_shapes.py), או תווים שאינם בסט
_UNICODE_UNMIRRORED = {"\u2018": "\u2019", "\u2019": "\u2018", "\u201c": "\u201d", "\u201d": "\u201c"}
_WEAK = frozenset({"AN", "EN", "NSM", "CS", "ES", "ET", "BN"})


def document_r2l(pdf) -> bool:
    """האם במסמך ViewerPreferences/Direction הוא R2L, כמו ש-FPDFText_LoadPage קובע את rtl_ של
    CPDF_TextPage (fpdfsdk/fpdf_text.cpp: CPDF_ViewerPreferences::IsDirectionR2L). נקרא דרך
    FPDF_VIEWERREF_GetName, שמחזיר את האורך כולל ה-NUL, ו-0 כשאין מפתח כזה או כשהערך אינו שם (name)
    (fpdfsdk/fpdf_view.cpp, CPDF_ViewerPreferences::GenericName)."""
    length = pdfium_raw.FPDF_VIEWERREF_GetName(pdf, b"Direction", None, 0)
    if length <= 0:
        return False
    buffer = ctypes.create_string_buffer(length)
    if pdfium_raw.FPDF_VIEWERREF_GetName(pdf, b"Direction", buffer, length) != length:
        return False
    return buffer.value == b"R2L"


def mirrored_by_pdfium(textpage, r2l: bool) -> set[int]:
    """האינדקסים של התווים בעמוד ש-PDFium שיקף, לפי התווים שהוא מחזיר (FPDFText_GetUnicode) ולפי השורות
    שהוא יצר (התווים "\r" ו-"\n" שהוא הוסיף, FPDFText_IsGenerated). התנאי עצמו ב-_mirrored_in_lines."""
    sequence = []
    for i in range(pdfium_raw.FPDFText_CountChars(textpage)):
        char = chr(pdfium_raw.FPDFText_GetUnicode(textpage, i))
        sequence.append((char, char in "\r\n" and pdfium_raw.FPDFText_IsGenerated(textpage, i) == 1))
    return _mirrored_in_lines(sequence, r2l)


def _direction(char: str) -> str:
    """הכיוון של תו כמו ב-CFX_BidiChar::AppendChar (core/fxcrt/fx_bidi.cpp): L, R (גם AL), W (חלש: AN,
    EN, NSM, CS, ES, ET, BN) או N (כל השאר). לפי Bidi_Class של unicodedata; ל-PDFium טבלה משלו
    (core/fxcrt/fx_ucddata.inc), ובתווים שבסט הן מסכימות (נבדק: 217 מתוך 217 מירכאות, tests/test_chars.py),
    חוץ מחצאים של זוג UTF-16 (characters): בטבלה של PDFium כל 2,048 החצאים הם ON, ו-unicodedata נותן להם L.
    בסט אלה 52 החצאים של האימוג'י ב-doc-6p_gdocs.pdf, ובלי זה הרצף אחרי אימוג'י בשורה עברית היה נחשב
    משמאל לימין. הטבלאות שונות עוד ב-1,023 תווים ב-BMP (רובם תווים שנוספו ל-Unicode אחרי הטבלה של PDFium),
    ואף אחד מהם אינו בסט (נמדד בסבב 6ב, על כל אינדקס בכל 15 הקבצים)."""
    if 0xD800 <= ord(char) <= 0xDFFF:
        return "N"
    kind = unicodedata.bidirectional(char)
    if kind == "L":
        return "L"
    if kind in ("R", "AL"):
        return "R"
    return "W" if kind in _WEAK else "N"


def _mirrored_in_lines(sequence: Sequence[tuple[str, bool]], r2l: bool) -> set[int]:
    """האינדקסים ש-PDFium העביר ב-AddCharInfo עם is_rtl, ולכן שיקף (GetMirrorChar), לפי
    CPDF_TextPage::CloseTempLine בגרסה שבתוך pypdfium2 5.13.0 (PDFium 153.0.7999.0, הענף chromium/7999,
    core/fpdftext/cpdf_textpage.cpp). sequence: לכל תו בעמוד, (התו, האם הוא שבירת שורה ש-PDFium יצר).

    PDFium בונה את העמוד בשורות זמניות, וסוגר שורה (CloseTempLine) כשהוא מוסיף שבירת שורה ("\r\n")
    ובסוף העמוד. בכל שורה הוא מחלק את התווים לרצפים של אותו כיוון (_direction), ועובר עליהם לפי הסדר,
    עם "כיוון נוכחי" שמתחיל משמאל לימין, או מימין לשמאל כשהמסמך R2L (r2l): רצף R, ורצף N כשהכיוון הנוכחי
    מימין לשמאל, עוברים בשיקוף והכיוון הנוכחי נהיה מימין לשמאל; רצף L מחזיר אותו לשמאל לימין, ורצף W לא
    משנה אותו. כשהמסמך R2L, הרצפים מתהפכים (SetOverallDirectionRight) לפני המעבר.
    הסדר שבו PDFium מחזיר את התווים הוא סדר המעבר: כל רצף, ורצפים סמוכים שומרים על הכיוון שלהם, ולכן
    החלוקה לרצפים על התווים שהוא מחזיר היא החלוקה שהוא עבר עליה (גם כשהוא הפך את סדר התווים ברצף או
    את סדר הרצפים). בגרסה קודמת של PDFium (עד 2025) הכיוון הכללי נקבע גם לפי מספר הרצפים בכל כיוון
    (auto_order); בגרסה הזו לא, ו-5 מתוך 217 מירכאות בסט מכריעות בין השתיים."""
    mirrored: set[int] = set()
    line: list[tuple[int, str]] = []

    def close():
        segments: list[tuple[str, list[int]]] = []
        for index, char in line:
            direction = _direction(char)
            if segments and segments[-1][0] == direction:
                segments[-1][1].append(index)
            else:
                segments.append((direction, [index]))
        current = "R" if r2l else "L"
        for direction, indices in segments:
            if direction == "R" or (direction == "N" and current == "R"):
                current = "R"
                mirrored.update(indices)
            elif direction != "W":
                current = "L"

    for index, (char, line_break) in enumerate(sequence):
        if line_break:
            close()
            line = []
        else:
            line.append((index, char))
    close()
    return mirrored


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
