"""המבנה של עמוד HTML לפי הסדר: כותרות, פסקאות, פריטי רשימה, ציטוטים, קוד וטבלאות.

אותו פירוק משמש את שני הצדדים של מדידת המבנה: tools/build_table_pdf.py גוזר ממנו את דף התשובות,
מה-HTML שממנו נבנה ה-PDF, ו-harness/markdown_check.py קורא בו את ה-HTML ש-cmark-gfm מוציא מה-Markdown
שהחבילה בנתה. כך יש הגדרה אחת ל"הטקסט של פריט" או "הטקסט של תא", ולא שני עותקים שיכולים להיפרד.

הבלוקים (HtmlBlock), לפי הסדר שבו הם מתחילים ב-HTML:
- heading: h1 עד h6, והרמה היא המספר.
- paragraph: p שאינו בתוך פריט או תא.
- item: li. הרמה היא עומק הקינון (0: פריט ברשימה שאינה בתוך פריט). הטקסט הוא של הפריט עצמו, כולל
  פסקאות שבתוכו, ובלי פריטים של רשימה פנימית: לכל אחד מהם בלוק משלו, אחרי הפריט שהוא בתוכו.
- code: pre.
- table: table, עם הטקסט של כל תא, שורה אחרי שורה (thead ו-tbody יחד, לפי הסדר).
quote: בכמה blockquote הבלוק נמצא (0: לא בציטוט).

הטקסט של בלוק הוא מה שמוצג (visible_text): בלי תווי עיצוב בלתי נראים (הקטגוריה Cf ב-Unicode, כמו
RLM: הם לא מצוירים), ועם רווח אחד במקום כל רצף של רווחים. בבלוק קוד השורות נשמרות.
הערות HTML (כמו גבולות העמודים, hebrew_pdf/markdown.py), ותוכן של style, script ו-title, אינם טקסט.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser

HEADING_TAGS = frozenset(f"h{level}" for level in range(1, 7))
# תגיות שהתוכן שלהן אינו טקסט מוצג
_HIDDEN = frozenset({"head", "script", "style", "template", "title"})
# תגיות בתוך שורה: לא מתחילות ולא מסיימות בלוק
_INLINE = frozenset({"a", "b", "code", "del", "em", "i", "img", "kbd", "s", "span", "strong", "sub", "sup"})
KINDS = frozenset({"heading", "paragraph", "item", "code", "table"})


def visible_text(text: str) -> str:
    """הטקסט כמו שהוא מוצג: בלי תווי Cf, ועם רווח אחד במקום כל רצף של רווחים."""
    return re.sub(r"\s+", " ", "".join(ch for ch in text if unicodedata.category(ch) != "Cf")).strip()


@dataclass(frozen=True)
class HtmlBlock:
    kind: str  # אחד מ-KINDS
    text: str = ""  # heading, paragraph, item, code. בטבלה: ריק
    level: int = 0  # heading: 1 עד 6. item: עומק הקינון, מ-0
    quote: int = 0  # בכמה blockquote הבלוק נמצא
    rows: tuple[tuple[str, ...], ...] = ()  # table: הטקסט של כל תא, והשורה הראשונה היא שורת הכותרת


def block_to_json(block: HtmlBlock) -> dict:
    """הבלוק כמו שהוא נשמר בדף התשובות: רק השדות שיש להם משמעות לסוג שלו (harness/tables.load_blocks קורא)."""
    out: dict = {"kind": block.kind}
    if block.kind in ("heading", "item"):
        out["level"] = block.level
    if block.kind == "table":
        out["rows"] = [list(row) for row in block.rows]
    else:
        out["text"] = block.text
    if block.quote:
        out["quote"] = block.quote
    return out


@dataclass
class _Open:
    """בלוק בבנייה: הטקסט שלו מצטבר עד תגית הסגירה."""
    kind: str
    level: int
    quote: int
    parts: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


class ParsedHtml(HTMLParser):
    """הטקסט, הטבלאות, הכותרות, מספר הפריטים והמבנה (structure) ב-HTML. הערות לא נספרות כטקסט.

    text, tables, headings ו-blocks הם הטקסט כמו שהמפרסר מוציא אותו, בלי נרמול; structure הוא
    המבנה המלא, בטקסט שמוצג (visible_text)."""

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
        # המבנה: הבלוקים לפי הסדר שבו התחילו, והפתוחים מביניהם (פנימי אחרון)
        self._entries: list[_Open] = []
        self._stack: list[tuple[str, _Open]] = []  # (התג שסוגר, הבלוק)
        self._quote = 0
        self._items_open = 0
        self._table: _Open | None = None
        self._cell_parts: list[str] | None = None
        self._hidden = 0  # בתוך style, script וכו' (_HIDDEN)
        self._stray: _Open | None = None  # פסקה של טקסט מחוץ לכל בלוק (handle_data), עד התגית הבאה שאינה בתוך שורה

    @property
    def structure(self) -> list[HtmlBlock]:
        out = []
        for entry in self._entries:
            if entry.kind == "table":
                out.append(HtmlBlock("table", quote=entry.quote, rows=tuple(tuple(row) for row in entry.rows)))
            elif entry.kind == "code":
                out.append(HtmlBlock("code", "\n".join(visible_text(line) for line in "".join(entry.parts).strip("\n").split("\n")),
                                     quote=entry.quote))
            else:
                out.append(HtmlBlock(entry.kind, visible_text("".join(entry.parts)), entry.level, entry.quote))
        return out

    def _start(self, tag: str, kind: str, level: int = 0) -> None:
        entry = _Open(kind, level, self._quote)
        self._entries.append(entry)
        self._stack.append((tag, entry))

    def _inside(self, kind: str) -> bool:
        return any(entry.kind == kind for _, entry in self._stack)

    def handle_starttag(self, tag, attrs):
        if tag in _HIDDEN:
            self._hidden += 1
            return
        if self._hidden:
            return  # תגית בתוך מה שלא מוצג (template וכו'): לא טקסט ולא בלוק
        if tag not in _INLINE:
            self._stray = None
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag in HEADING_TAGS:
            self._heading = (int(tag[1]), [])
        if tag == "li":
            self.items += 1
        if tag in ("p", "li") or tag in HEADING_TAGS:
            self._open.append((tag, []))
        # המבנה
        if tag == "blockquote":
            self._quote += 1
        elif tag == "table":
            self._start(tag, "table")
            self._table = self._stack[-1][1]
        elif tag == "tr" and self._table is not None:
            self._table.rows.append([])
        elif tag in ("td", "th") and self._table is not None:
            self._cell_parts = []
        elif self._cell_parts is not None:
            if tag == "br":
                self._cell_parts.append(" ")
            return  # מבנה בתוך תא הוא חלק מהתא
        elif tag == "br" and self._stack:
            self._stack[-1][1].parts.append(" ")  # שבירת שורה מוצגת כרווח בין המילים
        elif tag in HEADING_TAGS:
            self._start(tag, "heading", int(tag[1]))
        elif tag == "li":
            self._start(tag, "item", self._items_open)
            self._items_open += 1
        elif tag == "pre":
            self._start(tag, "code")
        elif tag == "p" and self._inside("item"):
            self._stack[-1][1].parts.append(" ")  # פסקה בתוך פריט: חלק מהטקסט שלו, ברווח מהקודמת
        elif tag == "p":
            self._start(tag, "paragraph")

    def handle_endtag(self, tag):
        if tag in _HIDDEN:
            self._hidden = max(0, self._hidden - 1)
            return
        if self._hidden:
            return
        if tag not in _INLINE:
            self._stray = None
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.tables[-1].append(tuple(self._row))
            self._row = None
        elif tag in HEADING_TAGS and self._heading is not None:
            self.headings.append((self._heading[0], "".join(self._heading[1])))
            self._heading = None
        if self._open and self._open[-1][0] == tag:
            name, parts = self._open.pop()
            self.blocks.append((name, "".join(parts)))
        # המבנה
        if tag == "blockquote":
            self._quote = max(0, self._quote - 1)
        elif tag in ("td", "th") and self._cell_parts is not None and self._table is not None and self._table.rows:
            self._table.rows[-1].append(visible_text("".join(self._cell_parts)))
            self._cell_parts = None
        elif self._stack and self._stack[-1][0] == tag:
            _, entry = self._stack.pop()
            if entry.kind == "item":
                self._items_open -= 1
            elif entry.kind == "table":
                self._table = None

    def handle_data(self, data):
        if self._hidden:
            return
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)
        if self._heading is not None:
            self._heading[1].append(data)
        if self._open:
            self._open[-1][1].append(data)
        # המבנה: לבלוק הפתוח הפנימי ביותר (פסקה בתוך פריט היא חלק מהפריט)
        if self._cell_parts is not None:
            self._cell_parts.append(data)
        elif self._stack and self._stack[-1][1].kind != "table":
            self._stack[-1][1].parts.append(data)
        elif self._stray is not None:
            self._stray.parts.append(data)
        elif data.strip():
            # טקסט מחוץ לכל בלוק (HTML גולמי במקור): פסקה משלו, כדי שלא ייעלם מהמבנה
            self._stray = _Open("paragraph", 0, self._quote, [data])
            self._entries.append(self._stray)


def parse(html: str) -> ParsedHtml:
    parser = ParsedHtml()
    parser.feed(html)
    parser.close()
    return parser
