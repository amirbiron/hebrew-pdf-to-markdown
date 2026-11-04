"""בניית Markdown מהמבנה שהקורא כבר מוציא (lines.PageText), ולא מחדש מהטקסט.

הקלט: העמודים של מסמך, כל אחד עם השורות שלו (Line: הטקסט בסדר הלוגי, הרכיבים, והגיאומטריה),
והשורות כתאים (PageText.rows, עם RowSource: מאיזו שורה או טבלה כל אחת באה). הבונה לא משנה
את הסדר ולא את הריווח שהקורא הוציא: הוא רק מחליט איך לקבץ שורות ומה הסימון של כל קבוצה.

ההחלטות, וכולן יחסיות למסמך עצמו (בלי סף לתוכנה מסוימת):

1. כותרות עליונות ותחתונות של עמוד (_running_lines): שורה (או רכיב) שחוזרת כמעט זהה, באותו גובה
   בעמוד, ברצף של לפחות MIN_RUN עמודים רצופים, או ברוב העמודים, יורדת. "כמעט זהה": ספרות נחשבות זהות
   (מספר העמוד). רק מהקצוות: מלמעלה כל עוד השורות חוזרות, ומלמטה כך. שורה של טבלה לא נבדקת (הכותרת
   החוזרת של טבלה יורדת באיחוד, סעיף 6).
   הרצף (מסבב 5ג): מסמך שבנוי מכמה חלקים חוזר על הכותרת שלו רק בעמודים של החלק. בדוח הכספי "רב בריח
   (08) תעשיות בע"מ" חוזר ב-27 מתוך 66 עמודים, ברצפים של 19 ושל 8, ולפי "רוב העמודים" לא ירדה שם אף
   שורה. עמוד בלי טקסט בכלל (תמונה, כמו הכריכה ועמוד 3 בספר GPS) לא קוטע רצף: אין בו ראיה לכאן או
   לכאן. "רוב העמודים" נשאר לצד הרצף, כי כותרת של כל המסמך נקטעת לפעמים בעמוד אחד: במצגת (Canva)
   השורה התחתונה מצוירת בשקופית 22 באמצע העמוד, ובשקופיות 23 ו-24 היא רצף של שתיים בלבד.
   כל העותקים יורדים, גם הראשון ברצף. במסמך שהכותרת העליונה שלו היא גם שם החלק, השם יורד איתה: בדוח
   הכספי שמות של שלושה דוחות (למשל "ביאורים לדוחות הכספיים המאוחדים") קיימים רק בכותרת העליונה.

2. גוף הטקסט וכותרות (_Sizes): גודל האות (Char.size, em) של כל שורה, והגופן שרוב האותיות שלה
   מצוירות בו (Char.font). הגוף הוא קבוצת הגודל (chars.SAME_SIZE) שיש בה הכי הרבה אותיות, מחוץ
   לטבלאות, וגופן הגוף הוא הגופן הנפוץ בה. כותרת היא שורה בקבוצת גודל גדולה מהגוף, שמצוירת בגופן אחר
   מגופן הגוף; הרמות לפי קבוצות הגודל מהגדולה לקטנה (# לגדולה).
   למה לא סף על היחס לגוף (עד סבב 5ב, פי 1.1): בסט יש הרבה טקסט רץ בגודל שקצת גדול מהגוף (פסקת
   פתיחה ב-MentorOS, פי 1.1; טקסט במצגת, פי 1.14), ומספר הכותרות השתנה בכל צעד של הסף (340 ב-1.02,
   216 ב-1.3). מה שמבדיל ביניהם הוא הגופן: כותרת מצוירת בגופן מודגש, שהוא גופן אחר בקובץ ("Heebo-Bold"
   מול "Heebo"), וטקסט רץ גדול בגופן של הגוף. לא נבדק שהשם מכיל "Bold": רק שהוא שונה משם גופן הגוף.
   כשהשם לא ידוע (ב-Chrome הוא ריק לכל האותיות), אין ראיה מהגופן, והכותרת לפי הגודל בלבד. משקל
   הגופן (FPDFText_GetFontWeight) לא בשימוש: הוא מחזיר 400 גם לגופן מודגש ב-WeasyPrint, 0 ב-Chrome
   ו-812 לטקסט רגיל ב-Canva (נמדד בסבב 5).
   ושורה שמתחילה במספור ("1.") בגודל ובגופן של כותרת, בלי שורה כזו לידה, היא כותרת ממוספרת ולא
   פריט ברשימה (_numbered_heading).

3. פסקאות (_runs, _continues): שורות רצופות באותו גודל, שחופפות אופקית, הן "גוש". המרווח הרגיל
   בין השורות של גוש הוא המרווח הקטן ביותר בו בין שורה שנשברה בגלל רוחב לשורה שאחריה (_wrapped).
   פסקה חדשה מתחילה כשהמרווח גדול ממנו פי SAME_STEP, כשהגודל משתנה, או בתחילת פריט ברשימה.
   בגוש שאין בו אף שורה שנשברה בגלל רוחב המסגרת (למשל שורות בתא של טבלה שהקורא לא זיהה), המרווח
   הרגיל הוא של אותו גודל במסמך כולו (_document_steps); ובלי זה, השורות נפרדות.
   למה לא המרווח הנפוץ במסמך: באותו מסמך ובאותו גודל יש גושים עם מרווחים שונים (בדוח הכספי
   0.99 ו-1.48 מגודל האות), ובמסמך של פסקאות בנות שורה אחת הנפוץ הוא דווקא המרווח בין פסקאות.
   החיבור בין שורות של פסקה הוא אותו כלל שמחבר שורות בתא (lines.join_lines): ברווח, חוץ מאחרי
   מקף או לוכסן שצמודים למילה.

4. רשימות (_marker): תבליט (תו מהגושים Geometric Shapes או תבליט מ-General Punctuation, או -, *,
   +, –) או מספור ("1.", "1)", "א.", "א)") בתחילת השורה הלוגית, ואחריו רווח וטקסט. רמת הקינון לפי
   ההזחה מהקצה שממנו מתחילה הקריאה (במסמך עברי: מימין).
   ותבליט מצויר (מסבב 5ג): צורה ולא תו, לפני השורה (Line.drawn_marker, lines.drawn_marker). ב-Chrome כך
   מצויר התבליט של רשימה. אין לו תו בטקסט, ולכן הסימן של הפריט ריק, והוא לא נספר ב-Markdown.markers.

5. רכיבים שאינם טבלה (שורה עם כמה רכיבים, layout.py): כל רכיב כפסקה משלו, לפי סדר הקריאה.

6. טבלאות: שורות של אותה טבלה (RowSource.table) הן טבלת GFM, והשורה הראשונה היא שורת הכותרת.
   טבלה שהעמוד הקודם הסתיים בה, והעמוד הזה מתחיל בה עם אותה שורת כותרת, מתאחדת איתה, והכותרת
   החוזרת יורדת.

7. גבולות עמודים: לפני התוכן של כל עמוד, הערת HTML "<!-- page N -->". כשהעמוד מתחיל בהמשך של
   טבלה, ההערה נמצאת בתא הראשון של השורה הראשונה מהעמוד הזה (הערה בתוך תא היא HTML בתוך השורה,
   ו-GFM מתיר אותה), כי שורה בין שורות של טבלה הייתה סוגרת אותה.

8. הגנה על תווי Markdown (escape_text, _escape_block): טקסט מוצג כטקסט ולא כעיצוב.

הפלט בלי תווי כיוון: פסקה במסמך עברי שמתחילה באות לטינית תוצג במציג שקובע כיוון לפי האות
החזקה הראשונה משמאל לימין. זו החלטה פתוחה (מסמך האפיון), והמונה שלה ב-first_strong.
"""

import re
import statistics
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from hebrew_pdf.chars import SAME_SIZE
from hebrew_pdf.lines import Geometry, PageText, join_lines
from hebrew_pdf.logical_order import bidi_class

# מרווח "רגיל" בגוש: עד פי 1.15 מהמרווח של השורות שנשברו. בתוך פסקה המרווח זהה עד כדי עיגול,
# חוץ משורה שיש בה תו גבוה יותר (נמדד ב-Google Docs: עד פי 1.09); פסקה חדשה מוסיפה רווח
# (נמדד בדוח הכספי: פי 1.17 בגבול בין פסקאות). בדיקת רגישות (סבב 5, כל הסט): מ-1.02 עד 1.3 מספר
# הפסקאות משתנה בין 767 ל-753; ב-1.5 הוא יורד ל-650
SAME_STEP = 1.15
MAX_LEVEL = 6
# כותרת עליונה או תחתונה: באותו מקום בלפחות כמה עמודים רצופים (סעיף 1 בראש הקובץ). בדיקת רגישות (סבב
# 5ג, כל הסט; שורות שירדו, לפי MIN_RUN):
#                 2    3    4    5-6  7    8    10-12  14   20 ומעלה (רוב העמודים בלבד)
#   דוח כספי      97   83   68   64,59 59  52   44     19   0
#   מצגת          40   36   30   22   22   22   22     22   22
#   MentorOS      10   10   7    7    7    7    7      7    7
#   ספר GPS       35   20   20   20   20   20   20     20   20
# ובשאר הקבצים אותו מספר בכל ערך (קובץ הטבלאות 26, הצעת המחיר 7, מסמך האפיון 9 בכל תוכנה, והשאר 0).
# התוצאה רגישה לערך בכל הטווח, וזה דגל: אורך הרצף לא מפריד בין כותרת עליונה לתוכן. בדוח הכספי יש רצפים
# בכל אורך מ-2 עד 19, כי כל דוח בו חוזר על השם שלו בכל העמודים שלו. מה שכן נמדד: ב-2 יורד גם תוכן,
# הערת שוליים שחוזרת בעמודים 6 ו-7 של הדוח הכספי, ומילים של תמונה שנפרשת על שני עמודים בספר GPS (6-7,
# 10-11). מ-3 כל מה שנוסף הוא שורה שחוזרת בראש או בתחתית של כל עמודי החלק: מספר עמוד, השם של החלק או
# של הדוח, "(המשך)", ובמצגת השם של החלק בראש כל שקופית שלו (השם עצמו נשאר בשקופית הפותחת). 3 הוא הערך
# הקטן ביותר שבו לא ירד תוכן כזה, ולא ערך יציב
#
# מה הרצף מוריד בדוח הכספי, שורה שורה (סבב 6, PR א׳: מול אותה בנייה עם "רוב העמודים" בלבד): 83 שורות, 8 טקסטים,
# כולם בקצה העמוד. מספר העמוד ("- 1 -", 27 עמודים) ושם החברה (27); שמות של דוחות ושל חלקים שמופיעים רק בכותרת
# העליונה (3, 13 ו-4 עמודים); שתי כותרות "(המשך)", "ביאור 5 - מגזרי פעילות (המשך):" ו-"ב. מידע לגבי רווח או
# הפסד (המשך):" (עמודים 47 עד 49); ומשפט התחתית "הביאורים המצורפים מהווים חלק בלתי נפרד..." (עמודים 33 עד 35,
# והוא יורד מכל העותקים, כמו כל שורה חוזרת). מספר הפריטים ירד מ-72 ל-42, ואף פריט עם תוכן לא ירד, גם לא
# ב-MIN_RUN=2: 27 ממספרי העמוד נקראו עד אז כפריטים (מקף ואחריו "1 -"), ומכאן 27 הסימנים (51 ל-24), ושלוש כותרות
# "(המשך)" היו פריטים ("ב."). השורה שאחרי כל כותרת כזו נשארת בפלט. ובעמוד 50 הפריט "ג. הרכב הכנסות לפי
# מוצרים (המשך):" כבר לא מתחבר לכותרת המשנה שמתחתיו, כמו בעמוד: עד אז השורות של הכותרת העליונה היו באותו גוש
# (_runs), ושתיים מהן נחשבו שורה שנשברה בגלל רוחב, וכך המרווח בין שתי כותרות נחשב המרווח הרגיל של פסקה.
# מה נשאר: 4 מספרי עמוד שהם עדיין פריטים (עמודים 38, 39, 55 ו-56). ב-Aspose מספר העמוד מצויר מיד אחרי סוף
# התוכן, ולכן הגובה שלו משתנה מעמוד לעמוד (26 עד 140 נקודות מתחתית העמוד), והוא לא "באותו מקום" (_same_place)
MIN_RUN = 3

PAGE_MARKER = "<!-- page {} -->"

# תווים שמשנים את התצוגה בתוך שורה: עיצוב (* _ ~), קוד (`), HTML (<), קישור ([ ]), ישות (&), טבלה (|),
# והלוכסן ההפוך עצמו. לוכסן הפוך לפניהם הופך אותם לתו רגיל (GFM, "Backslash escapes":
# https://github.github.com/gfm/#backslash-escapes). harness/labels.py קורא בדיוק את זה בחזרה (split_row)
_INLINE_ESCAPES = frozenset("\\|*_`~<[]&")
# תחילת שורה שפותחת מבנה (GFM, "Leaf blocks" ו-"Container blocks"): כותרת (#), ציטוט (>), רשימה
# (- + ומספר עם . או ")"), וקו מפריד (-). * ו-_ כבר מוגנים בתוך השורה
_BLOCK_START = re.compile(r"[#>+\-=]|[0-9]{1,9}(?=[.)])")

_BULLETS = frozenset("-*+–")
_NUMBERED = re.compile(r"([0-9]{1,3}|[א-ת])([.)])$")


# כתובת שתהפוך לקישור אוטומטי (GFM, "Autolinks (extension)": http://, https://, ftp:// ו-www.). ב-cmark-gfm
# הקישור נמצא בטקסט המקור, לפני ביטול ה-escapes, ולכן לוכסן הפוך בתוכו נשאר גלוי ("a\\_b" מוצג
# "a\\_b"; נבדק ב-cmarkgfm 2025.10.22). לוכסן לפני ה-":" של "://" ולפני הנקודה של "www." מונע את
# הקישור, והטקסט מוצג זהה. כתובת מייל לא צריכה את זה: היא מזוהה אחרי ביטול ה-escapes
_AUTOLINK_START = re.compile(r"(:)(?=//)|(?i:(?<=www)(\.))")


def escape_text(text: str) -> str:
    """טקסט שמוצג בדיוק כמו שהוא בתוך שורה של Markdown (או בתא של טבלה): לוכסן הפוך לפני
    התווים ב-_INLINE_ESCAPES, ולפני מה שהיה הופך כתובת לקישור אוטומטי (_AUTOLINK_START). הכתובת
    מוצגת כטקסט ולא כקישור: בתוך קישור אוטומטי GFM לא מבטל escapes, ואז ההגנה על שאר התווים לא
    הייתה אפשרית. גם הדוח של מערך הבדיקה וטבלת התיוג משתמשים בזה."""
    escaped = "".join("\\" + char if char in _INLINE_ESCAPES else char for char in text)
    return _AUTOLINK_START.sub(lambda m: "\\" + m.group(0), escaped)


def _escape_block(text: str) -> str:
    """טקסט של פסקה, כותרת או פריט: בתוך השורה (escape_text), ובתחילתה גם תו שהיה פותח מבנה.
    במספר ("3.") הלוכסן לפני הנקודה, כי רק היא הופכת את המספר לרשימה."""
    escaped = escape_text(text)
    found = _BLOCK_START.match(escaped)
    if not found:
        return escaped
    if found.group(0)[0].isdigit():
        end = found.end()
        return escaped[:end] + "\\" + escaped[end:]
    return "\\" + escaped


def first_strong(text: str) -> str | None:
    """הסוג (L, R או AL) של התו החזק הראשון בטקסט, כמו שמציג קובע כיוון של פסקה (UAX #9, P2).
    None כשאין תו חזק."""
    for char in text:
        kind = bidi_class(char)
        if kind in ("L", "R", "AL"):
            return kind
    return None


@dataclass(frozen=True)
class Block:
    kind: str  # "heading", "paragraph", "item", "table"
    page: int  # העמוד שבו הבלוק מתחיל, מ-1
    text: str = ""  # heading, paragraph, item: הטקסט הלוגי, בלי סימון ובלי הסימן של הפריט
    level: int = 0  # heading: 1 עד 6. item: עומק הקינון, מ-0
    marker: str = ""  # item: הסימן כמו שהוא בשורה ("•", "3.", "א."). "": תבליט מצויר, בלי תו (סעיף 4)
    rows: tuple[tuple[str, ...], ...] = ()  # table: השורות, והראשונה היא שורת הכותרת
    # table: השורות שבהן מתחיל עמוד חדש בתוך הטבלה: (אינדקס ב-rows, מספר העמוד)
    page_starts: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class Markdown:
    text: str
    blocks: tuple[Block, ...]
    # מה שירד ככותרת עליונה או תחתונה: (עמוד מ-1, אינדקס ב-PageText.lines, אינדקס ב-Line.parts)
    dropped: tuple[tuple[int, int, int], ...] = ()
    # סימני הפריטים שהפכו לתחביר של רשימה ולא מופיעים כטקסט (תבליטים ומספרים; "א." נשאר טקסט)
    markers: tuple[str, ...] = field(default=())
    # שורות כותרת חוזרות של טבלה שירדו כשהטבלה התאחדה עם הטבלה מהעמוד הקודם (סעיף 6)
    repeated_headers: tuple[tuple[str, ...], ...] = field(default=())
    # לכל עמוד, לפי הסדר: המקום (אינדקס תו ב-text) שבו מתחיל סמן העמוד שלו, PAGE_MARKER (סעיף 7). נרשם בזמן
    # הבנייה ולא מחופש בטקסט אחר כך: טקסט מהקובץ שכתוב בו "<!-- page 2 -->" יוצא אחרי ההגנה "\<!-- page 2 -->",
    # וחיפוש של המחרוזת היה מוצא אותו. לפי הקוד (_add_table, _render) הסדר בטקסט יכול להיות שונה מסדר העמודים:
    # עמוד שמתחיל בהמשך של טבלה מעמוד קודם מקבל את הסמן בתוך הטבלה, וכשביניהם עמוד בלי טקסט, הסמן של העמוד הריק
    # בא אחריו. בסט זה לא קורה (נבדק בדף, בכל 15 הקבצים), ולכן הדף ממיין לפי השורה ולא מניח את הסדר
    page_offsets: tuple[int, ...] = field(default=())


@dataclass(frozen=True)
class _Unit:
    """שורה בעמוד (או רכיב שלה) כיחידה לבנייה."""
    text: str
    geometry: Geometry
    line: int  # האינדקס ב-PageText.lines
    alone: bool  # רכיב משורה עם כמה רכיבים: פסקה משלו, לא מתחבר לשורות סמוכות
    part: int = 0  # האינדקס של הרכיב ב-Line.parts
    drawn_marker: bool = False  # Line.drawn_marker: לפני השורה מצויר תבליט (סעיף 4)

    @property
    def key(self) -> tuple[int, int]:
        return self.line, self.part


@dataclass(frozen=True)
class _Table:
    rows: tuple[tuple[str, ...], ...]
    table: int  # RowSource.table


def build_markdown(pages: Sequence[PageText]) -> Markdown:
    """ה-Markdown של מסמך שלם (כל העמודים, לפי הסדר)."""
    units = [_page_units(page) for page in pages]
    dropped = _running_lines(pages, units)
    kept = [[u for u in page_units if not (isinstance(u, _Unit) and (number, *u.key) in dropped)]
            for number, page_units in enumerate(units, 1)]
    sizes = _Sizes.of(kept)
    rtl = pages[0].rtl_document if pages else True
    runs = [_runs(page_units, sizes.size_of) for page_units in kept]
    document_steps = _document_steps(runs)
    blocks: list[Block] = []
    repeated: list[tuple[str, ...]] = []
    for number, (page_units, page_runs) in enumerate(zip(kept, runs), 1):
        continues = _continues(page_runs, document_steps)
        _page_blocks(number, page_units, sizes, rtl, continues, blocks, repeated)
    text, markers, offsets = _render(blocks, len(pages))
    return Markdown(text, tuple(blocks), tuple(sorted(dropped)), tuple(markers), tuple(repeated), offsets)


def _page_units(page: PageText) -> list:
    """היחידות של עמוד לפי הסדר: _Table לכל טבלה, ו-_Unit לכל שורה או רכיב מחוץ לטבלה."""
    out: list = []
    for cells, source in zip(page.rows, page.sources):
        if source.table is not None:
            if out and isinstance(out[-1], _Table) and out[-1].table == source.table:
                out[-1] = _Table(out[-1].rows + (cells,), source.table)
            else:
                out.append(_Table((cells,), source.table))
            continue
        index = source.lines[0]
        line = page.lines[index]
        if len(line.parts) > 1:
            out.extend(_Unit(part.text, part.geometry, index, True, k) for k, part in enumerate(line.parts) if part.text)
        elif line.text:
            out.append(_Unit(line.text, line.geometry, index, False, drawn_marker=line.drawn_marker))
    return out


def _signature(text: str) -> str:
    """הטקסט של שורה לזיהוי שורה חוזרת: כל רצף ספרות הוא אותו דבר, ורווחים לא נספרים."""
    return re.sub("[0-9]+", "0", re.sub(r"\s+", "", text))


def _same_place(a: _Unit, page_a: PageText, b: _Unit, page_b: PageText) -> bool:
    """אותו מקום בעמוד: קו בסיס באותו גובה (מלמטה, או מלמעלה כשגובה העמודים שונה) עד כדי גודל אות.
    בלי תנאי אופקי: בספר מספר העמוד מתחלף בין הצד הימני לשמאלי (נמדד בספר GPS: 8 עמודים בכל צד).
    גודל האות הקטנה מהשתיים (גודל לא ידוע, 0, לא מצמצם): עד סבב 5ג הגדולה, ואז שם של חלק במצגת (Canva),
    בגודל 30 בשקופית הפותחת של החלק, נחשב באותו מקום כמו הכותרת העליונה של השקופיות שאחריה, בגודל 14
    ו-30 נקודות מעליו, וירד איתה. עם "רוב העמודים" בלבד זה לא קרה (בסט התוצאה זהה בשתי הגרסאות)."""
    ga, gb = a.geometry, b.geometry
    tolerance = min((size for size in (ga.size, gb.size) if size > 0), default=0.0)
    from_bottom = abs(ga.baseline - gb.baseline)
    from_top = abs((page_a.height - ga.baseline) - (page_b.height - gb.baseline))
    return min(from_bottom, from_top) <= tolerance


def _running_lines(pages: Sequence[PageText], units: list[list]) -> set[tuple[int, int, int]]:
    """השורות שחוזרות כמעט זהות באותו מקום, ברצף של לפחות MIN_RUN עמודים או ברוב העמודים, מהקצה העליון
    והתחתון של כל עמוד (סעיף 1 בראש הקובץ)."""
    count = len(pages)
    if count < 2:
        return set()
    needed = count // 2 + 1  # רוב העמודים
    texts = [[(u, _signature(u.text)) for u in page_units if isinstance(u, _Unit)] for page_units in units]
    # עמוד בלי טקסט בכלל לא קוטע רצף
    empty = [not any(line.text.strip() for line in page.lines) for page in pages]

    def repeated(page: int, unit: _Unit, signature: str) -> bool:
        here = [other == page or any(sig == signature and _same_place(unit, pages[page], u, pages[other])
                                     for u, sig in texts[other]) for other in range(count)]
        if sum(here) >= needed:
            return True
        run = 1
        for step in (1, -1):
            other = page + step
            while 0 <= other < count and (here[other] or empty[other]):
                run += here[other]
                other += step
        return run >= MIN_RUN

    dropped: set[tuple[int, int, int]] = set()
    for page, page_units in enumerate(units):
        for ordered in (page_units, page_units[::-1]):
            for unit in ordered:
                if not isinstance(unit, _Unit) or not repeated(page, unit, _signature(unit.text)):
                    break
                dropped.add((page + 1, *unit.key))
    return dropped


def _visible_length(text: str) -> int:
    """מספר האותיות בלי רווחים (Zs, טאב). לא str.isspace(): הוא מחשיב גם את U+001C עד U+001F,
    ובקבצים אלה אותיות שמופו בטעות (harness/textdiff.py)."""
    return sum(1 for char in text if char != "\t" and unicodedata.category(char) != "Zs")


@dataclass(frozen=True)
class _Sizes:
    """קבוצות הגודל של המסמך (סעיף 2 בראש הקובץ): הגודל המייצג של כל גודל (גדלים שווים עד SAME_SIZE),
    רמת הכותרת של כל קבוצה שגדולה מהגוף, וגופן הגוף."""
    size_of: dict
    levels: dict
    body_font: str

    @staticmethod
    def of(pages: list[list]) -> "_Sizes":
        weight: Counter = Counter()
        for page_units in pages:
            for unit in page_units:
                if isinstance(unit, _Unit) and unit.geometry.size > 0:
                    weight[unit.geometry.size] += _visible_length(unit.text)
        clusters: list[list[float]] = []
        for size in sorted(weight):
            if clusters and size <= clusters[-1][0] * SAME_SIZE:
                clusters[-1].append(size)
            else:
                clusters.append([size])
        size_of = {}
        representative = []
        for cluster in clusters:
            main = max(cluster, key=lambda s: (weight[s], s))
            representative.append((main, sum(weight[s] for s in cluster)))
            for size in cluster:
                size_of[size] = main
        if not representative:
            return _Sizes(size_of, {}, "")
        body = max(representative, key=lambda item: (item[1], -item[0]))[0]
        fonts: Counter = Counter()
        for page_units in pages:
            for unit in page_units:
                if isinstance(unit, _Unit) and size_of.get(unit.geometry.size) == body:
                    fonts[unit.geometry.font] += _visible_length(unit.text)
        body_font = max(fonts, key=lambda f: (fonts[f], f)) if fonts else ""
        larger = sorted((s for s, _ in representative if s > body), reverse=True)
        return _Sizes(size_of, {size: min(i + 1, MAX_LEVEL) for i, size in enumerate(larger)}, body_font)

    def level(self, geometry: Geometry) -> int:
        """רמת הכותרת של שורה (0: לא כותרת): קבוצת גודל גדולה מהגוף, בגופן אחר מגופן הגוף. כשאחד
        מהשמות לא ידוע ("") אין ראיה מהגופן, והגודל מכריע לבד."""
        level = self.levels.get(self.size_of.get(geometry.size, geometry.size), 0)
        if level and geometry.font and self.body_font and geometry.font == self.body_font:
            return 0
        return level


def _marker(text: str) -> tuple[str, str] | None:
    """(הסימן, הטקסט שאחריו) כשהשורה מתחילה בסימן של פריט ברשימה, אחרת None."""
    head, space, rest = text.partition(" ")
    if not space or not rest.strip(" "):
        return None
    if len(head) == 1 and (head in _BULLETS or _is_bullet(head)):
        return head, rest
    if _NUMBERED.fullmatch(head):
        return head, rest
    return None


def _is_bullet(char: str) -> bool:
    """תו של תבליט: מהגוש Geometric Shapes (U+25A0–U+25FF: ● ○ ◆ ◂ ▪ ◦), או תבליט מ-General
    Punctuation (• U+2022, ‣ U+2023, ⁃ U+2043), או BULLET OPERATOR (∙ U+2219)."""
    code = ord(char)
    return 0x25A0 <= code <= 0x25FF or char in "•‣⁃∙"


def _overlap(a: Geometry, b: Geometry) -> bool:
    return min(a.right, b.right) > max(a.left, b.left)


def _wrapped(before: _Unit, after: _Unit, frame: float) -> bool:
    """האם before נשברה בגלל רוחב: המקום שנשאר בה עד רוחב המסגרת קטן מהמילה הראשונה של after
    ועוד רווח. כך שוברים שורה (המילה הבאה לא נכנסה); שורה אחרונה של פסקה משאירה יותר מקום."""
    word = after.text.split(" ")[0]
    return frame - before.geometry.width < (len(word) + 1) * after.geometry.glyph


@dataclass
class _Draft:
    """בלוק בבנייה: היחידות שלו, ובפריט גם הסימן וההזחה."""
    kind: str
    level: int
    pieces: list[str]  # הטקסט של כל שורה בעמוד שבבלוק
    marker: str = ""
    indent: float = 0.0
    glyph: float = 0.0


def _frame(units: list) -> float:
    """רוחב המסגרת של הטקסט בעמוד: השורה הרחבה ביותר מחוץ לטבלאות ולרכיבים."""
    return max((u.geometry.width for u in units if isinstance(u, _Unit) and not u.alone), default=0.0)


def _page_blocks(number: int, units: list, sizes: "_Sizes", rtl: bool, continues: dict[int, bool],
                 blocks: list[Block], repeated: list[tuple[str, ...]]) -> None:
    text_units = [u for u in units if isinstance(u, _Unit) and not u.alone]
    # הקצה שממנו מתחילה הקריאה: ההזחה של פריט נמדדת ממנו
    start_edge = (max((u.geometry.right for u in text_units), default=0.0) if rtl
                  else min((u.geometry.left for u in text_units), default=0.0))
    drafts: list = []  # _Draft או _Table, לפי הסדר
    numbered_heading = [_numbered_heading(unit, sizes) for unit in units]
    for i, unit in enumerate(units):
        if isinstance(unit, _Table):
            drafts.append(unit)
            continue
        marked = _marker(unit.text)
        if marked is not None and numbered_heading[i] and not (
                (i > 0 and numbered_heading[i - 1] == numbered_heading[i])
                or (i + 1 < len(units) and numbered_heading[i + 1] == numbered_heading[i])):
            marked = None  # מספור בגודל של כותרת, בלי שורה ממוספרת באותו גודל לידו: כותרת ממוספרת
        if marked is None and unit.drawn_marker:
            marked = ("", unit.text)  # תבליט מצויר: כל הטקסט הוא התוכן של הפריט
        # continues נכון רק כשהיחידה הקודמת היא שורה רגילה (לא טבלה ולא רכיב), ולכן drafts[-1] הוא שלה
        if marked is None and continues.get(i):
            drafts[-1].pieces.append(unit.text)
            continue
        geometry = unit.geometry
        if marked is not None:
            indent = start_edge - geometry.right if rtl else geometry.left - start_edge
            drafts.append(_Draft("item", 0, [marked[1]], marked[0], indent, geometry.glyph))
        else:
            level = sizes.level(geometry)
            drafts.append(_Draft("heading" if level else "paragraph", level, [unit.text]))
    _nest(drafts)
    for draft in drafts:
        if isinstance(draft, _Table):
            _add_table(number, draft, draft is drafts[0], blocks, repeated)
        else:
            text = join_lines(draft.pieces)
            blocks.append(Block(draft.kind, number, text, draft.level, draft.marker))


def _numbered_heading(unit, sizes: "_Sizes") -> int | None:
    """רמת הכותרת של שורה שמתחילה במספור ("1.", "3)") ושהיא בגודל ובגופן של כותרת (_Sizes.level);
    אחרת None. שתי שורות סמוכות עם אותה רמה הן רשימה ממוספרת, לא כותרות (_page_blocks)."""
    if not isinstance(unit, _Unit) or unit.alone:
        return None
    marked = _marker(unit.text)
    if marked is None or not _NUMBERED.fullmatch(marked[0]):
        return None
    return sizes.level(unit.geometry) or None


def _nest(drafts: list) -> None:
    """רמת הקינון של כל פריט, בכל רשימה (פריטים רצופים): ההזחות השונות ברשימה, מהקטנה לגדולה.
    שתי הזחות שונות כשההפרש ביניהן גדול מרוחב אות."""
    i = 0
    while i < len(drafts):
        if not (isinstance(drafts[i], _Draft) and drafts[i].kind == "item"):
            i += 1
            continue
        end = i
        while end < len(drafts) and isinstance(drafts[end], _Draft) and drafts[end].kind == "item":
            end += 1
        items = drafts[i:end]
        glyph = statistics.median(item.glyph for item in items) or 0.0
        indents: list[float] = []
        for indent in sorted(item.indent for item in items):
            if not indents or indent - indents[-1] > glyph:
                indents.append(indent)
        for item in items:
            item.level = max(k for k, value in enumerate(indents) if item.indent - value >= -glyph)
        i = end


@dataclass(frozen=True)
class _Run:
    """גוש: יחידות רצופות באותו גודל שחופפות אופקית. לכל זוג: האינדקס של השנייה, המרווח כחלק
    מגודל האות, והאם הראשונה נשברה בגלל רוחב (_wrapped)."""
    size: float
    pairs: tuple[tuple[int, float, bool], ...]


def _runs(units: list, size_of: dict) -> list[_Run]:
    frame = _frame(units)
    linked: list[tuple[int, float, float, bool]] = []  # (אינדקס, גודל, מרווח, נשברה)
    for i in range(1, len(units)):
        a, b = units[i - 1], units[i]
        if not (isinstance(a, _Unit) and isinstance(b, _Unit)) or a.alone or b.alone:
            continue
        size_a = size_of.get(a.geometry.size, a.geometry.size)
        size_b = size_of.get(b.geometry.size, b.geometry.size)
        if not size_a or size_a != size_b or not _overlap(a.geometry, b.geometry):
            continue
        step = (a.geometry.baseline - b.geometry.baseline) / size_a
        if step > 0:
            linked.append((i, size_a, step, _wrapped(a, b, frame)))
    runs: list[_Run] = []
    for i, size, step, wrapped in linked:
        if runs and runs[-1].pairs[-1][0] == i - 1:
            runs[-1] = _Run(size, runs[-1].pairs + ((i, step, wrapped),))
        else:
            runs.append(_Run(size, ((i, step, wrapped),)))
    return runs


def _document_steps(pages: list[list[_Run]]) -> dict[float, float]:
    """המרווח של שורות בתוך פסקה במסמך, לכל גודל: הנפוץ מבין המרווחים אחרי שורה שנשברה בגלל רוחב
    (בעיגול ל-0.01 מגודל האות). משמש גוש שאין בו עדות משלו (שורות בתא של טבלה שהקורא לא זיהה)."""
    by_size: dict[float, Counter] = {}
    for runs in pages:
        for run in runs:
            for _, step, wrapped in run.pairs:
                if wrapped:
                    by_size.setdefault(run.size, Counter())[round(step, 2)] += 1
    return {size: max(steps, key=lambda s: (steps[s], -s)) for size, steps in by_size.items()}


def _continues(runs: list[_Run], document_steps: dict[float, float]) -> dict[int, bool]:
    """לכל יחידה: האם היא ממשיכה את הפסקה של היחידה שלפניה (סעיף 3 בראש הקובץ). המרווח הרגיל של
    גוש: הקטן ביותר אחרי שורה שנשברה בגלל רוחב בגוש עצמו, ואם אין כזו, של אותו גודל במסמך."""
    out: dict[int, bool] = {}
    for run in runs:
        wrapped = [step for _, step, was_wrapped in run.pairs if was_wrapped]
        usual = min(wrapped) if wrapped else document_steps.get(run.size)
        if usual is None:
            continue
        for i, step, _ in run.pairs:
            out[i] = step <= usual * SAME_STEP
    return out


def _add_table(page: int, table: _Table, first_on_page: bool, blocks: list[Block],
               repeated: list[tuple[str, ...]]) -> None:
    previous = blocks[-1] if blocks else None
    if (first_on_page and previous is not None and previous.kind == "table" and previous.page < page
            and _same_row(previous.rows[0], table.rows[0])):
        repeated.append(table.rows[0])
        rows = previous.rows + table.rows[1:]
        starts = previous.page_starts + ((len(previous.rows), page),) if len(table.rows) > 1 else previous.page_starts
        blocks[-1] = Block("table", previous.page, rows=rows, page_starts=starts)
        return
    blocks.append(Block("table", page, rows=table.rows))


def _same_row(a: Sequence[str], b: Sequence[str]) -> bool:
    def norm(row):
        return tuple(re.sub(r"\s+", " ", cell).strip() for cell in row)
    return norm(a) == norm(b)


_BLOCK_SEPARATOR = "\n\n"


def _render(blocks: list[Block], pages: int) -> tuple[str, list[str], tuple[int, ...]]:
    """הטקסט של ה-Markdown, הסימנים של פריטים שהפכו לתחביר של רשימה (Markdown.markers), והמקום של הסמן של כל
    עמוד בטקסט (Markdown.page_offsets)."""
    out: list[str] = []
    markers: list[str] = []
    offsets: dict[int, int] = {}
    position = 0  # המקום בטקסט שבו יתחיל הקטע הבא

    def add(piece: str, page_markers: dict[int, int] | None = None) -> None:
        """קטע אחד של הטקסט (בלוק, רשימה או סמן), ו-page_markers: לכל עמוד שהסמן שלו בתוך הקטע, המקום שלו בקטע."""
        nonlocal position
        for number, at in (page_markers or {}).items():
            offsets[number] = position + at
        out.append(piece)
        position += len(piece) + len(_BLOCK_SEPARATOR)

    by_page: dict[int, list[Block]] = {}
    for block in blocks:
        by_page.setdefault(block.page, []).append(block)
    # עמודים שמתחילים בהמשך של טבלה: ההערה שלהם בתוך הטבלה (_table)
    inside_tables = {page for block in blocks for _, page in block.page_starts}
    for page in range(1, pages + 1):
        if page not in inside_tables:
            add(PAGE_MARKER.format(page), {page: 0})
        page_blocks = by_page.get(page, [])
        i = 0
        while i < len(page_blocks):
            block = page_blocks[i]
            if block.kind == "item":
                end = i
                while end < len(page_blocks) and page_blocks[end].kind == "item":
                    end += 1
                for piece in _list(page_blocks[i:end], markers):
                    add(piece)
                i = end
                continue
            if block.kind == "table":
                add(*_table(block))
            elif block.kind == "heading":
                add("#" * block.level + " " + escape_text(block.text).replace("#", "\\#"))
            else:
                add(_escape_block(block.text))
            i += 1
    if len(offsets) != pages:
        raise ValueError(f"לא לכל עמוד יש סמן: {len(offsets)} סמנים ל-{pages} עמודים")
    return _BLOCK_SEPARATOR.join(out) + "\n", markers, tuple(offsets[page] for page in range(1, pages + 1))


def _list(items: list[Block], markers: list[str]) -> list[str]:
    """פריטים רצופים כרשימות של Markdown. תבליט הופך ל-"-", ומספר נשאר מספר; "א." נשאר טקסט
    בפריט עם תבליט, כי ב-Markdown אין רשימה ממוספרת באותיות.

    הקינון: פריט שההזחה שלו (Block.level) גדולה משל הפריט הפתוח האחרון הוא בתוכו, ופריט באותה
    הזחה הוא אחיו. השורה של פריט פנימי מוזחת ברוחב הסימן של כל פריט שהוא בתוכו (GFM, "List items").
    שני כללים של GFM שמשנים את התוצאה אם לא מטפלים בהם (https://github.github.com/gfm/#lists):
    - רשימה ממוספרת שמתחילה במספר שאינו 1 לא יכולה לקטוע פסקה, ולכן לפני רשימה פנימית כזו
      נכנסת שורה ריקה (היא לא קוטעת את הטקסט של הפריט שמעליה, והרשימה החיצונית נהיית "רחבה").
    - ברשימה ממוספרת המציג מספר את הפריטים ברצף ממספר הפתיחה. פריט שהמספר שלו לא ממשיך את
      הקודם פותח רשימה חדשה, אחרי הערת HTML ריקה שסוגרת את הקודמת."""
    lists: list[list[str]] = [[]]
    stack: list[tuple[int, int, int | None]] = []  # לכל פריט פתוח: (הזחה, רוחב הסימן ועוד רווח, המספר הבא)
    for item in items:
        sibling = None  # הפריט הקודם באותה רמה, אם יש
        while stack and stack[-1][0] >= item.level:
            sibling = stack.pop()
        numbered = _NUMBERED.fullmatch(item.marker)
        content = _escape_block(item.text)
        lines = lists[-1]
        if numbered and numbered.group(1).isdigit():
            value = int(numbered.group(1))
            expected = sibling[2] if sibling is not None else None
            if not stack and expected is not None and value != expected:
                lists.append([])
                lines = lists[-1]
            elif stack and expected is None and value != 1:
                lines.append("")
            mark = numbered.group(1) + numbered.group(2)
            following = value + 1
            markers.append(item.marker)
        else:
            mark = "-"
            following = None
            if numbered:  # אות עברית: נשארת בטקסט
                content = escape_text(item.marker) + " " + content
            elif item.marker:  # תבליט מצויר (סימן ריק) אינו תו בטקסט, ואין מה לנכות
                markers.append(item.marker)
        lines.append(" " * sum(width for _, width, _ in stack) + mark + " " + content)
        stack.append((item.level, len(mark) + 1, following))
    return ["\n".join(lines) if k == 0 else "<!-- -->\n\n" + "\n".join(lines)
            for k, lines in enumerate(lists)]


def _table(block: Block) -> tuple[str, dict[int, int]]:
    """הטבלה כטקסט, ולכל עמוד שמתחיל בתוכה (Block.page_starts) המקום של הסמן שלו בטקסט הזה."""
    width = max(len(row) for row in block.rows)
    page_at = dict(block.page_starts)
    lines = []
    markers: dict[int, int] = {}
    position = 0  # המקום בטקסט של הטבלה שבו מתחילה השורה הבאה
    for k, row in enumerate(block.rows):
        cells = [escape_text(cell) for cell in row] + [""] * (width - len(row))
        if k in page_at:
            cells[0] = PAGE_MARKER.format(page_at[k]) + cells[0]  # בלי רווח: הוא היה נכנס לטקסט של התא
            markers[page_at[k]] = position + len("| ")
        lines.append("| " + " | ".join(cells) + " |")
        if k == 0:
            lines.append("|" + " --- |" * width)
        position += sum(len(line) + 1 for line in lines[-2 if k == 0 else -1:])
    return "\n".join(lines), markers
