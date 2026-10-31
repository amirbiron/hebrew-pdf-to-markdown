"""קיבוץ אותיות לשורות, חלוקת כל שורה לרכיבים, ובניית הטקסט של כל רכיב."""

import statistics
from dataclasses import dataclass, field

import pypdfium2.raw as pdfium_raw
from pypdfium2 import PdfiumError

from hebrew_pdf.chars import Char, page_chars
from hebrew_pdf.layout import (MIN_PAGE_GAPS, PageLine, column_of, page_layout, page_line, split_components,
                               usual_word_gap)
from hebrew_pdf.logical_order import document_rtl, to_logical
from hebrew_pdf.spacing import SpaceCounts, space_by_gaps

BASELINE_TOLERANCE = 2.0  # נקודות PDF: אותיות שקו הבסיס שלהן קרוב עד כדי זה באותה שורה


@dataclass(frozen=True)
class Component:
    """רכיב בשורה: תא, תיבה או תג, שנקרא בנפרד משאר השורה (layout.py)."""
    text: str  # הסדר הלוגי של הרכיב
    visual: str  # התווים של הרכיב כמו שהם בעמוד, משמאל לימין, עם הרווחים לפי הפערים
    rtl: bool  # כיוון הפסקה שבה הרכיב נקרא (logical_order.to_logical)
    ambiguous: bool = False


@dataclass(frozen=True)
class Line:
    text: str  # הסדר הלוגי: הרכיבים לפי סדר הקריאה, עם רווח ביניהם
    # התווים כמו שהם מופיעים בעמוד, משמאל לימין, עם הרווחים לפי הפערים ולא תווי הרווח
    # שבקובץ (spacing.py). לבדיקת הסדר של התיוג
    visual: str
    # כיוון הפסקה של השורה: של המסמך, או מימין לשמאל כשיש בשורה עברית (logical_order.to_logical)
    rtl: bool
    # יותר מקריאה אחת מוצגת בדיוק כמו השורה בעמוד, וברירת המחדל הכריעה (logical_order.py)
    ambiguous: bool = False
    # כמה הרווחים לפי הפער שונים מתווי הרווח שבקובץ (spacing.py). build_line ממלא תמיד
    spacing: SpaceCounts = SpaceCounts()
    # הרכיבים לפי סדר הקריאה (layout.py). ריק: כל השורה היא רכיב אחד
    components: tuple[Component, ...] = ()
    # בשורה של טבלה: הטקסט של כל עמודה לפי סדר הקריאה, ו-"" לעמודה שאין בה טקסט בשורה
    columns: tuple[str, ...] | None = None

    @property
    def parts(self) -> tuple[Component, ...]:
        return self.components or (Component(self.text, self.visual, self.rtl, self.ambiguous),)

    @property
    def cells(self) -> tuple[str, ...]:
        """התאים של השורה, לפי סדר הקריאה: בטבלה, תא לכל עמודה; אחרת, תא לכל רכיב.

        מערך הבדיקה משווה לפיהם את השורה לתיוג.
        """
        if self.columns is not None:
            return self.columns
        return tuple(part.text for part in self.parts)


@dataclass(frozen=True)
class PageText:
    lines: list[Line]
    skipped_chars: int  # אותיות שדולגו כי אין להן מיקום (ראו chars.page_chars)
    unknown_brackets: int = 0  # סוגריים שהצורה שלהם לא נקבעה מהציור (bracket_shapes.py)
    # השורות של העמוד כתאים, לפי הסדר: שורה רגילה כמו שהיא (Line.cells), ושורה של טבלה
    # שנשברה לכמה שורות בעמוד כשורה אחת (table_rows). None: כל שורה כמו שהיא
    table_rows: list[tuple[str, ...]] | None = field(default=None)

    @property
    def ambiguous_lines(self) -> int:
        return sum(line.ambiguous for line in self.lines)

    @property
    def spacing(self) -> SpaceCounts:
        return sum((line.spacing for line in self.lines), SpaceCounts())

    @property
    def text(self) -> str:
        """השורות של העמוד, מופרדות ב-"\\n"."""
        return "\n".join(line.text for line in self.lines)

    @property
    def rows(self) -> list[tuple[str, ...]]:
        return self.table_rows if self.table_rows is not None else [line.cells for line in self.lines]


def group_rows(chars: list[Char]) -> list[list[Char]]:
    """קיבוץ אותיות לשורות לפי קו הבסיס, מלמעלה למטה (ב-PDF ציר y עולה כלפי מעלה)."""
    rows: list[list[Char]] = []
    for c in sorted(chars, key=lambda c: -c.baseline):
        if rows and abs(rows[-1][0].baseline - c.baseline) <= BASELINE_TOLERANCE:
            rows[-1].append(c)
        else:
            rows.append([c])
    return rows


def _component(chars: list[Char], rtl_document: bool) -> Component:
    reading = to_logical(chars, lambda c: c.text, rtl_document)
    return Component("".join(reading.texts), "".join(c.text for c in chars), reading.rtl, reading.ambiguous)


def build_line(row: list[Char], rtl_document: bool) -> Line:
    """שורה אחת בלי חלוקה לרכיבים: כל השורה נקראת כפסקה אחת (ראו logical_order.py).

    rtl_document: כיוון הפסקה של המסמך (logical_order.document_rtl).
    """
    spaced = space_by_gaps(sorted(row, key=lambda c: c.x))
    return _line(page_line(spaced.chars), set(), None, rtl_document, spaced.counts)[0]


@dataclass(frozen=True)
class _Piece:
    """הטקסט של תא בשורה אחת בעמוד, עם מה שצריך כדי לחבר אותו לשורה הבאה של אותו תא."""
    text: str
    width: float  # מהקצה השמאלי לימני של הטקסט בתא
    glyph: float  # רוחב אופייני של אות בתא (החציון)


def _line(line: PageLine, boundaries: set[int], columns, rtl_document: bool, counts: SpaceCounts):
    """השורה מהרכיבים שלה, ובטבלה גם החלק של כל תא בשורה (_Piece), לפי סדר הקריאה.

    הרכיבים בסדר הקריאה: מימין לשמאל במסמך עברי, אחרת משמאל לימין.
    columns: גבולות העמודות כשהשורה בטבלה (layout.PageLayout.columns), אחרת None.
    הרווחים בקצוות של כל רכיב יורדים: רווח נכנס רק בפער בין מילים, ופער של גבול הוא לא חלק מאף רכיב.
    """
    parts = split_components(line, boundaries)
    built = [_component(part, rtl_document) for part in parts]
    order = list(range(len(built)))
    if rtl_document:
        order.reverse()
    components = tuple(built[k] for k in order)
    cells = pieces = None
    if columns is not None:
        in_column: list[list[int]] = [[] for _ in range(len(columns) + 1)]
        for k in order:
            in_column[column_of(parts[k], columns)].append(k)
        if rtl_document:
            in_column.reverse()
        pieces = [_piece([built[k].text for k in ks], [c for k in ks for c in parts[k]]) for ks in in_column]
        cells = tuple(piece.text for piece in pieces)
    rtl = rtl_document or any(c.rtl for c in components)
    built_line = Line(" ".join(c.text for c in components), "".join(c.text for c in line.chars), rtl,
                      any(c.ambiguous for c in components), counts, components, cells)
    return built_line, pieces


def _piece(texts: list[str], chars: list[Char]) -> "_Piece":
    glyphs = [c for c in chars if c.text != " "]
    if not glyphs:
        return _Piece("", 0.0, 0.0)
    width = max(c.right for c in glyphs) - min(c.left for c in glyphs)
    return _Piece(" ".join(texts), width, statistics.median(c.right - c.left for c in glyphs))


def read_document(pdf) -> list[PageText]:
    """הטקסט של כל עמוד במסמך, לפי סדר העמודים.

    כיוון הפסקה נקבע פעם אחת, מכל השורות במסמך (logical_order.document_rtl), וגם הפער
    הרגיל בין מילים, כשבעמוד אין מספיק פערים משלו (layout.usual_word_gap). לכן קודם
    נקראות האותיות של כל העמודים ורק אחר כך נבנות השורות.
    """
    pdf_pages = list(pdf)
    pages = [page_chars(page) for page in pdf_pages]
    rows = [group_rows(found.chars) for found in pages]
    rtl = document_rtl([c.text for c in row] for page_rows in rows for row in page_rows)
    spaced_pages = [[space_by_gaps(sorted(row, key=lambda c: c.x)) for row in page_rows] for page_rows in rows]
    line_pages = [[page_line(s.chars) for s in spaced] for spaced in spaced_pages]
    document_gap = usual_word_gap([g.ratio for lines in line_pages for line in lines for g in line.gaps])
    out = []
    for pdf_page, found, spaced, lines in zip(pdf_pages, pages, spaced_pages, line_pages):
        ratios = [g.ratio for line in lines for g in line.gaps]
        word_gap = usual_word_gap(ratios) if len(ratios) >= MIN_PAGE_GAPS else document_gap
        layout = page_layout(lines, word_gap)
        built = [_line(line, layout.boundaries[i], layout.columns[i], rtl, s.counts)
                 for i, (line, s) in enumerate(zip(lines, spaced))]
        page_lines = [b[0] for b in built]
        out.append(PageText(page_lines, found.skipped, found.unknown_brackets,
                            table_rows(page_lines, [b[1] for b in built], layout.tables, lines, horizontal_rules(pdf_page))))
    return out


def horizontal_rules(page) -> list[tuple[float, float, float]]:
    """קווים אופקיים שמצוירים בעמוד (קווי מסגרת של טבלה): (שמאל, ימין, y).

    קו הוא אובייקט ציור (FPDF_PAGEOBJ_PATH) דק ורחב: גובה עד 2 נקודות, ורוחב פי 10 מהגובה
    לפחות. התיבה מ-PdfObject.get_bounds (pypdfium2/_helpers/pageobjects.py), שזורקת
    PdfiumError כשאין לאובייקט מיקום; אובייקט כזה לא יכול להיות קו, ולכן מדולג.
    """
    rules = []
    for obj in page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_PATH]):
        try:
            left, bottom, right, top = obj.get_bounds()
        except PdfiumError:
            continue  # אובייקט בלי מיקום על הדף: לא קו שאפשר להשתמש בו
        height = top - bottom
        if height <= 2.0 and right - left >= 10 * max(height, 0.1):
            rules.append((left, right, (top + bottom) / 2))
    return rules


def table_rows(lines: list[Line], pieces: list[list[_Piece] | None], table_of: list[int | None],
               geometry: list[PageLine], rules: list[tuple[float, float, float]]) -> list[tuple[str, ...]]:
    """השורות של העמוד כתאים, כששורה של טבלה שנשברה לכמה שורות בעמוד מתאחדת לשורה אחת.

    שורה בטבלה היא המשך של השורה שמעליה, כשיש לשתיהן אותן עמודות ולא מתחילה בה שורת טבלה
    חדשה (_new_rows). בכל עמודה, הטקסטים מתחברים ברווח, אלא אם השבירה הייתה בתוך מילה
    (_breaks_inside_a_word). שורה מחוץ לטבלה נשארת כמו שהיא (Line.cells).
    """
    new_row = _new_rows(pieces, table_of, geometry, rules)
    widths: dict[tuple[int, int, int], float] = {}  # (טבלה, מספר עמודות, עמודה) -> הרוחב הגדול ביותר
    for line_pieces, table in zip(pieces, table_of):
        if line_pieces is not None:
            for k, piece in enumerate(line_pieces):
                key = (table, len(line_pieces), k)
                widths[key] = max(widths.get(key, 0.0), piece.width)
    rows: list[tuple[str, ...]] = []
    current: list[list[_Piece]] | None = None
    current_table = None

    def flush():
        if current is not None:
            rows.append(tuple(_joined(column, widths[(current_table, len(current), k)])
                              for k, column in enumerate(current)))

    for i, (line, line_pieces, table) in enumerate(zip(lines, pieces, table_of)):
        if line_pieces is None:
            flush()
            current = None
            rows.append(line.cells)
            continue
        if current is not None and table == current_table and len(line_pieces) == len(current) and not new_row[i]:
            for column, piece in zip(current, line_pieces):
                if piece.text:
                    column.append(piece)
            continue
        flush()
        current = [[piece] if piece.text else [] for piece in line_pieces]
        current_table = table
    flush()
    return rows


def _new_rows(pieces, table_of, geometry: list[PageLine], rules) -> list[bool]:
    """לכל שורה בטבלה: האם מתחילה בה שורת טבלה חדשה.

    כשבטבלה יש קווים אופקיים בין השורות, קו בין שתי שורות בעמוד הוא הגבול בין שורות
    הטבלה: כך שם משתנה ארוך שנשבר לשתי שורות (MONGODB_SOCKET_TIMEOUT_M / S) נשאר בשורה
    אחת, אף שיש טקסט בעמודה הראשונה של שורת ההמשך. "יש קווים" נבדק מהטבלה עצמה: קו
    מפריד את רוב הזוגות שבהם יש טקסט בעמודה הראשונה של השורה השנייה. טבלה שיש בה קו רק
    מתחת לכותרת, או בלי קווים בכלל (הדוח הכספי), נשענת על העמודה הראשונה: שורה שאין בה
    טקסט בעמודה הראשונה (לפי סדר הקריאה) היא המשך.
    """
    def ruled(i: int) -> bool:
        above, below = geometry[i - 1], geometry[i]
        top, bottom = below.baseline + 0.6 * below.height, above.baseline - 0.2 * above.height
        return any(top < y < bottom and left < below.right and right > below.left for left, right, y in rules)

    new = [True] * len(pieces)
    by_table: dict[int, list[int]] = {}
    for i, table in enumerate(table_of):
        if table is not None and pieces[i] is not None:
            by_table.setdefault(table, []).append(i)
    for indices in by_table.values():
        pairs = [i for i in indices[1:] if i - 1 in indices and pieces[i][0].text]
        use_rules = bool(pairs) and 2 * sum(ruled(i) for i in pairs) > len(pairs)
        for i in indices[1:]:
            if i - 1 not in indices:
                continue
            new[i] = ruled(i) if use_rules else bool(pieces[i][0].text)
    return new


def _joined(column: list[_Piece], column_width: float) -> str:
    text = ""
    for i, piece in enumerate(column):
        if i == 0:
            text = piece.text
        else:
            text += ("" if _breaks_inside_a_word(column[i - 1], column_width) else " ") + piece.text
    return text


def _breaks_inside_a_word(before: _Piece, column_width: float) -> bool:
    """האם השבירה בסוף before, בתוך תא, לא הייתה ברווח (ואז לא נוסף רווח בחיבור).

    שבירת שורה בטקסט היא ברווח, חוץ משני מקרים שבהם היא בתוך מילה:
    - אחרי מקף או לוכסן שצמודים למילה שלפניהם (כמו "ל-" ו-"Bot/WebApp/"): שם מותר לשבור
      בלי רווח (UAX #14, https://www.unicode.org/reports/tr14/: אחרי HY ואחרי SY).
    - מילה שלא נכנסת בשורה לבדה נשברת באמצע (overflow-wrap: anywhere, כמו שם משתנה ארוך).
      אז החלק הראשון שלה ממלא את כל רוחב התא, עד כדי אות אחת, ואין בו רווח. רוחב התא הוא
      הרוחב הגדול ביותר של טקסט באותה עמודה בטבלה. בשבירה ברווח הטקסט מתמלא עד כדי מילה
      שלמה, ומילה אחת שממלאת בדיוק את הרוחב היא צירוף מקרים.
      הגבול הידוע: מילה אחת בשורה שהיא גם הטקסט הרחב ביותר בעמודה שלה נראית בדיוק כמו
      שבירה באמצע מילה, ומחוברת בלי רווח. בקובץ הטבלאות הכלל הזה מעלה את התאים הזהים
      מ-1,663 ל-2,561 (שמות משתנים ארוכים שנשברו), ולכן הוא נשאר.
    """
    if len(before.text) >= 2 and before.text[-1] in "-/" and before.text[-2] != " ":
        return True
    return " " not in before.text and before.width >= column_width - before.glyph
