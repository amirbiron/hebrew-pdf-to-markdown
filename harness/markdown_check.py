"""בדיקות של ה-Markdown שהחבילה בונה (hebrew_pdf/markdown.py), דרך מפרסר GFM אמיתי.

המפרסר הוא cmark-gfm, הספרייה ש-GitHub עצמו מציג בה Markdown, דרך cmarkgfm (תלות פיתוח בלבד,
requirements-dev.txt, רישיון MIT). github_flavored_markdown_to_html מפעיל את ההרחבות table,
autolink, tagfilter, strikethrough ו-tasklist (cmarkgfm/cmark.py). בלי CMARK_OPT_UNSAFE, HTML גולמי
(כמו ההערות של גבולות העמודים) הופך להערה "raw HTML omitted", שאינה טקסט.

שלוש בדיקות:
1. שלמות (completeness): האותיות שהמפרסר מציג, בלי רווחים, הן בדיוק האותיות של הקורא בכל המסמך,
   חוץ ממה שירד ככותרת עליונה או תחתונה (Markdown.dropped), משורות כותרת חוזרות של טבלה שהתאחדה
   (Markdown.repeated_headers), ומהסימנים של פריטים שהפכו לרשימה
   (Markdown.markers: תבליט ומספר, שהמציג מצייר בעצמו). אות שנעלמה או נוספה היא באג. רצה על כל
   הקבצים, ולא רק על המתויגים, כמו בדיקת התצוגה. ומספר הפריטים ברשימות (li) שווה למספר הסימנים
   שהפכו לרשימה ועוד הפריטים שהסימן שלהם נשאר טקסט ("א."), כדי שהניכוי לא יסתיר טקסט.
2. טבלאות בסיבוב מלא (tables): התאים כמו שהמפרסר מוציא אותם מה-HTML, מול דף התשובות
   (harness/tables.py). כך נבדקים גם הבנייה וגם ההגנה על התווים.
3. מבנה (match_blocks): הכותרות, פריטי הרשימה והפסקאות שהמפרסר מוציא, מול אלה שבדף התשובות, שנגזרו
   מה-HTML שממנו נבנה ה-PDF (harness/html_structure.py, אותו פירוק בשני הצדדים): כמה זהים, באותו סדר,
   עם אותו טקסט ובאותה רמה (כותרת: h1 עד h6; פריט: עומק הקינון).

ועוד ספירה אחת, להחלטה הפתוחה על תו כיוון: כמה פסקאות, כותרות ופריטים במסמך עברי מתחילים
באות חזקה שאינה עברית (hebrew_pdf.markdown.first_strong), ותאים של טבלה בנפרד.
"""

import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

import cmarkgfm

from harness.html_structure import HtmlBlock, ParsedHtml, parse
from hebrew_pdf.lines import PageText
from hebrew_pdf.markdown import Markdown, first_strong

_SPACES = frozenset("\t\n\r\f\v")


def to_html(markdown: str) -> str:
    return cmarkgfm.github_flavored_markdown_to_html(markdown)


def visible_chars(text: str) -> Counter:
    """האותיות של טקסט בלי רווחים: קטגוריה Zs ב-Unicode, וטאב ושורה חדשה. לא str.isspace(), שמחשיב
    גם את U+001C עד U+001F, ובקבצים אלה אותיות שמופו בטעות (harness/textdiff.py)."""
    return Counter(char for char in text if char not in _SPACES and unicodedata.category(char) != "Zs")


@dataclass(frozen=True)
class Completeness:
    missing: Counter  # אותיות של הקורא שלא מוצגות
    extra: Counter  # אותיות מוצגות שאין אצל הקורא
    dropped_units: int  # שורות ורכיבים שירדו ככותרת עליונה או תחתונה
    repeated_headers: int  # שורות כותרת חוזרות של טבלה שירדו באיחוד
    list_markers: int  # סימנים של פריטים שהפכו לתחביר של רשימה
    items: int  # פריטים ברשימות ב-HTML
    expected_items: int  # הפריטים שהבונה יצר

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra and self.items == self.expected_items


def completeness(pages: Sequence[PageText], markdown: Markdown, parsed: ParsedHtml) -> Completeness:
    dropped = set(markdown.dropped)
    reader = Counter()
    for number, page in enumerate(pages, 1):
        for index, line in enumerate(page.lines):
            for part_index, part in enumerate(line.parts):
                if (number, index, part_index) not in dropped:
                    reader += visible_chars(part.text)
    for marker in markdown.markers:
        reader -= visible_chars(marker)
    for row in markdown.repeated_headers:
        reader -= visible_chars("".join(row))
    shown = visible_chars("".join(parsed.text))
    expected_items = sum(1 for block in markdown.blocks if block.kind == "item")
    return Completeness(reader - shown, shown - reader, len(dropped), len(markdown.repeated_headers),
                        len(markdown.markers), parsed.items, expected_items)


@dataclass(frozen=True)
class BlockMatch:
    """בלוקים מסוג אחד (כותרות, פריטים או פסקאות) בדף התשובות, מול הבלוקים מאותו סוג שהמפרסר מוציא."""
    kind: str
    source: int  # בדף התשובות
    output: int  # בפלט
    in_order: int  # של דף התשובות, שנמצאים בפלט באותו סדר, עם אותו טקסט ובאותה רמה
    in_order_any_level: int  # כנ"ל, בלי תנאי על הרמה (בפסקאות אין רמה, ושני המספרים שווים)
    missing: tuple[tuple[int, str], ...] = field(default=())  # (רמה, טקסט) של דף התשובות שלא נמצאו באותו סדר


def match_blocks(kind: str, truth: Sequence[HtmlBlock], output: Sequence[HtmlBlock]) -> BlockMatch:
    """הבלוקים מסוג kind באותו סדר: התת-סדרה המשותפת הארוכה ביותר, בלי לדלג על מה שלא תואם.

    הטקסט בשני הצדדים הוא מה שמוצג (html_structure.visible_text), ולכן השוואה מדויקת. "באותו סדר" ולא
    "קיים בפלט": בלוק שהגיע למקום אחר במסמך הוא בלוק שהקורא שיבץ לא נכון. הרמה: של כותרת (h1 עד h6)
    ושל פריט (עומק הקינון). ציטוט (quote) לא נבדק: הבונה לא מוציא ציטוטים, ופסקה בציטוט נמדדת כפסקה."""
    source = [(block.level, block.text) for block in truth if block.kind == kind]
    found = [(block.level, block.text) for block in output if block.kind == kind]
    exact = _lcs(source, found, lambda a, b: a == b)
    any_level = _lcs(source, found, lambda a, b: a[1] == b[1])
    return BlockMatch(kind, len(source), len(found), len(exact), len(any_level),
                      tuple(item for k, item in enumerate(source) if k not in exact))


def _lcs(a, b, same) -> set[int]:
    """האינדקסים ב-a של התת-סדרה המשותפת הארוכה ביותר עם b."""
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            table[i][j] = table[i + 1][j + 1] + 1 if same(a[i], b[j]) else max(table[i + 1][j], table[i][j + 1])
    out, i, j = set(), 0, 0
    while i < len(a) and j < len(b):
        if same(a[i], b[j]):
            out.add(i)
            i, j = i + 1, j + 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


@dataclass(frozen=True)
class Direction:
    """כמה בלוקים במסמך עברי מתחילים באות חזקה לטינית, כך שמציג שקובע כיוון לפי האות החזקה
    הראשונה יציג אותם משמאל לימין."""
    blocks: int  # פסקאות, כותרות ופריטים
    ltr_blocks: int
    cells: int  # תאים של טבלה שיש בהם אות חזקה
    ltr_cells: int


def direction(parsed: ParsedHtml) -> Direction:
    kinds = [first_strong(text) for _, text in parsed.blocks]
    cells = [first_strong(cell) for table in parsed.tables for row in table for cell in row]
    blocks = [k for k in kinds if k is not None]
    strong_cells = [k for k in cells if k is not None]
    return Direction(len(blocks), sum(k == "L" for k in blocks), len(strong_cells),
                     sum(k == "L" for k in strong_cells))
