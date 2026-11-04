"""הציון של עמוד: החלטה (תקין, לא בטוח, נפסל) ורשימת סיבות קצרות שאדם קורא.

זה מבנה נתונים נפרד מה-Markdown, והוא רק מתאר: הוא לא מתקן ולא משנה את הפלט. ההחלטות לפי מסמך האפיון, סעיף
"הציון והסימון": כמה צירים ולא מספר אחד, כי ציון אחד מערבב שאלות שונות ואז אין דרך לדעת מה נכשל.

פסילה מיידית, בלי ציון (_rejection): עמוד בלי טקסט (תמונה), טקסט מסובב (chars.is_rotated), או תו שאינו אות
אמיתית: תו בקרה, אזור השימוש הפרטי או U+FFFD בפלט (chars.unmapped_char), או תו ש-PDFium עצמו מסמן כחסר ערך
Unicode בקובץ ונראה כתו רגיל (chars.page_reference: האימוג'י שיוצא "5" במצגת). תו אחד מספיק: הוא תוכן שנמצא
בעמוד ולא בפלט, ובמקומו בפלט תו אחר.

שלושה צירים. שניים מהם, סבירות ושלמות, מחליטים: עמוד "לא בטוח" כשאחד מהם נכשל. השלישי, מאמץ התיקון, הוא הערה
(מסבב 6ב): מידע שמוצג למשתמש ולא משנה את ההחלטה. סיבה והערה הם שני שדות נפרדים במבנה (PageScore.reasons,
PageScore.notes):

1. סבירות (_plausibility): האם הטקסט נראה כמו עברית ועברית-אנגלית תקינה. רק מה שמגיע ל-Markdown נבדק:
   שורה שירדה ככותרת עליונה או תחתונה לא מוצגת למשתמש, ואזהרה עליה הייתה מפנה לשורה שאינה בפלט (במצגת
   כל השורות הדו-משמעיות הן שורת התחתית שחוזרת ב-23 שקופיות).
   - בדיקת התצוגה (shows_as_page): רכיב שלא מוצג כמו העמוד. זו עובדה ולא סימן: הפלט שלו בוודאות לא ייראה כמו
     העמוד, ולכן רכיב אחד מספיק.
   - מסבב 6ב, גם כן אחד מספיק: מספר שכתוב במפרידי אלפים ולא בצורה תקינה שלהם (bad_digit_groups), ותא עם כמה
     מספרים בעמודה של מספרים (crowded_cells). אלה כשלים שבהם כל שורה עדיין מוצגת כמו העמוד (מספרים שנדבקו,
     שורות או עמודות של טבלה שהתאחדו), ולכן בדיקת התצוגה לא רואה אותם. נכנסו להחלטה כי לא סימנו אף עמוד ידוע
     כנכון (harness/calibration.py).
   - סימנים, כשיעור של מילים: אותיות סופיות במקום לא נכון (final_letter_anomaly), מספרים בצורה של מספר הפוך
     (reversed_numbers), שורה שמתחילה בסימן פיסוק (indirect_checks.punct_at_start), סוגר בלי זוג בעמוד
     (unpaired_brackets), ושורה דו-משמעית (lines.Line.ambiguous). כל סימן הוא מילה אחת לא סבירה. הציון הוא הגבול
     התחתון של רווח בר-סמך Wilson לשיעור המילים הסבירות (wilson_lower), ולא השיעור עצמו: 9 מתוך 9 נותן 0.70,
     ו-200 מתוך 200 נותן 0.98, כך שעמוד קצר לא מקבל ביטחון שלא הרוויח. הציר נכשל מתחת ל-MIN_PLAUSIBLE.
     עמוד קצר (מסבב 6ב, Signals.decides): עמוד שגם בלי אף סימן הציון שלו מתחת לסף, כלומר הסימנים לא יכולים
     להכריע בו לכאן או לכאן (פחות מ-14 מילים בסף של היום). בעמוד כזה הסימנים לא משתתפים בהחלטה, והעמוד
     מקבל הערה "עמוד קצר" עם מה שנמצא. עד סבב 6ב עמוד קצר היה "לא בטוח" רק בגלל האורך (11 עמודים בסט, בלי
     שום בעיה שנמצאה). בדיקת התצוגה, השלמות והפסילה הן עובדות ולא סטטיסטיקה, ועובדות גם על שורה אחת.
2. שלמות (_completeness): התווים של כל הפלט של העמוד, בלי סדר ובלי רווחים, מול כל התווים של העמוד לפי PDFium
   (lines.PageText.reference). תו שנשר או שהוכפל הוא כשל. סוגר נחשב בלי הכיוון שלו (הקורא קובע אותו מהציור), וכך
   גם מירכאות (הקורא מבטל את השיקוף של PDFium). כאן נבדק כל הפלט של הקורא, גם מה שירד מה-Markdown: זה ציר של
   הקורא, ואת הירידה עצמה בודק מערך הבדיקה (harness/markdown_check.py).
3. מאמץ תיקון (_effort), הערה ולא סיבה: כמה מההחלטות של הקורא שינו את מה שבקובץ: רווחים שהורדו ונוספו
   (spacing.SpaceCounts), סוגריים שהציור הכריע בהם נגד התו שבקובץ (lines.Component.brackets_changed), סוגריים
   שהצורה שלהם לא נקבעה, ואותיות שדולגו כי אין להן מיקום. הציון הוא הגבול התחתון של Wilson לשיעור התיקונים,
   והעמוד מקבל הערה מעל MAX_EFFORT. למה הערה (סבב 6ב): הסף מכוון למדגם (הטווח היציב 0.106 עד 0.107), והעמוד
   היחיד בסט מעליו הוא שקופית 7 במצגת, ש-18 הסוגריים בה נקבעו מהציור, כלומר הקורא עשה עבודה נכונה. ואין עדיין
   ראיה שהמאמץ מנבא שגיאות: השחתה של הפלט לא משנה אותו, ולכן אף שגיאה מכוונת לא נמדדת בו. כשתהיה ראיה כזו, הוא
   יחזור להחלטה.

הספים נקבעו בכיול ולא לפי מה שנותן מספרים יפים על הסט (harness/calibration.py): שגיאות מכוונות ברמת הפלט,
השארת תוכנה אחת בחוץ, ורגישות. הנימוקים והמספרים ליד כל סף.

בלי AI כשופט (מסמך האפיון), ובלי שום כלל לתוכנה מסוימת או לקובץ מסוים.
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from hebrew_pdf.bracket_shapes import FAMILIES
from hebrew_pdf.chars import _UNICODE_UNMIRRORED, unmapped_char
from hebrew_pdf.indirect_checks import FINAL_LETTERS, punct_at_start
from hebrew_pdf.lines import Component, PageText
from hebrew_pdf.logical_order import _BRACKET_PAIRS, drawn
from hebrew_pdf.markdown import _marker

OK = "תקין"
UNSURE = "לא בטוח"
REJECTED = "נפסל"
DECISIONS = (OK, UNSURE, REJECTED)

# רווח בר-סמך של 95% (z של התפלגות נורמלית). מסמך האפיון: "9 מתוך 9 מילים תקינות נותן בערך 0.70"
Z = 1.96
# הסף של הסבירות: הגבול התחתון לשיעור המילים הסבירות. כיול (harness/calibration.py; הדוח, "כיול"), מסבב 6ב:
# - שגיאות מכוונות: על 28 העמודים הידועים כנכונים בלי כשל ודאי (מסבב 6ב: רק עמודים שהפלט שלהם זהה לדף התשובות,
#   harness/tables.pages_matching_truth, ולא כל העמודים של קובץ עם דף תשובות), כשכל השורות בעמוד הפוכות (היפוך
#   שורה שלמה, היפוך אותיות בתוך מילה), האחוזון ה-95 של הציון הוא 0.747. מעל זה הסימנים לבדם תופסים 95% מהעמודים
#   האלה. בשאר הצורות, ובשורה הפוכה אחת בעמוד, הסימנים כמעט לא תופסים, ואת אלה תופסת בדיקת התצוגה (100% בכל
#   צורה): הסימנים הם גיבוי שלא נשען על המיקומים, ולא הבדיקה העיקרית.
# - רגישות: ההחלטות והסיבות בכל הסט זהות לכל ערך מעל 0.736 ועד 0.790 (העמודים בקצוות: עמוד 25 בקובץ הטבלאות, 3
#   שורות דו-משמעיות ב-29 מילים, ועמוד 9 במסמך האפיון בשתי התוכנות). הדרישה בתוך הטווח, והאמצע שלו מעליה, ולכן
#   הערך הוא האמצע (calibration.chosen_range). עד סבב 6ב הערך היה 0.774, באמצע של 0.757 עד 0.790: עמוד קצר בלי
#   סימן (שקופית 1 במצגת, 12 מילים) היה מסומן, וקבע את הקצה 0.757. בשני הערכים אותן החלטות ואותן סיבות בכל הסט.
# - עמוד קצר: פחות מ-13 מילים, שבהן גם בלי שום סימן הציון מתחת לסף (n / (n + z²); Signals.decides). בעמוד כזה
#   הסימנים לא מכריעים, והוא מקבל הערה.
# - השארת תוכנה בחוץ: הדרישה מהעמודים של שאר התוכנות בין 0.729 ל-0.787, והסימנים תפסו בה 55 מתוך 56 עמודים
#   הפוכים של התוכנה שבחוץ. רוב העמודים הידועים כנכונים הם של WeasyPrint ו-Chrome (23 מתוך 28), ולשאר התוכנות
#   יש עמוד אחד או שניים כאלה או אף לא אחד, כך שהבדיקה על תוכנה אחרת דקה
MIN_PLAUSIBLE = 0.763
# הסף של הערת מאמץ התיקון (מסבב 6ב הערה, ולא סיבה: ראו בראש הקובץ, ציר 3): הגבול התחתון לשיעור ההחלטות של הקורא
# ששינו את הקובץ. השחתה של הפלט לא משנה אותו (הוא נמדד מול הקובץ), ולכן אין לו שגיאות מכוונות. הכלל: המאמץ הגבוה ביותר בעמוד שהפלט שלו ידוע כנכון, כי עד שם יש ראיה
# שהתיקונים של הקורא עובדים. בסט זה 0.106 (הצעת המחיר, עמוד 1: כותרת עם ריווח אותיות, שתויגה), והערך באמצע הטווח
# היציב שמכיל אותו.
# זה דגל ולא ערך: ההתפלגות של המאמץ רציפה (אין בה פער גדול מ-0.01 בין 0.02 ל-0.12), הטווח היציב הוא 0.106 עד
# 0.107 בלבד, והמעטפת נקבעת לפי עמוד אחד: כשמשאירים את WeasyPrint בחוץ היא 0.092. מעליו בסט: שקופית 7 במצגת,
# שכל 18 הסוגריים בה הפוכים לתו שבקובץ (Canva שומר את הצורה המצוירת). עמודים מתויגים מקבצים שתוקנו הרבה (Google
# Docs, Canva) היו מרחיבים את המעטפת על סמך ראיה
MAX_EFFORT = 0.1066


def wilson_lower(successes: int, total: int, z: float = Z) -> float:
    """הגבול התחתון של רווח בר-סמך Wilson לשיעור successes מתוך total. 0 כשאין אף ניסיון: אין ראיה.

    https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval
    זורקת ValueError על ספירה שלילית או successes גדול מ-total: אלה באג אצל הקורא, ולא שיעור."""
    if total < 0 or not 0 <= successes <= total:
        raise ValueError(f"שיעור לא תקין: {successes} מתוך {total}")
    if total == 0:
        return 0.0
    p = successes / total
    z2 = z * z
    centre = p + z2 / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total))
    return max(0.0, (centre - margin) / (1 + z2 / total))


def visible_chars(text: str) -> Counter:
    """האותיות של טקסט בלי רווחים: קטגוריה Zs ב-Unicode, וטאב, שבירת שורה ושבירת עמוד. לא str.isspace(), שמחשיב
    גם את U+001C עד U+001F, ובקבצים אלה אותיות שמופו בטעות (harness/textdiff.py). גם מערך הבדיקה סופר כך."""
    return Counter(char for char in text if char not in "\t\n\r\f\v" and unicodedata.category(char) != "Zs")


# ---------- סימנים של סבירות ----------

# גרש וגרשיים, וכל תו שמשמש במקומם בסט: ' " ׳ ״ ’ ‘ ” “ ו-`. בתוך מילה הם מסמנים ראשי תיבות ("בע"מ") או מילה
# לועזית ("צ'אט"), ובשניהם האות שלפניהם אינה סוף מילה
_GERESH = "'\"׳״’‘”“`"
_POINTS = "֑-ׇ"  # טעמים וניקוד: חלק מהמילה, לא אות
_WORD = re.compile(rf"[א-ת][א-ת{_POINTS}]*(?:[{_GERESH}][א-ת][א-ת{_POINTS}]*)*")
# האותיות שיש להן צורה סופית, בצורה הרגילה. בלי פ: "וואטסאפ", "טיפ" ו-"לופ" נכתבים בסט בפ רגילה (נמדד בסבב
# 6: 37 מילים כאלה בטקסט נקי, ואף אחת לא שגויה)
_FINAL_FORMS = "כמנצ"


def final_letter_anomaly(word: str) -> bool:
    """מילה עברית (_WORD) שהאותיות הסופיות בה לא במקום: אות סופית (ך ם ן ף ץ) לפני סוף המילה, או אחת מ-כ מ נ צ
    בצורה הרגילה בסוף מילה בלי גרש וגרשיים. במילה הפוכה ("תוריכממ") שתיהן קורות; בטקסט תקין רק בשתי מילים
    שנדבקו ("בינייםלא" בדוח הכספי), שגם הן פלט שגוי. ראשי תיבות ("בע"מ", "סה"כ") ומילים לועזיות עם גרש
    מסתיימים בצורה הרגילה, ולכן הכלל השני לא חל עליהם."""
    letters = [char for char in word if "א" <= char <= "ת"]
    if len(letters) < 2:
        return False
    if any(char in FINAL_LETTERS for char in letters[:-1]):
        return True
    return letters[-1] in _FINAL_FORMS and not any(char in _GERESH for char in word)


_NUMBER = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
# הצורות של מספר מעוצב אחרי היפוך תו-תו: "1,234.56" הופך ל-"65.432,1" (שבר עשרוני ואחריו מפרידי אלפים), ו-"12,345"
# הופך ל-"543,21" (קבוצה אחרונה של פחות משלוש ספרות אחרי מפריד אלפים)
_REVERSED_DECIMAL = re.compile(r"[0-9]+\.(?:[0-9]{3},)+[0-9]{1,3}")
_REVERSED_THOUSANDS = re.compile(r"(?:[0-9]{3},)+[0-9]{1,2}")
_YEARS = range(1900, 2100)


def reversed_numbers(text: str) -> int:
    """כמה מספרים בטקסט נראים כמו מספר הפוך: "65.432,1", "543,21", או שנה הפוכה ("5202"): ארבע ספרות שאינן שנה,
    שההיפוך שלהן הוא שנה, ובלי סימן מינוס לפניהן (שנה אינה שלילית: "-1002" הוא מזהה, לא 2001 הפוך). ספרות אינן
    סימטריות, ולכן היפוך של מספר כמעט לא קורה במקרה (ההתייעצות על מדידה, סעיף 1.3)."""
    count = 0
    for found in _NUMBER.finditer(text):
        number = found.group(0)
        if _REVERSED_DECIMAL.fullmatch(number) or _REVERSED_THOUSANDS.fullmatch(number):
            count += 1
        elif (len(number) == 4 and number.isdigit() and int(number) not in _YEARS and int(number[::-1]) in _YEARS
              and not text[:found.start()].endswith(("-", "+", "−"))):
            count += 1
    return count


# ---------- מספרים ותאים של מספרים (סבב 6ב) ----------

# מספר עם מפרידים: ספרות, ונקודות או פסיקים ביניהן
_FORMATTED = re.compile(r"[0-9]+(?:[.,][0-9]+)+")
# מספר במפרידי אלפים תקין: עד שלוש ספרות, קבוצות של שלוש אחרי כל פסיק, ולכל היותר נקודה עשרונית אחת בסוף
_THOUSANDS = re.compile(r"[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?")


def bad_digit_groups(text: str) -> int:
    """כמה מספרים בטקסט כתובים במפרידי אלפים (פסיק שאחריו בדיוק שלוש ספרות) ולא בצורה תקינה שלהם (_THOUSANDS):
    קבוצה של יותר או פחות משלוש ספרות אחרי פסיק, או יותר מנקודה עשרונית אחת. ההתייעצות על ארכיטקטורה, סעיף
    2.6: "בדיקת קבוצות ספרות (מפריד אלפים במקום הנכון, נקודה עשרונית אחת)". כך יוצאים שני מספרים שנדבקו
    ("146,137449,413" בדוח הכספי בסבב 5). רק מספר שיש בו מפריד אלפים: מספר עם נקודות בלבד הוא גם גרסה, תאריך
    או כתובת IP ("3.12.1", "11.05.2026", "127.0.0.1"), ופסיקים בין ספרות בודדות הם רשימה ("1,2,3"). מספר שנראה
    הפוך ("65.432,1", "543,21") אין בו קבוצה של שלוש אחרי פסיק, ולכן הוא לא נספר כאן פעם שנייה (reversed_numbers).
    בסט: 0 בכל העמודים (נמדד בסבב 6ב)."""
    count = 0
    for found in _FORMATTED.finditer(text):
        number = found.group(0)
        groups = re.split(r"[.,]", number)
        separators = re.findall(r"[.,]", number)
        thousands = any(sep == "," and len(groups[k + 1]) == 3 for k, sep in enumerate(separators))
        if thousands and not _THOUSANDS.fullmatch(number):
            count += 1
    return count


# תא של מספר אחד: מספר עם סימן לפניו או אחריו (מינוס, סוגריים של מספר שלילי, מטבע, אחוז, כוכבית של הערה)
_CELL_NUMBER = re.compile(r"[(\-−+]?[₪$€£]*[0-9]+(?:[.,][0-9]+)*[%*)]*")


def _one_number(cell: str) -> bool:
    return bool(_CELL_NUMBER.fullmatch(cell.strip(" ")))


def _several_numbers(cell: str) -> bool:
    parts = cell.split()
    return len(parts) >= 2 and all(_CELL_NUMBER.fullmatch(part) for part in parts)


def crowded_cells(rows: Sequence[tuple[str, ...]]) -> int:
    """כמה תאים בטבלה (rows: השורות שלה, כתאים) מכילים כמה מספרים ורק מספרים, בעמודה של מספרים: עמודה שרוב
    התאים הלא ריקים בה הם מספר אחד (_one_number), ולפחות שניים. ההתייעצות על ארכיטקטורה, סעיף 2.6: בטבלה אין
    "סדר טקסט", יש גריד, והבדיקה של תא מספרי היא הצורה של המספר. תא כזה הוא שתי שורות שהתאחדו ("23,479 69" בדוח
    הכספי) או שני תאים שנכנסו לאותה עמודה ("178,881 145,921"). בעמודה של טקסט שני מספרים בתא הם טקסט רגיל."""
    crowded = 0
    width = max((len(row) for row in rows), default=0)
    for column in range(width):
        cells = [row[column] for row in rows if column < len(row) and row[column].strip(" ")]
        singles = sum(_one_number(cell) for cell in cells)
        if singles >= 2 and 2 * singles > len(cells):
            crowded += sum(_several_numbers(cell) for cell in cells)
    return crowded


def _page_crowded_cells(page: PageText) -> int:
    """crowded_cells לכל טבלה בעמוד, לפי השורות שלה כמו שהן נקראות (PageText.rows, אחרי איחוד השורות)."""
    tables: dict[int, list[tuple[str, ...]]] = {}
    for cells, source in zip(page.rows, page.sources):
        if source.table is not None:
            tables.setdefault(source.table, []).append(tuple(cells))
    return sum(crowded_cells(rows) for rows in tables.values())


_CLOSERS = {closer: opener for opener, closer in _BRACKET_PAIRS.items()}


def unpaired_brackets(texts: Iterable[str]) -> int:
    """סוגריים בלי זוג, כשקוראים את הטקסטים לפי הסדר: סוגר שלא נפתח, ופותח שלא נסגר עד הסוף. הזוגות של
    BidiBrackets.txt, כמו באלגוריתם התצוגה (logical_order._BRACKET_PAIRS). לפי העמוד ולא לפי שורה, כי סוגריים
    נפתחים בשורה אחת ונסגרים בבאה. לא נספרים: הסימן של פריט ברשימה ("1)", "א)"), וסוגר שצמוד ל-":" או ל-";"
    לפניו, פרצוף (":)"). כך נתפס "(₪3.60 :(DALL-E 3 API" ב-Google Docs, שעובר את בדיקת התצוגה."""
    stack: list[str] = []
    unpaired = 0
    for text in texts:
        marked = _marker(text)
        if marked is not None and marked[0].endswith(")"):
            text = marked[1]
        for i, char in enumerate(text):
            if i and text[i - 1] in ":;" and (char in _BRACKET_PAIRS or char in _CLOSERS):
                continue
            if char in _BRACKET_PAIRS:
                stack.append(char)
            elif char in _CLOSERS:
                if stack and stack[-1] == _CLOSERS[char]:
                    stack.pop()
                else:
                    unpaired += 1
    return unpaired + len(stack)


def tokens(text: str) -> int:
    """מספר המילים בטקסט: רצפים בין רווחים שיש בהם לפחות אות או ספרה."""
    return sum(1 for token in text.split(" ") if any(char.isalnum() for char in token))


def _spaces_collapsed(text: str) -> str:
    return re.sub(" +", " ", text).strip(" ")


def shows_as_page(component: Component) -> bool:
    """האם הטקסט של הרכיב, כשמציגים אותו באלגוריתם התצוגה של החבילה (logical_order.drawn, כולל שיקוף סוגריים),
    בכיוון שבו הוא נקרא, נראה בדיוק כמו התווים שלו בעמוד (Component.visual). רצף רווחים הוא רווח אחד, ורווחים
    בקצוות לא נספרים: את המקום של רווח לא בודקים כאן (ראו harness/display_check.py). רכיב שנקרא בפסקה משמאל לימין
    (מסמך שרובו לא עברי, בלי עברית בשורה) מוצג כמו שהוא. אותה בדיקה ש-to_logical עושה לכל קריאה, אבל על הטקסט
    עצמו: כך היא בודקת גם פלט ששונה אחרי הקריאה (שגיאות מכוונות, harness/calibration.py)."""
    shown = "".join(drawn(list(component.text))[1]) if component.rtl else component.text
    return _spaces_collapsed(shown) == _spaces_collapsed(component.visual)


# ---------- המבנה שיוצא ----------

@dataclass(frozen=True)
class Signals:
    """הסימנים של סבירות בעמוד, כל אחד כמספר המילים שהוא הופך ללא סבירות."""
    words: int
    ambiguous: int = 0  # רכיבים שבהם כמה קריאות מוצגות כמו העמוד, וברירת המחדל הכריעה
    final_letters: int = 0
    reversed_numbers: int = 0
    punctuation: int = 0  # רכיבים שמתחילים בסימן פיסוק
    brackets: int = 0  # סוגריים בלי זוג

    @property
    def suspicious(self) -> int:
        return min(self.words, self.ambiguous + self.final_letters + self.reversed_numbers + self.punctuation
                   + self.brackets)

    @property
    def score(self) -> float:
        return wilson_lower(self.words - self.suspicious, self.words)

    def decides(self, min_plausible: float) -> bool:
        """האם בעמוד יש מספיק מילים כדי שהסימנים יכריעו: גם בלי אף סימן, הציון שלו (n / (n + z²)) מגיע לסף.
        אחרת הוא מתחת לסף בכל מקרה, כלומר התוצאה לא תלויה בסימנים, ואין בהם ראיה לכאן או לכאן (עמוד קצר).
        הגבול נגזר מהסף ולא נקבע בנפרד: 14 מילים בסף של היום (min_words)."""
        return wilson_lower(self.words, self.words) >= min_plausible


def min_words(min_plausible: float) -> int:
    """מספר המילים הקטן ביותר שבו הסימנים יכולים להכריע (Signals.decides)."""
    words = 0
    while wilson_lower(words, words) < min_plausible:
        words += 1
    return words


@dataclass(frozen=True)
class Plausibility:
    display_failures: int  # רכיבים שלא מוצגים כמו העמוד (shows_as_page)
    signals: Signals
    # מסבב 6ב, כמו בדיקת התצוגה, אחד מספיק: מספרים עם קבוצות ספרות לא תקינות (bad_digit_groups), ותאים עם כמה
    # מספרים בעמודה של מספרים (crowded_cells). שתיהן לא סימנו אף עמוד ידוע כנכון (harness/calibration.py)
    bad_numbers: int = 0
    crowded_cells: int = 0

    def ok(self, min_plausible: float) -> bool:
        """אין כשל ודאי (שורה שלא מוצגת כמו העמוד, מספר או תא מספרי לא תקינים), והסימנים עוברים את הסף, או
        שהעמוד קצר מכדי שיכריעו."""
        return (not self.display_failures and not self.bad_numbers and not self.crowded_cells
                and (not self.signals.decides(min_plausible) or self.signals.score >= min_plausible))


@dataclass(frozen=True)
class Completeness:
    missing: Counter  # תווים של העמוד לפי PDFium שאינם בפלט
    extra: Counter  # תווים בפלט שאינם בעמוד לפי PDFium

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra


@dataclass(frozen=True)
class Effort:
    spaces_changed: int  # רווחים שהורדו ונוספו
    space_decisions: int  # פערים שהיה בהם תו רווח בקובץ, ועוד פערים שנוסף בהם רווח
    brackets_changed: int
    brackets: int
    unknown_brackets: int
    skipped: int

    @property
    def corrections(self) -> int:
        return self.spaces_changed + self.brackets_changed + self.unknown_brackets + self.skipped

    @property
    def decisions(self) -> int:
        return self.space_decisions + self.brackets + self.skipped

    @property
    def score(self) -> float:
        return wilson_lower(self.corrections, self.decisions)

    def ok(self, max_effort: float) -> bool:
        return self.score <= max_effort


# הסוג של כל סיבה, ושם קצר שלו לסיכומים (harness/run.py). הסוג יציב, והטקסט של הסיבה הוא מה שאדם קורא
REASON_KINDS = {
    "no_text": "עמוד בלי טקסט",
    "rotated": "טקסט מסובב",
    "unmapped": "תווים לא ממופים",
    "display": "שורות שלא מוצגות כמו העמוד",
    "final_letters": "אותיות סופיות במקום לא נכון",
    "reversed_numbers": "מספרים שנראים הפוכים",
    "brackets": "סוגריים בלי זוג",
    "punctuation": "פיסוק בתחילת שורה",
    "ambiguous": "שורות דו-משמעיות",
    "missing": "תווים שחסרים בפלט",
    "extra": "תווים שנוספו לפלט",
    "digit_groups": "מספרים עם קבוצות ספרות לא תקינות",
    "crowded_cells": "תאים עם כמה מספרים בעמודה של מספרים",
}
REJECTING = frozenset({"no_text", "rotated", "unmapped"})
# הסוג של כל הערה: מידע שמוצג למשתמש ולא משנה את ההחלטה (סבב 6ב)
NOTE_KINDS = {
    "short": "עמוד קצר",
    "effort": "הרבה תיקונים",
}


@dataclass(frozen=True)
class Reason:
    kind: str  # מפתח ב-REASON_KINDS
    text: str  # המשפט לאדם, בעברית, עם המספרים

    def __post_init__(self):
        if self.kind not in REASON_KINDS:
            raise ValueError(f"סוג סיבה לא מוכר: {self.kind}")


@dataclass(frozen=True)
class Note:
    """הערה: מידע על העמוד שמוצג למשתמש ולא משנה את ההחלטה."""
    kind: str  # מפתח ב-NOTE_KINDS
    text: str  # המשפט לאדם, בעברית, עם המספרים

    def __post_init__(self):
        if self.kind not in NOTE_KINDS:
            raise ValueError(f"סוג הערה לא מוכר: {self.kind}")


@dataclass(frozen=True)
class PageScore:
    """הציון של עמוד. decision אחד מ-DECISIONS, ו-reasons הן הסיבות, לפי הסדר. בעמוד שנפסל אין צירים (None):
    פסילה היא בלי ציון. החלטה שאינה "תקין" בלי סיבה, או "תקין" עם סיבה, לא נוצרת (ValueError), וגם לא "נפסל"
    בלי סיבה של פסילה (REJECTING) או "לא בטוח" עם סיבה כזו. notes: הערות, בכל החלטה, נפרדות מהסיבות: הן לא
    נספרות בהחלטה."""
    decision: str
    reasons: tuple[Reason, ...]
    plausibility: Plausibility | None = None
    completeness: Completeness | None = None
    effort: Effort | None = None
    notes: tuple[Note, ...] = ()

    def __post_init__(self):
        if self.decision not in DECISIONS:
            raise ValueError(f"החלטה לא מוכרת: {self.decision}")
        if (self.decision == OK) != (not self.reasons):
            raise ValueError(f"החלטה בלי סיבה, או סיבה בלי החלטה: {self.decision}")
        rejecting = [reason.kind in REJECTING for reason in self.reasons]
        if self.decision == REJECTED and not all(rejecting) or self.decision == UNSURE and any(rejecting):
            raise ValueError(f"סיבה שלא מתאימה להחלטה: {self.decision}")


# ---------- הניסוח של הסיבות ----------

def _many(count: int, one: str, many: str) -> str:
    """"שורה אחת שלא מוצגת..." או "3 שורות שלא מוצגות...": one עם "אחת" או "אחד" כבר בפנים."""
    return one if count == 1 else f"{count} {many}"


def _signal_phrases(signals: Signals) -> list[tuple[str, str]]:
    """(סוג, משפט) לכל סימן שנמצא בעמוד, לפי הסדר."""
    phrases = []
    for kind, count, one, many in (
            ("final_letters", signals.final_letters, "מילה אחת עם אות סופית במקום לא נכון",
             "מילים עם אות סופית במקום לא נכון"),
            ("reversed_numbers", signals.reversed_numbers, "מספר אחד שנראה הפוך", "מספרים שנראים הפוכים"),
            ("brackets", signals.brackets, "סוגר אחד בלי זוג", "סוגריים בלי זוג"),
            ("punctuation", signals.punctuation, "שורה אחת שמתחילה בסימן פיסוק", "שורות שמתחילות בסימן פיסוק"),
            ("ambiguous", signals.ambiguous, "שורה אחת ששני סדרים שלה נראים זהה", "שורות ששני סדרים שלהן נראים זהה")):
        if count:
            phrases.append((kind, _many(count, one, many)))
    return phrases


def _signal_reasons(signals: Signals) -> list[Reason]:
    """הסיבות של עמוד שהסימנים הכריעו בו (Signals.decides) ושהציון שלו מתחת לסף: יש בו לפחות סימן אחד."""
    # האורך של העמוד הוא חלק מהסיבה: אותו סימן אחד מפיל עמוד של 20 מילים ולא עמוד של 200 (wilson_lower)
    return [Reason(kind, phrase + ", בעמוד של " + _many(signals.words, "מילה אחת", "מילים"))
            for kind, phrase in _signal_phrases(signals)]


def _short_note(signals: Signals, min_plausible: float) -> Note:
    found = _signal_phrases(signals)
    text = (f"עמוד קצר: {_many(signals.words, 'מילה אחת', 'מילים')} (פחות מ-{min_words(min_plausible)}), מעט מדי כדי "
            "שהסימנים של הסבירות יכריעו לכאן או לכאן")
    if found:
        text += ". נמצא: " + ", ".join(phrase for _, phrase in found)
    return Note("short", text)


# ---------- הציון ----------

_FOLD = {char: pair[0] for char, pair in FAMILIES.items()}
_FOLD.update({char: min(char, other) for char, other in _UNICODE_UNMIRRORED.items()})


def _folded(text: str) -> Counter:
    """visible_chars, כשכל תו של זוג (סוגר, מירכאות) נספר כתו הראשון של הזוג. לא מילון שנבנה מחדש מהמונה: שני
    התווים של זוג נופלים לאותו מפתח, ואחד מהם היה דורס את השני."""
    return Counter(_FOLD.get(char, char) for char in text if visible_chars(char))


def _all_text(page: PageText) -> str:
    return "".join(part.text for line in page.lines for part in line.parts)


def _shown(page: PageText, dropped: frozenset) -> tuple[list[Component], list[str]]:
    """מה שמגיע ל-Markdown: הרכיבים (לבדיקת התצוגה ולדו-משמעות), והטקסטים לפי סדר הקריאה, תא של טבלה אחרי
    האיחוד של השורות שלו (PageText.rows), כמו שהוא נקרא בפלט. dropped: (שורה, רכיב) שירדו ככותרת עליונה או
    תחתונה (markdown.Markdown.dropped)."""
    parts = [part for i, line in enumerate(page.lines) for j, part in enumerate(line.parts) if (i, j) not in dropped]
    texts = []
    for cells, source in zip(page.rows, page.sources):
        if source.table is not None:
            texts.extend(cells)
        else:
            texts.extend(cell for j, cell in enumerate(cells) if (source.lines[0], j) not in dropped)
    return parts, texts


def _plausibility(page: PageText, dropped: frozenset) -> Plausibility:
    parts, texts = _shown(page, dropped)
    failures = sum(1 for part in parts if _spaces_collapsed(part.visual) and not shows_as_page(part))
    words = sum(tokens(text) for text in texts)
    signals = Signals(
        words,
        ambiguous=sum(part.ambiguous for part in parts),
        final_letters=sum(final_letter_anomaly(word) for text in texts for word in _WORD.findall(text)),
        reversed_numbers=sum(reversed_numbers(text) for text in texts),
        punctuation=sum(punct_at_start(text) for text in texts),
        brackets=unpaired_brackets(texts),
    )
    return Plausibility(failures, signals, sum(bad_digit_groups(text) for text in texts), _page_crowded_cells(page))


def _completeness(page: PageText) -> Completeness:
    if page.reference is None:
        raise ValueError("אין לעמוד טקסט ייחוס (PageText.reference), ואי אפשר למדוד שלמות")
    output = _folded(_all_text(page))
    reference = _folded(page.reference)
    return Completeness(reference - output, output - reference)


def _effort(page: PageText) -> Effort:
    spacing = page.spacing
    return Effort(spacing.dropped + spacing.added, spacing.in_file + spacing.added, page.brackets_changed,
                  page.brackets, page.unknown_brackets, page.skipped_chars)


def _rejection(page: PageText) -> list[Reason]:
    """הסיבות לפסילה מיידית. ריק: העמוד לא נפסל."""
    reasons = []
    text = _all_text(page)
    if not visible_chars(text) and not visible_chars(page.reference or ""):
        reasons.append(Reason("no_text", "עמוד בלי טקסט (כנראה תמונה): אין מה לחלץ ממנו"))
    if page.rotated_chars:
        reasons.append(Reason("rotated", _many(page.rotated_chars, "תו אחד בטקסט מסובב", "תווים בטקסט מסובב") +
                              ": הקורא לא בונה שורות לטקסט כזה"))
    unmapped = sum(unmapped_char(char) for char in text) + page.marked_unmapped
    if unmapped:
        reasons.append(Reason("unmapped", _many(unmapped, "תו אחד שלא ממופה בקובץ", "תווים שלא ממופים בקובץ") +
                              ": במקום האות שבעמוד יוצא תו אחר"))
    return reasons


def score_page(page: PageText, dropped: Iterable[tuple[int, int]] = (), *,
               min_plausible: float = MIN_PLAUSIBLE, max_effort: float = MAX_EFFORT) -> PageScore:
    """הציון של עמוד אחד. dropped: (אינדקס ב-PageText.lines, אינדקס ב-Line.parts) של מה שירד מה-Markdown ככותרת
    עליונה או תחתונה; כל השאר הוא מה שהמשתמש מקבל. הספים כפרמטרים בשביל הכיול בלבד."""
    rejected = _rejection(page)
    if rejected:
        return PageScore(REJECTED, tuple(rejected))
    plausibility = _plausibility(page, frozenset(dropped))
    completeness = _completeness(page)
    effort = _effort(page)
    reasons: list[Reason] = []
    notes: list[Note] = []
    if plausibility.display_failures:
        reasons.append(Reason("display", _many(plausibility.display_failures, "שורה אחת שלא מוצגת כמו העמוד",
                                               "שורות שלא מוצגות כמו העמוד")))
    if plausibility.bad_numbers:
        reasons.append(Reason("digit_groups", _many(plausibility.bad_numbers, "מספר אחד שקבוצות הספרות שלו לא תקינות",
                                                    "מספרים שקבוצות הספרות שלהם לא תקינות") +
                              ": כנראה שני מספרים שנדבקו"))
    if plausibility.crowded_cells:
        reasons.append(Reason("crowded_cells", _many(plausibility.crowded_cells, "תא אחד עם כמה מספרים",
                                                     "תאים עם כמה מספרים") +
                              " בעמודה של מספרים: כנראה שורות או עמודות של הטבלה שהתאחדו"))
    if not plausibility.signals.decides(min_plausible):
        notes.append(_short_note(plausibility.signals, min_plausible))
    elif plausibility.signals.score < min_plausible:
        reasons.extend(_signal_reasons(plausibility.signals))
    missing, extra = sum(completeness.missing.values()), sum(completeness.extra.values())
    if missing:
        emoji = " (אימוג'י)" if all(ord(char) > 0xFFFF for char in completeness.missing) else ""
        reasons.append(Reason("missing", _many(missing, "תו אחד שבעמוד חסר בפלט", "תווים שבעמוד חסרים בפלט") + emoji))
    if extra:
        reasons.append(Reason("extra", _many(extra, "תו אחד בפלט שאינו בעמוד", "תווים בפלט שאינם בעמוד")))
    if not effort.ok(max_effort):
        notes.append(Note("effort", f"הקורא תיקן הרבה: {effort.corrections} מתוך {effort.decisions} החלטות "
                                    f"({effort.spaces_changed} רווחים, "
                                    f"{effort.brackets_changed + effort.unknown_brackets} סוגריים), יותר מבכל עמוד "
                                    "שנבדק כנכון. מידע בלבד: אין עדיין ראיה שזה מנבא שגיאות"))
    return PageScore(UNSURE if reasons else OK, tuple(reasons), plausibility, completeness, effort, tuple(notes))


def score_document(pages: Sequence[PageText], dropped: Iterable[tuple[int, int, int]] = (), **thresholds) -> list[PageScore]:
    """הציון של כל עמוד במסמך, לפי הסדר. dropped: markdown.Markdown.dropped (עמוד מ-1, שורה, רכיב)."""
    by_page: dict[int, set[tuple[int, int]]] = {}
    for number, line, part in dropped:
        by_page.setdefault(number, set()).add((line, part))
    return [score_page(page, by_page.get(number, ()), **thresholds) for number, page in enumerate(pages, 1)]
