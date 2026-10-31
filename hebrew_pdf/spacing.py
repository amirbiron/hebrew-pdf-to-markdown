"""רווחים בין מילים לפי הפער בעמוד, ולא לפי תווי הרווח שבקובץ.

למה לא לפי הקובץ: בסט הבדיקה תווי הרווח לא אמינים, ובכל תוכנה בצורה אחרת:
- Illustrator: הרווח של "ומה איתך" מצויר בתוך המילה ("ומהא יתך"), ובין המילים יש פער
  בלי תו רווח.
- Google Docs ו-Chrome: הרווח שליד סוגר נמצא בצד הלא נכון שלו ("לצ׳טבוט) לפני").
- Aspose: רווחים ברוחב מלא שמצוירים בתוך מילה ("מפעיל וי ות") או על סוגר ("( 08)").
- WeasyPrint: בכותרת עם ריווח אותיות יש תו רווח, ברוחב אפס, בין כל שתי אותיות.
מה שאמין הוא מה שמצויר: הפער בין האותיות בעמוד.

הכלל: כל תווי הרווח שבקובץ יורדים (גם רווחים ש-PDFium הוסיף בעצמו, FPDFText_IsGenerated),
ורווח אחד נכנס בכל פער בין שני תווים סמוכים שגדול מהפער הרגיל בין אותיות באותה שורה,
ועוד חצי רוחב רווח (HALF_SPACE).

הפער נמדד בתיבה הרופפת (Char.left, Char.right): מהקצה הימני של כל מה שמשמאל, עד הקצה
השמאלי של התו הבא. בתיבה הרופפת אותיות בלי ריווח נוגעות זו בזו, כלומר הפער ביניהן 0
(נמדד: בתוך מילה, בכל התוכנות בסט). המקסימום של כל מה שמשמאל, ולא רק של התו הקודם,
כי תיבות יכולות לחפוף.

הפער הרגיל בין אותיות: החציון התחתון של הפערים בין שתי אותיות סמוכות, אותיות של ממש
(קטגוריה L ב-Unicode), לא ספרות ולא סימנים. בשורה רגילה הוא 0, ובכותרת עם ריווח אותיות
הוא הריווח. למה רק אותיות: בשורה של מילים קצרות, כמו "2 / 8" או "- 4 -", כל הפערים הם
בין מילים. חציון של כל הפערים היה אז פער בין מילים, אף פער לא היה גדול ממנו, וכל הרווחים
היו נעלמים. בשורה בלי שתי אותיות סמוכות אין עדות לריווח אותיות, והפער הרגיל הוא 0.
החציון התחתון ולא החציון הרגיל: בשורה כמו "We R AI" חצי מהזוגות הם בין מילים, והחציון
הרגיל (הממוצע של שני האמצעיים) היה מקרב את הסף לפער בין המילים.

מה לא מטופל: שורה שמערבבת כותרת עם ריווח אותיות וטקסט רגיל מקבלת פער רגיל אחד, ורווח
בטקסט הרגיל שקטן מהסף של הכותרת ייעלם. פער גדול מאוד, בין תאים בטבלה או בין עמודות,
מקבל רווח אחד כמו כל פער, ו-layout.py מחליט אם הוא גבול בין רכיבים.
"""

import statistics
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from hebrew_pdf.chars import Char

# חצי רוחב רווח, כחלק מגובה התיבה של התווים בשורה (החציון של Char.height). כלומר רווח
# הוא בערך 0.2 מהגובה. נמדד על תווי הרווח שמצוירים ברוחב בסט: החציון בכל תוכנה בין 0.15
# ל-0.27 מהגובה. התוצאה על כל הסט זהה לכל ערך בין 0.06 ל-0.125: אותן 40 שורות מתויגות,
# ומספר הרווחים שירדו ונוספו בכל תוכנה משתנה בפחות מ-5. הערך כאן באמצע הטווח, ולא כוון
# על שורה. מתחת ל-0.06 נכנסים רווחים בין סוגר לאות ב-Google Docs (הפער שם עד 0.055),
# ומעל 0.125 נעלמים רווחים בין מילים במצגת (הפער שם מ-0.11).
#
# למה לא רוחב הרווח של הגופן עצמו: PDFium מחזיר אותו (FPDFFont_GetGlyphWidth), אבל לגופן
# בלי תו רווח הוא מחזיר בשקט את רוחב ברירת המחדל, ריבוע שלם (core/fpdfapi/font/cpdf_cidfont.h,
# default_width_ = 1000). ב-Chrome כך יוצא רווח של 0.7 מהגובה, וכל הרווחים בקובץ היו
# נעלמים. ולמה לא רוחב תווי הרווח שמצוירים בשורה: ב-Google Docs וב-Chrome הם ברוחב אפס,
# ובשאר הסט זה משנה רק שתי שורות, ובשתיהן לרעה ("4.1.לאור").
HALF_SPACE = 0.1


def is_space(text: str) -> bool:
    """תו רווח: קטגוריה Zs ב-Unicode (רווח, רווח קשיח U+00A0 וכו'), או טאב.

    לא str.isspace(): הוא מחשיב גם את U+001C עד U+001F, ובקבצים אלה אותיות שמופו בטעות
    (ה-? של "ומה איתך?" בפלאייר). הם תווים לכל דבר, והפער סביבם נמדד כרגיל.
    """
    return len(text) == 1 and (text == "\t" or unicodedata.category(text) == "Zs")


def _is_letter(text: str) -> bool:
    return len(text) == 1 and unicodedata.category(text).startswith("L")


@dataclass(frozen=True)
class SpaceCounts:
    """כמה הריווח לפי הפער שונה מתווי הרווח שבקובץ. נספר לכל פער בין שני תווים סמוכים."""

    in_file: int = 0  # פערים שהיה בהם תו רווח בקובץ
    dropped: int = 0  # מתוכם: פערים שלא נכנס בהם רווח
    added: int = 0  # פערים שלא היה בהם תו רווח בקובץ, ונכנס בהם רווח

    def __add__(self, other: "SpaceCounts") -> "SpaceCounts":
        return SpaceCounts(self.in_file + other.in_file, self.dropped + other.dropped, self.added + other.added)


@dataclass(frozen=True)
class SpacedRow:
    chars: list[Char]  # בסדר שבעמוד, משמאל לימין: בלי תווי הרווח שבקובץ, ועם רווח בכל פער בין מילים
    counts: SpaceCounts


def space_by_gaps(visual: Sequence[Char]) -> SpacedRow:
    """התווים של שורה, בסדר שבעמוד משמאל לימין, עם רווחים לפי הפערים בעמוד.

    שורה שבה לאף תו אין גובה לא נותנת קנה מידה לפער. בסט אין שורה כזו; אם תהיה, הרווחים
    שלה נשארים כמו בקובץ (רווח אחד במקום רצף), כי זו העדות היחידה, והיא לא נספרת כשינוי.
    """
    glyphs: list[Char] = []
    space_before: list[bool] = []  # האם היה תו רווח בקובץ בין התו הזה לתו שלפניו
    pending = False
    for c in visual:
        if is_space(c.text):
            pending = True
            continue
        space_before.append(pending and bool(glyphs))
        glyphs.append(c)
        pending = False

    heights = [c.height for c in glyphs if c.height > 0]
    if not heights:
        kept: list[Char] = []
        for k, glyph in enumerate(glyphs):
            if space_before[k]:
                kept.append(_space_between(glyphs[k - 1].right, glyph))
            kept.append(glyph)
        return SpacedRow(kept, SpaceCounts(in_file=sum(space_before)))

    gaps: list[float] = []
    edges: list[float] = []  # הקצה הימני של כל מה שמשמאל לכל פער
    right = glyphs[0].right
    for c in glyphs[1:]:
        edges.append(right)
        gaps.append(c.left - right)
        right = max(right, c.right)
    letter_gaps = [gap for gap, a, b in zip(gaps, glyphs, glyphs[1:]) if _is_letter(a.text) and _is_letter(b.text)]
    usual = statistics.median_low(letter_gaps) if letter_gaps else 0.0
    threshold = usual + HALF_SPACE * statistics.median(heights)

    out = [glyphs[0]]
    in_file = dropped = added = 0
    for k in range(1, len(glyphs)):
        word_gap = gaps[k - 1] > threshold
        if word_gap:
            out.append(_space_between(edges[k - 1], glyphs[k]))
        in_file += space_before[k]
        dropped += space_before[k] and not word_gap
        added += word_gap and not space_before[k]
        out.append(glyphs[k])
    return SpacedRow(out, SpaceCounts(in_file, dropped, added))


def _space_between(left_edge: float, after: Char) -> Char:
    """תו רווח שממלא את הפער, בלי גובה (הוא לא נכנס לחישוב הגובה של השורה)."""
    return Char(" ", (left_edge + after.left) / 2, after.baseline, left_edge, after.left, 0.0)
