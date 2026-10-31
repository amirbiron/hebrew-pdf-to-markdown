"""גבולות בין רכיבים בשורה (תאים, תיבות, תגים), עמודות של טבלה, ואיחוד שורות של טבלה.

הקלט הוא השורות של עמוד, כל אחת כתווים בסדר שבעמוד עם רווח בכל פער בין מילים
(spacing.space_by_gaps: רווח שהקורא הכניס הוא Char(" ") בלי גובה, שממלא את הפער).

1. הפער הרגיל בין מילים בעמוד: הפער הנפוץ ביותר, כחלק מגובה השורה שלו (usual_word_gap).
   הנפוץ ולא החציון: בעמוד של טבלה יש לפעמים יותר פערים בין תאים מאשר בין מילים
   (נמדד: בעמוד 2 של קובץ הטבלאות החציון הוא פי 5 מהרווח), אבל הרווחים בין מילים
   מתקבצים סביב ערך אחד והפערים בין תאים מפוזרים.

2. פער של פי COMPONENT_GAP (10, סדר גודל) מהפער הרגיל הוא גבול בין רכיבים בכל מקרה.
   למה לא פחות: בשורות של טקסט רגיל יש פערים של עד פי 7.3 שאינם גבול ("הופקה
   ב-11/05/2026 · בתוקף עד 25/05/2026", שורה 13 בתיוג), ותבליטים של Google Docs עם
   פער של פי 8-9. הגבולות הברורים בסט (שורות 2, 8, 11, 21, הפלאייר, כותרות של טבלאות)
   הם מפי 13 ומעלה.

3. פער קטן יותר הוא גבול רק כשהוא חלק מעמודה: מסדרון ריק אנכי שחוזר בשורות רצופות
   (column_corridors). בטבלה עם עמודה רחבה ושם ארוך שממלא אותה, הפער בין התאים הוא רק
   הריפוד של התאים (נמדד בקובץ הטבלאות: מפי 3), כמו תבליט. ההבדל הוא במבנה: מסדרון
   של טבלה מתחיל בפער של פי 10 לפחות באחת השורות, ונמשך כל עוד אף שורה רצופה לא חוצה
   אותו בטקסט. בשורה שבתוכו, פער של פי COLUMN_GAP לפחות שמכיל את המסדרון הוא גבול.
   קווי מסגרת לא נדרשים, כי בדוח הכספי אין מסגרות מלאות.

4. טבלה: מסדרון שיש בו פער אמיתי (לא רק שוליים) בשתי שורות לפחות. השורות בטווח הזה
   מקבלות תא לכל עמודה, ותא ריק לעמודה שאין בה טקסט בשורה. איחוד שורות בעמוד לשורת
   טבלה אחת נמצא ב-lines.table_rows.

5. איפה טבלה נגמרת (_rows_of_the_table): שורה קצרה, כמו כותרת בצד ימין, לא חוצה את העמודות
   שמשמאלה, ולכן המסדרון ממשיך לתוכה. מה שמבדיל אותה הוא גודל האות: שורה במסדרון שאין בה פער
   של ממש (לא שורה של הטבלה עצמה), ושהגודל שלה (החציון של Char.size) לא שווה (chars.SAME_SIZE)
   לאף גודל של אות בשורות שתומכות במסדרון, מסיימת אותו. "אף גודל" ולא "הגודל של השורות": בשורה של
   טבלה יש כמה גדלים (בקובץ הטבלאות טקסט ב-6 נקודות וקוד ב-5.5).
   ובטבלה שיש בה קווי מסגרת (קו בין שורה שלה לשורה שמעליה), גודל אחר לבדו לא מספיק: צריך גם קו בין
   השורה לשורה הסמוכה של הטבלה. כך שורת המשך בתוך תא, שכולה קוד בטבלה שאין בשורות שלה קוד ("דרך
   FPDFText_GetCharOrigin" במסמך האפיון), נשארת בטבלה: בתוך תא אין קו. כותרת אחרי טבלה מופרדת ממנה
   בקו התחתון של השורה האחרונה. קווי המסגרת לבדם לא מספיקים: כותרת בין שתי טבלאות יושבת בין הקו
   התחתון של האחת לקו העליון של השנייה, כמו שורה של שורה אחת.

בלי שום סף לתוכנה מסוימת: כל הספים יחסיים לפער הרגיל בעמוד ולגובה השורה.
"""

import bisect
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from hebrew_pdf.chars import Char, same_size

# בדיקת רגישות (סבב 5, כל הסט): לכל ערך של COMPONENT_GAP בין 7.4 ל-13.25 התוצאה זהה (35 מתוך
# 40 תיוגים, אותם תאים בקובץ הטבלאות, אותה בדיקת תצוגה). שני הקצוות הם שני פערים מדודים: ב-7.3
# הפער של פי 7.3 בשורה 13 נהיה גבול, ומ-13.5 הגבול של שורה 31 בפלאייר (פי 13.43) נעלם. 10 באמצע.
COMPONENT_GAP = 10.0
# בדיקת רגישות (סבב 5ב, כל הסט כולל קובץ הטבלאות החדש ומסמך האפיון, אחרי שכלל הרוחב ירד): לכל ערך
# של COLUMN_GAP בין 1.5 ל-2.9 התוצאה זהה (התיוגים, התאים בשלושת הקבצים עם דף תשובות, הטבלאות, הכותרות
# והפסקאות). ב-1.4 פסקה אחת משתנה, ומ-3.0 הריפוד בין תאים במסמך האפיון מ-Chrome כבר לא נחשב גבול (2
# תאים, ו-24 ב-3.6). הערך באמצע הטווח. (בסבב 5, על קובץ הטבלאות הקודם, הטווח היה 1.9 עד 3.3 והערך 2.0.)
COLUMN_GAP = 2.2
# שני פערים "שווים" כשהיחס ביניהם עד 1.25: כך מתקבצים הרווחים של גופן אחד (ב-WeasyPrint הם
# זהים, וביישור לשני הצדדים של Google Docs הם משתנים בעד כ-20%)
_SAME_GAP = 1.25
# פחות פערים מזה בעמוד לא נותנים פער רגיל משלו, ונלקח הפער הרגיל של המסמך
MIN_PAGE_GAPS = 20
# שורה רצופה במסדרון: המרחק בין קווי הבסיס עד פי 3 מגובה השורה. בטבלה, בין שורות של
# תאים שונים יש ריפוד ומסגרת (נמדד בקובץ הטבלאות: כפי 1.8). בדיקת רגישות (סבב 5): התוצאה זהה
# לכל ערך בין 2.5 ל-5; ב-2.25 כבר 30 תאים בקובץ הטבלאות משתנים
_MAX_LINE_STEP = 3.0


@dataclass(frozen=True)
class Gap:
    index: int  # המקום ברשימת התווים של השורה: התו Char(" ") שהקורא הכניס בפער
    left: float
    right: float
    ratio: float  # רוחב הפער כחלק מגובה השורה


@dataclass(frozen=True)
class PageLine:
    """שורה לפני הפיצול לרכיבים: התווים בסדר שבעמוד עם רווח בכל פער (spacing.SpacedRow)."""
    chars: list[Char]
    baseline: float
    height: float  # החציון של גובה התווים בשורה; 0 בשורה בלי גובה
    gaps: list[Gap]

    @property
    def left(self) -> float:
        return min(c.left for c in self.chars)

    @property
    def right(self) -> float:
        return max(c.right for c in self.chars)

    @property
    def size(self) -> float:
        """החציון של גודל האות (Char.size) בתווים שיש להם גודל; 0 כשאין כאלה."""
        sizes = [c.size for c in self.chars if c.size > 0]
        return statistics.median(sizes) if sizes else 0.0


def page_line(chars: list[Char]) -> PageLine:
    heights = [c.height for c in chars if c.height > 0]
    height = statistics.median(heights) if heights else 0.0
    gaps = [Gap(i, c.left, c.right, (c.right - c.left) / height)
            for i, c in enumerate(chars) if height and c.text == " " and c.height == 0]
    return PageLine(chars, chars[0].baseline if chars else 0.0, height, gaps)


def usual_word_gap(ratios: Sequence[float]) -> float | None:
    """הפער הנפוץ ביותר: הערך שיש הכי הרבה פערים "שווים" לו (_SAME_GAP). בתיקו, הקטן."""
    values = sorted(ratios)
    best_count, best = 0, None
    for value in values:
        count = bisect.bisect_right(values, value * _SAME_GAP) - bisect.bisect_left(values, value / _SAME_GAP)
        if count > best_count:
            best_count, best = count, value
    return best


@dataclass(frozen=True)
class PageLayout:
    boundaries: list[set[int]]  # לכל שורה: האינדקסים של הפערים שהם גבול בין רכיבים
    # לכל שורה בטבלה: גבולות העמודות (מסדרונות) שעוברים בה, משמאל לימין; None מחוץ לטבלה.
    # לכל שורה העמודות שלה: כותרת שמרוכזת מעל שתי עמודות יוצרת מסדרונות משלה, שלא חלים
    # על שורות הנתונים שמתחתיה
    columns: list[tuple[tuple[float, float], ...] | None]
    tables: list[int | None]  # לכל שורה: מספר הטבלה (שורות רצופות עם עמודות), או None


def page_layout(lines: Sequence[PageLine], word_gap: float | None,
                rules: Sequence[tuple[float, float, float]] = ()) -> PageLayout:
    """הגבולות בין רכיבים בכל שורה של העמוד, והעמודות של הטבלאות. word_gap: הפער הרגיל (usual_word_gap).
    rules: הקווים האופקיים שמצוירים בעמוד (lines.horizontal_rules), לסוף של טבלה (סעיף 5)."""
    boundaries: list[set[int]] = [set() for _ in lines]
    columns: list[tuple[tuple[float, float], ...] | None] = [None] * len(lines)
    if not word_gap:
        return PageLayout(boundaries, columns, [None] * len(lines))
    spans: list[tuple[int, int, tuple[float, float], set[int]]] = []
    found = []  # (שורת הזרע, הבלוק, המסדרונות, התמיכה) לכל פער גדול
    for i, line in enumerate(lines):
        for gap in line.gaps:
            if gap.ratio < COMPONENT_GAP * word_gap:
                continue
            boundaries[i].add(gap.index)
            found.append((i, *_corridor(lines, i, gap, word_gap)))
    # השורות של הטבלאות בעמוד: כל שורה שתומכת במסדרון כלשהו בעמוד, גם אם לא במסדרון שהיא בו (שורת
    # היחידות "באלפי ש\"ח" בדוח הכספי ריקה בעמודה הראשונה, אבל תומכת במסדרונות שבין העמודות האחרות)
    table_rows = set().union(*(rows for *_, support in found for rows in support.values()))
    for i, block, corridors, support in found:
        block = _rows_of_the_table(lines, block, i, table_rows, rules)
        support = {corridor: rows & set(block) for corridor, rows in support.items()}
        for j in block:
            for other in lines[j].gaps:
                if other.ratio >= COLUMN_GAP * word_gap and any(other.left <= a and b <= other.right
                                                                 for a, b in corridors):
                    boundaries[j].add(other.index)
        for corridor in corridors:
            rows = sorted(support[corridor])
            # טבלה: פער של ממש באותו מסדרון בשתי שורות לפחות. הטווח שלה מהשורה הראשונה
            # שתומכת בו ועד סוף המסדרון למטה: שורות ההמשך של שורת הטבלה האחרונה (תיאור
            # שנשבר) לא חוצות אותו, אבל גם אין בהן פער בתוכו
            if len(rows) >= 2:
                spans.append((rows[0], max(rows[-1], block[-1]), corridor, support[corridor]))
    for i in range(len(lines)):
        here = sorted((corridor, rows) for first, last, corridor, rows in spans if first <= i <= last)
        if here:
            columns[i] = _distinct(lines, here)
    tables: list[int | None] = []
    for i, line_columns in enumerate(columns):
        if line_columns is None:
            tables.append(None)
        else:
            tables.append(tables[-1] if tables and tables[-1] is not None else i)
    return PageLayout(boundaries, columns, tables)


def _corridor(lines: Sequence[PageLine], seed: int, gap: Gap, word_gap: float):
    """המסדרון האנכי שמתחיל בפער seed: השורות הרצופות שאף אחת מהן לא חוצה אותו בטקסט.

    מחזירה: השורות, המסדרונות (המסדרון יכול להתפצל כשבשורה יש שני פערים בתוכו), ולכל
    מסדרון השורות שבהן יש בו פער של ממש (ולא רק שוליים, מחוץ לטקסט של השורה).
    """
    corridors = [(gap.left, gap.right)]
    support = {corridors[0]: {seed}}
    block = [seed]
    for step in (1, -1):
        previous = seed
        j = seed + step
        while 0 <= j < len(lines) and corridors:
            line = lines[j]
            limit = _MAX_LINE_STEP * max(line.height, lines[previous].height)
            if not line.height or abs(line.baseline - lines[previous].baseline) > limit:
                break
            # המקומות הפנויים בשורה: פערים של פי COLUMN_GAP לפחות (שורה שתומכת במסדרון), ומה
            # שמחוץ לטקסט שלה משני הצדדים (פנוי, אבל לא תמיכה: אין שם פער בין שני רכיבים)
            free = [(g.left, g.right, True) for g in line.gaps if g.ratio >= COLUMN_GAP * word_gap]
            free += [(-math.inf, line.left, False), (line.right, math.inf, False)]
            narrowed, kept_support = [], {}
            for a, b in corridors:
                for left, right, supports in free:
                    lo, hi = max(a, left), min(b, right)
                    if lo < hi:
                        narrowed.append((lo, hi))
                        kept_support[(lo, hi)] = support[(a, b)] | ({j} if supports else set())
            if not narrowed:
                break
            corridors, support = narrowed, kept_support
            block.append(j)
            previous = j
            j += step
    return sorted(block), corridors, support


def _rows_of_the_table(lines: Sequence[PageLine], block: list[int], seed: int, table_rows: set[int],
                       rules) -> list[int]:
    """השורות הרצופות סביב seed במסדרון, עד השורה הראשונה (בכל כיוון) שלא שייכת לטבלה (סעיף 5 בראש
    הקובץ): שורה שלא תומכת באף מסדרון בעמוד (table_rows), שהגודל שלה לא שווה לאף גודל של אות בשורות
    של הטבלה שבמסדרון, ובטבלה עם קווי מסגרת, שיש קו בינה לבין השורה הסמוכה של הטבלה. שורה בלי גודל
    (0) לא מסיימת."""
    rows = table_rows & set(block)
    sizes = {c.size for j in rows for c in lines[j].chars if c.size > 0}
    framed = any(rule_between(lines[j - 1], lines[j], rules) for j in rows if j - 1 in block)

    def foreign(j: int, neighbor: int) -> bool:
        size = lines[j].size
        if j in rows or size <= 0 or any(same_size(size, s) for s in sizes):
            return False
        if not framed:
            return True
        above, below = (lines[neighbor], lines[j]) if neighbor < j else (lines[j], lines[neighbor])
        return rule_between(above, below, rules)

    start = block.index(seed)
    end = start
    while start > 0 and not foreign(block[start - 1], block[start]):
        start -= 1
    while end + 1 < len(block) and not foreign(block[end + 1], block[end]):
        end += 1
    return block[start:end + 1]


def rule_between(above: PageLine, below: PageLine, rules: Sequence[tuple[float, float, float]]) -> bool:
    """האם קו אופקי (lines.horizontal_rules: שמאל, ימין, y) מצויר בין שתי שורות בעמוד, בתחום האופקי של
    השורה התחתונה: מתחת לקו הבסיס של העליונה בחמישית מגובה השורה (מתחת לאותיות היורדות), ומעל קו
    הבסיס של התחתונה בשש עשיריות מגובה השורה. (הועבר כמו שהוא מ-lines._new_rows, סבב 4.)"""
    top, bottom = below.baseline + 0.6 * below.height, above.baseline - 0.2 * above.height
    return any(top < y < bottom and left < below.right and right > below.left for left, right, y in rules)


def _distinct(lines: Sequence[PageLine], corridors) -> tuple[tuple[float, float], ...]:
    """גבולות העמודות של שורה, מהמסדרונות שעוברים בה: שני מסדרונות סמוכים הם שני גבולות
    רק כשיש עמודה ביניהם, כלומר שורה שבה יש טקסט בין שניהם ופער של ממש בשניהם (כמו "3א"
    בעמודת "באור" בדוח הכספי). אחרת הם אותו גבול: מסדרון שהתפצל סביב טקסט של שורה אחרת,
    למשל כותרת שמרוכזת מעל שתי עמודות. corridors: (מסדרון, השורות שתומכות בו), ממוינים."""
    merged: list[tuple[tuple[float, float], set[int]]] = []
    for corridor, rows in corridors:
        if merged:
            (a, b), previous_rows = merged[-1]
            between = any(any(b <= c.left and c.right <= corridor[0] for c in lines[j].chars if c.text != " ")
                          for j in previous_rows & rows)
            if not between:
                merged[-1] = ((a, max(b, corridor[1])), previous_rows | rows)
                continue
        merged.append((corridor, set(rows)))
    return tuple(corridor for corridor, _ in merged)


def split_components(line: PageLine, boundaries: set[int]) -> list[list[Char]]:
    """התווים של השורה, מחולקים לרכיבים בגבולות, בסדר שבעמוד משמאל לימין. בלי הרווח שבגבול."""
    parts: list[list[Char]] = [[]]
    for i, char in enumerate(line.chars):
        if i in boundaries:
            parts.append([])
        else:
            parts[-1].append(char)
    return [part for part in parts if part]


def column_of(component: Sequence[Char], columns: Sequence[tuple[float, float]]) -> int:
    """מספר העמודה של רכיב, משמאל לימין: כמה גבולות עמודה (אמצע המסדרון) יש משמאל למרכז שלו."""
    center = (min(c.left for c in component) + max(c.right for c in component)) / 2
    return sum(1 for left, right in columns if (left + right) / 2 <= center)
