"""בדיקת הסדר של טבלת התיוג: האם "הטקסט הנכון", כשמציגים אותו, נראה כמו השורה בעמוד.

אדם שמתייג בודק תוכן: מילה חסרה, מילה מיותרת. את הסדר בודקת המכונה, כי סדר של עברית
ואנגלית מעורבת קשה לבדוק בעין, ותיוג שגוי בסדר הופך שורה נכונה של הקורא ל"שגויה".

השיטה: כל תא של הטקסט הנכון מוצג בנפרד באלגוריתם התצוגה, בפסקה מימין לשמאל, והתאים
מונחים זה לצד זה מימין לשמאל (התא הראשון בסדר הקריאה הוא הימני ביותר). התוצאה מושווית
לשורה בעמוד (Line.visual: התווים כמו שהם בעמוד, משמאל לימין) שיש לה הכי הרבה תווים
משותפים עם הטקסט הנכון. הרווחים לא נספרים: הבדיקה היא על הסדר ועל התווים, ואת הרווחים
בודקים התיוג עצמו והבדיקות של hebrew_pdf/spacing.py.

אלגוריתם התצוגה הוא זה של החבילה (hebrew_pdf/logical_order.drawn), שהקורא מאמת בו את
עצמו, ולא עותק נוסף שלו. הוא מיישם גם את כלל L4 (שיקוף סוגריים), ולכן נבדק גם הכיוון
של כל סוגר מול הצורה המצוירת בעמוד, ולא רק המקום שלו. (python-bidi, שבו משתמשת בדיקת
התצוגה של הקורא, לא מיישם L4; ראו harness/display_check.py.) שהסדר של drawn זהה לזה של
python-bidi, מימוש שלא חולק איתו קוד, נבדק על כל שורה בסט (tests/test_display_check.py).

התוצאות האפשריות:
- שורה שלמה: הטקסט הנכון מוצג בדיוק כמו השורה בעמוד.
- חלק מהשורה: הוא מוצג כמו רצף בתוך השורה. כך כשהקורא מדביק לשורה אחת כמה עמודות או
  תיבות, והשורה המתויגת היא רק אחת מהן (ראו "שורה אחת" ב-testset/labels.md).
- סדר שונה: כל התווים נמצאים בשורה, אבל לא בסדר הזה. זה תיוג שגוי בסדר.
- חסר בעמוד: יש בטקסט הנכון תווים שאין בשורה. בסט זה טקסט שנראה בעמוד אבל לא קיים בקובץ
  (GPS בפלאייר, אימוג'י במצגת), או מילה שהמתייג הוסיף.
- לא נבדק: השורה בעמוד נקראה בפסקה משמאל לימין (מסמך שרובו לא עברי). drawn מציג רק
  בפסקה מימין לשמאל, ובסט הבדיקה אין מסמך כזה.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from harness.textdiff import without_spaces
from hebrew_pdf.lines import Line
from hebrew_pdf.logical_order import drawn

WHOLE_LINE = "שורה שלמה"
PART_OF_LINE = "חלק מהשורה"
OTHER_ORDER = "סדר שונה"
MISSING = "חסר בעמוד"
NOT_CHECKED = "לא נבדק"


@dataclass(frozen=True)
class OrderCheck:
    kind: str
    missing: str = ""  # ב-MISSING: התווים של הטקסט הנכון שאין בשורה, לפי סדר הקריאה

    @property
    def ok(self) -> bool:
        return self.kind in (WHOLE_LINE, PART_OF_LINE)


def shown(cells: Sequence[str]) -> str:
    """הטקסט הנכון כמו שהוא נראה בעמוד, משמאל לימין, בלי רווחים: כל תא מוצג בפסקה מימין
    לשמאל, והתאים מימין לשמאל."""
    return without_spaces("".join("".join(drawn(list(cell))[1]) for cell in reversed(cells)))


def check_label_order(cells: Sequence[str], lines: Sequence[Line]) -> OrderCheck:
    """בדיקת הסדר של תיוג אחד מול השורות של העמוד שלו (כמו שהקורא קיבץ אותן).

    cells: הטקסט הנכון כתאים, לפי סדר הקריאה (harness.labels.Label.expected).
    בתיקו בין שתי שורות עם אותו מספר תווים משותפים, נבחרת העליונה.
    """
    target = shown(cells)
    wanted = Counter(target)
    if not lines:
        return OrderCheck(MISSING, _in_reading_order(wanted, cells))
    best = max(lines, key=lambda line: sum((Counter(without_spaces(line.visual)) & wanted).values()))
    if not best.rtl:
        return OrderCheck(NOT_CHECKED)
    page = without_spaces(best.visual)
    if target == page:
        return OrderCheck(WHOLE_LINE)
    if target in page:
        return OrderCheck(PART_OF_LINE)
    missing = wanted - Counter(page)
    if not missing:
        return OrderCheck(OTHER_ORDER)
    return OrderCheck(MISSING, _in_reading_order(missing, cells))


def _in_reading_order(missing: Counter, cells: Sequence[str]) -> str:
    """התווים החסרים לפי הסדר שבו הם בטקסט הנכון, ולא לפי הסדר שבעמוד (שבו מילה עברית
    הפוכה). מה שלא נמצא כך, למשל סוגר שהצורה שלו אחרי שיקוף אחרת, נוסף בסוף."""
    left = Counter(missing)
    out = []
    for char in without_spaces("".join(cells)):
        if left[char] > 0:
            out.append(char)
            left[char] -= 1
    out.extend(left.elements())
    return "".join(out)
