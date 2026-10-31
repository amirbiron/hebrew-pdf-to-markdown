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
3. כותרות (headings): הכותרות שהמפרסר מוציא (h1 עד h6) מול הכותרות במקור (# בתחילת שורה),
   באותה רמה ובאותו סדר.

ועוד ספירה אחת, להחלטה הפתוחה על תו כיוון: כמה פסקאות, כותרות ופריטים במסמך עברי מתחילים
באות חזקה שאינה עברית (hebrew_pdf.markdown.first_strong), ותאים של טבלה בנפרד.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser

import cmarkgfm

from hebrew_pdf.lines import PageText
from hebrew_pdf.markdown import Markdown, first_strong

_SPACES = frozenset("\t\n\r\f\v")


def to_html(markdown: str) -> str:
    return cmarkgfm.github_flavored_markdown_to_html(markdown)


def visible_chars(text: str) -> Counter:
    """האותיות של טקסט בלי רווחים: קטגוריה Zs ב-Unicode, וטאב ושורה חדשה. לא str.isspace(), שמחשיב
    גם את U+001C עד U+001F, ובקבצים אלה אותיות שמופו בטעות (harness/textdiff.py)."""
    return Counter(char for char in text if char not in _SPACES and unicodedata.category(char) != "Zs")


class ParsedHtml(HTMLParser):
    """הטקסט, הטבלאות, הכותרות ומספר הפריטים ב-HTML של cmark-gfm. הערות לא נספרות כטקסט."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.tables: list[list[tuple[str, ...]]] = []
        self.headings: list[tuple[int, str]] = []
        self.items = 0
        self.blocks: list[tuple[str, str]] = []  # (תג, טקסט) של p, h1-h6, li: מה שמציג קובע לו כיוון
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._heading: tuple[int, list[str]] | None = None
        self._open: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
        elif re.fullmatch("h[1-6]", tag):
            self._heading = (int(tag[1]), [])
        if tag == "li":
            self.items += 1
        if tag in ("p", "li") or re.fullmatch("h[1-6]", tag):
            self._open.append((tag, []))

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(tuple(self._row))
            self._row = None
        elif re.fullmatch("h[1-6]", tag) and self._heading is not None:
            self.headings.append((self._heading[0], "".join(self._heading[1])))
            self._heading = None
        if self._open and self._open[-1][0] == tag:
            name, parts = self._open.pop()
            self.blocks.append((name, "".join(parts)))

    def handle_data(self, data):
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)
        if self._heading is not None:
            self._heading[1].append(data)
        if self._open:
            self._open[-1][1].append(data)


def parse(html: str) -> ParsedHtml:
    parser = ParsedHtml()
    parser.feed(html)
    parser.close()
    return parser


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


def source_headings(source: str) -> list[tuple[int, str]]:
    """הכותרות במקור Markdown: # בתחילת שורה, מחוץ לבלוק קוד."""
    out = []
    fenced = False
    for line in source.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            continue
        found = re.fullmatch(r"(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*", line)
        if found and not fenced:
            out.append((len(found.group(1)), _norm(found.group(2))))
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class HeadingMatch:
    source: int  # כותרות במקור
    output: int  # כותרות בפלט
    in_order: int  # כותרות של המקור שנמצאות בפלט באותו סדר, באותה רמה ובאותו טקסט
    in_order_any_level: int  # כנ"ל, בלי תנאי על הרמה
    missing: tuple[tuple[int, str], ...] = field(default=())  # של המקור, שלא נמצאו באותו סדר


def match_headings(source: list[tuple[int, str]], output: list[tuple[int, str]]) -> HeadingMatch:
    output = [(level, _norm(text)) for level, text in output]
    exact = _lcs(source, output, lambda a, b: a == b)
    any_level = _lcs(source, output, lambda a, b: a[1] == b[1])
    return HeadingMatch(len(source), len(output), len(exact), len(any_level),
                        tuple(h for k, h in enumerate(source) if k not in exact))


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
