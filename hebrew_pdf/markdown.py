"""בניית Markdown מהמבנה שהקורא כבר מוציא (lines.PageText), ולא מחדש מהטקסט.

הקלט: העמודים של מסמך, כל אחד עם השורות שלו (Line: הטקסט בסדר הלוגי, הרכיבים, והגיאומטריה),
והשורות כתאים (PageText.rows, עם RowSource: מאיזו שורה או טבלה כל אחת באה). הבונה לא משנה
את הסדר ולא את הריווח שהקורא הוציא: הוא רק מחליט איך לקבץ שורות ומה הסימון של כל קבוצה.

ההחלטות, וכולן יחסיות למסמך עצמו (בלי סף לתוכנה מסוימת):

1. כותרות עליונות ותחתונות של עמוד (_running_lines): שורה (או רכיב) שחוזרת כמעט זהה, באותו גובה
   בעמוד, ברוב העמודים, יורדת. "כמעט זהה": ספרות נחשבות זהות (מספר העמוד). רק מהקצוות: מלמעלה כל עוד
   השורות חוזרות, ומלמטה כך. שורה של טבלה לא נבדקת (הכותרת החוזרת של טבלה יורדת באיחוד, סעיף 6).

2. גוף הטקסט וכותרות (_size_levels): גודל האות (Char.size, em) של כל שורה. הגוף הוא הגודל
   שיש בו הכי הרבה אותיות, מחוץ לטבלאות. כותרת היא שורה בגודל גדול מהגוף פי HEADING_RATIO לפחות,
   והרמות לפי הגדלים השונים מהגדול לקטן (# לגדול). משקל הגופן לא בשימוש: FPDFText_GetFontWeight
   מחזיר 400 גם לגופן מודגש ב-WeasyPrint, 0 ב-Chrome ו-812 לטקסט רגיל ב-Canva (נמדד בסבב 5).

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

from hebrew_pdf.lines import Geometry, PageText, join_lines
from hebrew_pdf.logical_order import bidi_class

# שני גדלים של אות "שווים" כשהיחס ביניהם עד 1.02: הגודל מגיע מהקובץ (גודל הגופן כפול המטריצה),
# וגדלים של אותו סגנון שווים בו עד כדי עיגול. בדיקת רגישות (סבב 5, כל הסט): מ-1.005 עד 1.05 מספר
# הכותרות משתנה בעד 6 מתוך 276, והפסקאות בעד 3
SAME_SIZE = 1.02
# כותרת: גדולה מגוף הטקסט פי 1.1 לפחות. ב-CSS, h3 הוא פי 1.17 מהגוף; וריאציות של טקסט רגיל
# באותו מסמך קטנות מזה (בסט: עד פי 1.05, טקסט בתיבה או שורת פתיחה). כותרת בגודל הגוף (h4 בברירת
# המחדל של דפדפן) לא מזוהה בלי משקל גופן, ונשארת פסקה. בדיקת רגישות (סבב 5, כל הסט): אין טווח
# שבו התוצאה זהה, כי הגדלים בסט מפוזרים: 306 כותרות ב-1.03, 286 ב-1.06 עד 1.08, 276 ב-1.1, 249
# ב-1.15. ההתאמה לכותרות במקור של קובץ הטבלאות זהה בכל הטווח
HEADING_RATIO = 1.1
# מרווח "רגיל" בגוש: עד פי 1.15 מהמרווח של השורות שנשברו. בתוך פסקה המרווח זהה עד כדי עיגול,
# חוץ משורה שיש בה תו גבוה יותר (נמדד ב-Google Docs: עד פי 1.09); פסקה חדשה מוסיפה רווח
# (נמדד בדוח הכספי: פי 1.17 בגבול בין פסקאות). בדיקת רגישות (סבב 5, כל הסט): מ-1.02 עד 1.3 מספר
# הפסקאות משתנה בין 767 ל-753; ב-1.5 הוא יורד ל-650
SAME_STEP = 1.15
MAX_LEVEL = 6

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
    marker: str = ""  # item: הסימן כמו שהוא בשורה ("•", "3.", "א.")
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


@dataclass(frozen=True)
class _Unit:
    """שורה בעמוד (או רכיב שלה) כיחידה לבנייה."""
    text: str
    geometry: Geometry
    line: int  # האינדקס ב-PageText.lines
    alone: bool  # רכיב משורה עם כמה רכיבים: פסקה משלו, לא מתחבר לשורות סמוכות
    part: int = 0  # האינדקס של הרכיב ב-Line.parts

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
    levels, size_of = _size_levels(kept)
    rtl = pages[0].rtl_document if pages else True
    runs = [_runs(page_units, size_of) for page_units in kept]
    document_steps = _document_steps(runs)
    blocks: list[Block] = []
    repeated: list[tuple[str, ...]] = []
    for number, (page_units, page_runs) in enumerate(zip(kept, runs), 1):
        continues = _continues(page_runs, document_steps)
        _page_blocks(number, page_units, levels, size_of, rtl, continues, blocks, repeated)
    text, markers = _render(blocks, len(pages))
    return Markdown(text, tuple(blocks), tuple(sorted(dropped)), tuple(markers), tuple(repeated))


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
            out.append(_Unit(line.text, line.geometry, index, False))
    return out


def _signature(text: str) -> str:
    """הטקסט של שורה לזיהוי שורה חוזרת: כל רצף ספרות הוא אותו דבר, ורווחים לא נספרים."""
    return re.sub("[0-9]+", "0", re.sub(r"\s+", "", text))


def _same_place(a: _Unit, page_a: PageText, b: _Unit, page_b: PageText) -> bool:
    """אותו מקום בעמוד: קו בסיס באותו גובה (מלמטה, או מלמעלה כשגובה העמודים שונה) עד כדי גודל אות.
    בלי תנאי אופקי: בספר מספר העמוד מתחלף בין הצד הימני לשמאלי (נמדד בספר GPS: 8 עמודים בכל צד)."""
    ga, gb = a.geometry, b.geometry
    tolerance = max(ga.size, gb.size)
    from_bottom = abs(ga.baseline - gb.baseline)
    from_top = abs((page_a.height - ga.baseline) - (page_b.height - gb.baseline))
    return min(from_bottom, from_top) <= tolerance


def _running_lines(pages: Sequence[PageText], units: list[list]) -> set[tuple[int, int, int]]:
    """השורות שחוזרות כמעט זהות באותו מקום ברוב העמודים, מהקצה העליון והתחתון של כל עמוד."""
    count = len(pages)
    if count < 2:
        return set()
    needed = count // 2 + 1  # רוב העמודים
    texts = [[(u, _signature(u.text)) for u in page_units if isinstance(u, _Unit)] for page_units in units]

    def repeated(page: int, unit: _Unit, signature: str) -> bool:
        found = 1
        for other in range(count):
            if other != page and any(sig == signature and _same_place(unit, pages[page], u, pages[other])
                                     for u, sig in texts[other]):
                found += 1
        return found >= needed

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


def _size_levels(pages: list[list]) -> tuple[dict[float, int], dict]:
    """רמת הכותרת לכל גודל (0: גוף או קטן ממנו), והגודל המייצג של כל גודל (גדלים שווים עד SAME_SIZE)."""
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
        return {}, size_of
    body = max(representative, key=lambda item: (item[1], -item[0]))[0]
    larger = sorted((s for s, _ in representative if s >= body * HEADING_RATIO), reverse=True)
    return {size: min(i + 1, MAX_LEVEL) for i, size in enumerate(larger)}, size_of


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


def _page_blocks(number: int, units: list, levels: dict, size_of: dict, rtl: bool, continues: dict[int, bool],
                 blocks: list[Block], repeated: list[tuple[str, ...]]) -> None:
    text_units = [u for u in units if isinstance(u, _Unit) and not u.alone]
    # הקצה שממנו מתחילה הקריאה: ההזחה של פריט נמדדת ממנו
    start_edge = (max((u.geometry.right for u in text_units), default=0.0) if rtl
                  else min((u.geometry.left for u in text_units), default=0.0))
    drafts: list = []  # _Draft או _Table, לפי הסדר
    for i, unit in enumerate(units):
        if isinstance(unit, _Table):
            drafts.append(unit)
            continue
        marked = _marker(unit.text)
        # continues נכון רק כשהיחידה הקודמת היא שורה רגילה (לא טבלה ולא רכיב), ולכן drafts[-1] הוא שלה
        if marked is None and continues.get(i):
            drafts[-1].pieces.append(unit.text)
            continue
        geometry = unit.geometry
        if marked is not None:
            indent = start_edge - geometry.right if rtl else geometry.left - start_edge
            drafts.append(_Draft("item", 0, [marked[1]], marked[0], indent, geometry.glyph))
        else:
            level = levels.get(size_of.get(geometry.size, geometry.size), 0)
            drafts.append(_Draft("heading" if level else "paragraph", level, [unit.text]))
    _nest(drafts)
    for draft in drafts:
        if isinstance(draft, _Table):
            _add_table(number, draft, draft is drafts[0], blocks, repeated)
        else:
            text = join_lines(draft.pieces)
            blocks.append(Block(draft.kind, number, text, draft.level, draft.marker))


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


def _render(blocks: list[Block], pages: int) -> tuple[str, list[str]]:
    """הטקסט של ה-Markdown, והסימנים של פריטים שהפכו לתחביר של רשימה (Markdown.markers)."""
    out: list[str] = []
    markers: list[str] = []
    by_page: dict[int, list[Block]] = {}
    for block in blocks:
        by_page.setdefault(block.page, []).append(block)
    # עמודים שמתחילים בהמשך של טבלה: ההערה שלהם בתוך הטבלה (_table)
    inside_tables = {page for block in blocks for _, page in block.page_starts}
    for page in range(1, pages + 1):
        if page not in inside_tables:
            out.append(PAGE_MARKER.format(page))
        page_blocks = by_page.get(page, [])
        i = 0
        while i < len(page_blocks):
            block = page_blocks[i]
            if block.kind == "item":
                end = i
                while end < len(page_blocks) and page_blocks[end].kind == "item":
                    end += 1
                out.extend(_list(page_blocks[i:end], markers))
                i = end
                continue
            if block.kind == "table":
                out.append(_table(block))
            elif block.kind == "heading":
                out.append("#" * block.level + " " + escape_text(block.text).replace("#", "\\#"))
            else:
                out.append(_escape_block(block.text))
            i += 1
    return "\n\n".join(out) + "\n", markers


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
            else:
                markers.append(item.marker)
        lines.append(" " * sum(width for _, width, _ in stack) + mark + " " + content)
        stack.append((item.level, len(mark) + 1, following))
    return ["\n".join(lines) if k == 0 else "<!-- -->\n\n" + "\n".join(lines)
            for k, lines in enumerate(lists)]


def _table(block: Block) -> str:
    width = max(len(row) for row in block.rows)
    page_at = dict(block.page_starts)
    lines = []
    for k, row in enumerate(block.rows):
        cells = [escape_text(cell) for cell in row] + [""] * (width - len(row))
        if k in page_at:
            cells[0] = PAGE_MARKER.format(page_at[k]) + cells[0]  # בלי רווח: הוא היה נכנס לטקסט של התא
        lines.append("| " + " | ".join(cells) + " |")
        if k == 0:
            lines.append("|" + " --- |" * width)
    return "\n".join(lines)
