"""קיבוץ אותיות לשורות, חלוקת כל שורה לרכיבים, ובניית הטקסט של כל רכיב."""

import ctypes
import statistics
from collections import Counter
from dataclasses import dataclass, field

import pypdfium2.raw as pdfium_raw
from pypdfium2 import PdfiumError

from hebrew_pdf.chars import Char, page_chars, size_of
from hebrew_pdf.layout import (MIN_PAGE_GAPS, PageLine, column_of, page_layout, page_line, rule_between,
                               split_components, usual_word_gap)
from hebrew_pdf.logical_order import document_rtl, to_logical
from hebrew_pdf.spacing import SpaceCounts, space_by_gaps

BASELINE_TOLERANCE = 2.0  # נקודות PDF: אותיות שקו הבסיס שלהן קרוב עד כדי זה באותה שורה
# תבליט מצויר (drawn_marker): הצד הארוך של הצורה לפחות MIN_MARK מגודל האות של השורה, והמרחק שלה מהטקסט עד
# MAX_MARK_GAP מגודל האות. בדיקת רגישות (סבב 5ג, כל הסט; שורות עם תבליט מצויר): לכל MIN_MARK בין 0.1 ל-0.22
# ולכל MAX_MARK_GAP בין 1.5 ל-2.5 התוצאה זהה: 50 במסמך האפיון מ-Chrome, 67 במצגת, 13 במסמך ההגדרות של
# Social Publisher, 4 בפלאייר, ו-0 בשאר. ב-0.06 נוסף מפגש של קווי מסגרת בדוח הכספי (ריבוע של 0.05 מגודל
# האות), ומ-0.24 נעלמים התבליטים של המצגת (0.23). ב-1.25 נעלמים 2 תבליטים במצגת שרחוקים 1.35 מהטקסט, ומ-3
# נוסף קו אנכי בהצעת המחיר, 2.83 מהטקסט. שני הערכים באמצע הטווח
MIN_MARK = 0.15
MAX_MARK_GAP = 2.0


@dataclass(frozen=True)
class Geometry:
    """איפה טקסט נמצא בעמוד ובאיזה גודל: מה שבונה ה-Markdown צריך (markdown.py), ולא משפיע על הטקסט.

    0 בכל השדות: לא ידוע (למשל Line שנבנה בטסט בלי אותיות).
    """
    baseline: float = 0.0  # קו הבסיס (y, ב-PDF ציר y עולה כלפי מעלה)
    left: float = 0.0  # הקצה השמאלי של האות השמאלית
    right: float = 0.0  # הקצה הימני של האות הימנית
    size: float = 0.0  # גודל האות (chars.size_of)
    glyph: float = 0.0  # רוחב אופייני של אות: החציון של רוחב ההתקדמות (Char.right - Char.left)
    font: str = ""  # הגופן של רוב האותיות (Char.font); "": לא ידוע

    @property
    def width(self) -> float:
        return self.right - self.left


def geometry_of(chars: list[Char]) -> Geometry:
    """הגיאומטריה של אותיות (בלי הרווחים שהקורא הכניס בפערים, spacing.py)."""
    glyphs = [c for c in chars if c.text != " "]
    if not glyphs:
        return Geometry()
    fonts = Counter(c.font for c in glyphs)
    return Geometry(glyphs[0].baseline, min(c.left for c in glyphs), max(c.right for c in glyphs),
                    size_of(glyphs), statistics.median(c.right - c.left for c in glyphs),
                    max(fonts, key=lambda f: (fonts[f], f)))


@dataclass(frozen=True)
class Component:
    """רכיב בשורה: תא, תיבה או תג, שנקרא בנפרד משאר השורה (layout.py)."""
    text: str  # הסדר הלוגי של הרכיב
    visual: str  # התווים של הרכיב כמו שהם בעמוד, משמאל לימין, עם הרווחים לפי הפערים
    rtl: bool  # כיוון הפסקה שבה הרכיב נקרא (logical_order.to_logical)
    ambiguous: bool = False
    geometry: Geometry = Geometry()
    # סוגריים שהתו שלהם בפלט שונה מהתו שבקובץ (Char.source): הצורה המצוירת הכריעה נגד הקובץ. לציון (score.py)
    brackets_changed: int = 0


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
    geometry: Geometry = Geometry()
    # לפני השורה מצויר תבליט: צורה ולא תו בטקסט, ולכן הוא לא חלק מ-text (drawn_marker). רק בשורה של רכיב
    # אחד מחוץ לטבלה
    drawn_marker: bool = False
    # החלטות של הקורא בשורה שקרובות לסף שלהן: פערים שההחלטה עליהם מתהפכת בתוך הטווח היציב של הקבוע
    # (spacing.SpacedRow.near: רווח או לא; layout.PageLayout.near: גבול בין רכיבים או לא). מידע לכיול, סבב 6ב
    near_spaces: int = 0
    near_boundaries: int = 0

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
class RowSource:
    """מאיפה באה שורה של PageText.rows: השורות בעמוד (אינדקסים ב-PageText.lines) והטבלה שלה."""
    lines: tuple[int, ...]
    # הטבלה בעמוד (layout.PageLayout.tables: האינדקס של השורה הראשונה שלה), או None מחוץ לטבלה
    table: int | None


@dataclass(frozen=True)
class PageText:
    lines: list[Line]
    skipped_chars: int  # אותיות שדולגו כי אין להן מיקום (ראו chars.page_chars)
    unknown_brackets: int = 0  # סוגריים שהצורה שלהם לא נקבעה מהציור (bracket_shapes.py)
    # השורות של העמוד כתאים, לפי הסדר: שורה רגילה כמו שהיא (Line.cells), ושורה של טבלה
    # שנשברה לכמה שורות בעמוד כשורה אחת (table_rows). None: כל שורה כמו שהיא
    table_rows: list[tuple[str, ...]] | None = field(default=None)
    # לכל שורה ב-rows: מאיפה היא באה (RowSource). None: שורה לכל Line, מחוץ לטבלה
    row_sources: list[RowSource] | None = field(default=None)
    # כיוון הפסקה של המסמך (logical_order.document_rtl), אותו כיוון לכל העמודים
    rtl_document: bool = True
    # הרוחב והגובה של העמוד, בנקודות PDF (PdfPage.get_size). 0: לא ידוע
    width: float = 0.0
    height: float = 0.0
    # מכאן: מידע לציון של העמוד (score.py), מ-chars.PageChars. לא משנה את הטקסט
    brackets: int = 0  # סוגריים שנקראו (chars.PageChars.brackets)
    marked_unmapped: int = 0  # תווים ש-PDFium מסמן כלא ממופים ונראים כתווים רגילים (chars.page_reference)
    rotated_chars: int = 0  # תווים בשורה שאינה אופקית משמאל לימין (chars.is_rotated)
    # כל התווים של העמוד לפי הרשימה של PDFium (chars.page_reference): מולם נמדדת השלמות. None: לא ידוע
    reference: str | None = None

    @property
    def near_decisions(self) -> int:
        """החלטות קרובות לסף בכל העמוד (Line.near_spaces, Line.near_boundaries)."""
        return sum(line.near_spaces + line.near_boundaries for line in self.lines)

    @property
    def brackets_changed(self) -> int:
        """סוגריים שהציור הכריע בהם נגד התו שבקובץ (Component.brackets_changed), בכל העמוד."""
        return sum(part.brackets_changed for line in self.lines for part in line.parts)

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

    @property
    def sources(self) -> list[RowSource]:
        """RowSource לכל שורה ב-rows."""
        if self.row_sources is not None:
            return self.row_sources
        return [RowSource((i,), None) for i in range(len(self.lines))]


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
    # reading.texts הוא הטקסט הלוגי של כל אות (סוגר אחרי השיקוף של L4), באותו סדר כמו reading.logical
    changed = sum(1 for char, text in zip(reading.logical, reading.texts) if char.source and text != char.source)
    return Component("".join(reading.texts), "".join(c.text for c in chars), reading.rtl, reading.ambiguous,
                     geometry_of(chars), changed)


def build_line(row: list[Char], rtl_document: bool) -> Line:
    """שורה אחת בלי חלוקה לרכיבים: כל השורה נקראת כפסקה אחת (ראו logical_order.py).

    rtl_document: כיוון הפסקה של המסמך (logical_order.document_rtl).
    """
    spaced = space_by_gaps(sorted(row, key=lambda c: c.x))
    return _line(page_line(spaced.chars), set(), None, rtl_document, spaced.counts, near=(spaced.near, 0))


def _line(line: PageLine, boundaries: set[int], columns, rtl_document: bool, counts: SpaceCounts,
          marks: list[tuple[float, float, float, float]] = (), near: tuple[int, int] = (0, 0)) -> Line:
    """השורה מהרכיבים שלה, ובטבלה גם הטקסט של כל תא בשורה (Line.columns), לפי סדר הקריאה.

    הרכיבים בסדר הקריאה: מימין לשמאל במסמך עברי, אחרת משמאל לימין.
    columns: גבולות העמודות כשהשורה בטבלה (layout.PageLayout.columns), אחרת None.
    הרווחים בקצוות של כל רכיב יורדים: רווח נכנס רק בפער בין מילים, ופער של גבול הוא לא חלק מאף רכיב.
    marks: הצורות שמצוירות בעמוד (page_marks), לתבליט מצויר (drawn_marker).
    near: ההחלטות הקרובות לסף בשורה (רווחים, גבולות), לכיול בלבד (Line.near_spaces, Line.near_boundaries).
    """
    parts = split_components(line, boundaries)
    built = [_component(part, rtl_document) for part in parts]
    order = list(range(len(built)))
    if rtl_document:
        order.reverse()
    components = tuple(built[k] for k in order)
    cells = None
    if columns is not None:
        in_column: list[list[int]] = [[] for _ in range(len(columns) + 1)]
        for k in order:
            in_column[column_of(parts[k], columns)].append(k)
        if rtl_document:
            in_column.reverse()
        cells = tuple(" ".join(built[k].text for k in ks) for ks in in_column)
    rtl = rtl_document or any(c.rtl for c in components)
    geometry = geometry_of(line.chars)
    marker = len(components) == 1 and columns is None and drawn_marker(geometry, marks, rtl_document)
    return Line(" ".join(c.text for c in components), "".join(c.text for c in line.chars), rtl,
                any(c.ambiguous for c in components), counts, components, cells, geometry, marker, *near)


def drawn_marker(geometry: Geometry, marks: list[tuple[float, float, float, float]], rtl_document: bool) -> bool:
    """האם לפני השורה מצויר תבליט: צורה (page_marks) בגודל של אות, בקצה שממנו מתחילה הקריאה וממורכזת
    אנכית לשורה. כל הגדלים יחסיים לגודל האות של השורה (Geometry.size), ובלי גודל אין תבליט.

    - בגודל של אות: הצד הארוך של הצורה בין MIN_MARK לבין גודל האות.
    - ממורכזת אנכית: המרכז שלה בין קו הבסיס לגודל האות מעליו.
    - בקצה שממנו מתחילה הקריאה (במסמך עברי מימין): כולה מחוץ לטקסט של השורה מהצד הזה, עד MAX_MARK_GAP
      מגודל האות ממנו. השורה בעמוד היא כל האותיות באותו קו בסיס, ולכן אין טקסט שלה בין הצורה לבינו.

    למה צורה: ב-Chrome התבליט של רשימה מצויר כעיגול (48 עיגולים ממולאים ו-2 עיגולים ריקים ברשימה הפנימית,
    במסמך האפיון), ואין לו תו בשכבת הטקסט. כך גם במצגת (Canva) ובמסמך ההגדרות של Social Publisher.
    עיגול ריק ולא רק ממולא: כך מצויר התבליט של רשימה פנימית."""
    size = geometry.size
    if size <= 0:
        return False
    for left, bottom, right, top in marks:
        longest = max(right - left, top - bottom)
        if not MIN_MARK * size <= longest <= size:
            continue
        if not geometry.baseline < (bottom + top) / 2 < geometry.baseline + size:
            continue
        distance = left - geometry.right if rtl_document else geometry.left - right
        if 0 <= distance <= MAX_MARK_GAP * size:
            return True
    return False


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
        rules, verticals = page_rules(pdf_page)
        layout = page_layout(lines, word_gap, rules, verticals)
        marks = page_marks(pdf_page)
        page_lines = [_line(line, layout.boundaries[i], layout.columns[i], rtl, s.counts, marks,
                            (s.near, layout.near[i]))
                      for i, (line, s) in enumerate(zip(lines, spaced))]
        merged = _merged_rows(page_lines, layout.tables, lines, rules, verticals)
        width, height = pdf_page.get_size()
        out.append(PageText(page_lines, found.skipped, found.unknown_brackets, [row.cells for row in merged],
                            [row.source for row in merged], rtl, width, height, found.brackets,
                            found.marked_unmapped, found.rotated, found.reference))
    return out


def page_rules(page) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """קווים שמצוירים בעמוד (קווי מסגרת של טבלה): (אופקיים, אנכיים). אופקי: (שמאל, ימין, y);
    אנכי: (x, תחתית, ראש).

    קו הוא אובייקט ציור (FPDF_PAGEOBJ_PATH) דק וארוך: עובי עד 2 נקודות, ואורך פי 10 מהעובי
    לפחות; אופקי כשהעובי הוא הגובה, ואנכי כשהעובי הוא הרוחב. התיבה מ-PdfObject.get_bounds
    (pypdfium2/_helpers/pageobjects.py), שזורקת PdfiumError כשאין לאובייקט מיקום; אובייקט כזה לא
    יכול להיות קו, ולכן מדולג.
    """
    horizontal, vertical = [], []
    for obj in page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_PATH]):
        try:
            left, bottom, right, top = obj.get_bounds()
        except PdfiumError:
            continue  # אובייקט בלי מיקום על הדף: לא קו שאפשר להשתמש בו
        width, height = right - left, top - bottom
        if height <= 2.0 and width >= 10 * max(height, 0.1):
            horizontal.append((left, right, (top + bottom) / 2))
        elif width <= 2.0 and height >= 10 * max(width, 0.1):
            vertical.append(((left + right) / 2, bottom, top))
    return horizontal, vertical


def page_marks(page) -> list[tuple[float, float, float, float]]:
    """הצורות שמצוירות בעמוד ונראות, לתבליט מצויר (drawn_marker): (שמאל, תחתית, ימין, ראש).

    צורה היא אובייקט ציור (FPDF_PAGEOBJ_PATH) שממולא או שמצויר לו קו: FPDFPath_GetDrawMode מחזיר את
    אופן המילוי (אחד מ-FPDF_FILLMODE_*, ו-FPDF_FILLMODE_NONE הוא בלי מילוי) והאם מצויר קו, ו-FALSE בכשל
    (public/fpdf_edit.h). אובייקט בלי מילוי ובלי קו לא נראה (למשל גבול של חיתוך). התיבה מ-get_bounds,
    כמו ב-page_rules: היא זורקת PdfiumError כשאין לאובייקט מיקום.
    """
    out = []
    fill, stroke = ctypes.c_int(), ctypes.c_int()
    for obj in page.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_PATH]):
        try:
            bounds = obj.get_bounds()
        except PdfiumError:
            continue  # אובייקט בלי מיקום על הדף: אי אפשר לשייך אותו לשורה
        if not pdfium_raw.FPDFPath_GetDrawMode(obj, fill, stroke):
            continue  # לא ידוע אם הוא נראה, ולכן לא ראיה לתבליט
        if fill.value != pdfium_raw.FPDF_FILLMODE_NONE or stroke.value:
            out.append(bounds)
    return out


def table_rows(lines: list[Line], table_of: list[int | None], geometry: list[PageLine],
               rules: list[tuple[float, float, float]],
               verticals: list[tuple[float, float, float]] = ()) -> list[tuple[str, ...]]:
    """השורות של העמוד כתאים, כששורה של טבלה שנשברה לכמה שורות בעמוד מתאחדת לשורה אחת.

    שורה בטבלה היא המשך של השורה שמעליה, כשיש לשתיהן אותן עמודות ולא מתחילה בה שורת טבלה
    חדשה (_new_rows). בכל עמודה, הטקסטים מתחברים ברווח, חוץ מאחרי מקף או לוכסן שצמודים למילה
    (join_lines). שורה מחוץ לטבלה נשארת כמו שהיא (Line.cells).
    """
    return [row.cells for row in _merged_rows(lines, table_of, geometry, rules, verticals)]


@dataclass(frozen=True)
class _MergedRow:
    cells: tuple[str, ...]
    source: RowSource


def _merged_rows(lines: list[Line], table_of: list[int | None], geometry: list[PageLine],
                 rules: list[tuple[float, float, float]],
                 verticals: list[tuple[float, float, float]] = ()) -> list[_MergedRow]:
    """table_rows, ולכל שורה גם מאיפה היא באה (RowSource)."""
    new_row, by_content = _new_rows(lines, table_of, geometry, rules, verticals)
    rows: list[_MergedRow] = []
    current: list[list[str]] | None = None
    current_lines: list[int] = []
    current_table = None

    def flush():
        if current is not None:
            rows.append(_MergedRow(tuple(join_lines(column) for column in current),
                                   RowSource(tuple(current_lines), current_table)))

    for i, (line, table) in enumerate(zip(lines, table_of)):
        cells = line.columns
        if cells is None:
            flush()
            current = None
            rows.append(_MergedRow(line.cells, RowSource((i,), None)))
            continue
        # בטבלה שאינה רשת: שורה עם טקסט בכמה עמודות שכבר מלאות בשורת הטבלה הנוכחית היא שורה חדשה. כך
        # שורת סכום בלי תווית לא נדבקת לשורה שמעליה ("143,875 452,600"), ושורת מספרים מתחת לתווית שנשברה,
        # שהעמודות שלה עוד ריקות, נשארת איתה
        collides = i in by_content and current is not None and sum(
            1 for column, cell in zip(current, cells) if column and cell) >= 2
        if current is not None and table == current_table and len(cells) == len(current) and not new_row[i] \
                and not collides:
            for column, cell in zip(current, cells):
                if cell:
                    column.append(cell)
            current_lines.append(i)
            continue
        flush()
        current = [[cell] if cell else [] for cell in cells]
        current_lines = [i]
        current_table = table
    flush()
    return rows


def _new_rows(lines: list[Line], table_of, geometry: list[PageLine], rules, verticals=()) -> tuple[list[bool], set[int]]:
    """לכל שורה בטבלה: האם מתחילה בה שורת טבלה חדשה; ואילו שורות בטבלה שאינה רשת, שבה גם התוכן
    מכריע (_merged_rows: טקסט בכמה עמודות שכבר מלאות בשורת הטבלה).

    ברשת (_grid: מצוירים בה גבולות של תאים, קו אנכי בין העמודות וקו אופקי בין השורות), קו בין שתי
    שורות בעמוד הוא הגבול בין שורות הטבלה, ובלי קו זו אותה שורה. כך תווית שנשברה לכמה שורות, והמספרים
    שלה בשורה משלהם ביניהן ("הוצאות מכירה, פרסום" / "ושיווק" בדוח הכספי, עמוד 14), הם שורה אחת.
    עד סבב 5ב "יש קווים" נקבע לפי רוב הזוגות של שורות רצופות שהשנייה בהן מתחילה בעמודה הראשונה, וזה
    נכשל בטבלה שהתוויות בה נשברות (בתוך תא אין קו): בעמוד 15 של הדוח הכספי רק 8 מתוך 19 זוגות.
    טבלה שאינה רשת (בלי קווים, או קו רק תחת הכותרת ומעל שורת סכום) נשענת על העמודה הראשונה: שורה
    שיש בה טקסט בעמודה הראשונה (לפי סדר הקריאה) היא שורה חדשה, ושורה בלי טקסט בה היא המשך, חוץ
    מהמקרה של _merged_rows.
    """
    def ruled(i: int) -> bool:
        return rule_between(geometry[i - 1], geometry[i], rules)

    new = [True] * len(lines)
    by_content: set[int] = set()
    by_table: dict[int, list[int]] = {}
    for i, table in enumerate(table_of):
        if table is not None and lines[i].columns is not None:
            by_table.setdefault(table, []).append(i)
    for indices in by_table.values():
        use_rules = _grid(indices, geometry, rules, verticals)
        if not use_rules:
            by_content.update(indices)
        for i in indices[1:]:
            if i - 1 not in indices:
                continue
            new[i] = ruled(i) if use_rules else bool(lines[i].columns[0])
    return new, by_content


def _grid(indices: list[int], geometry: list[PageLine], rules, verticals) -> bool:
    """האם הטבלה (השורות indices בעמוד) היא רשת, כלומר מצוירים בה גבולות של תאים: יש בה קו אנכי בין
    העמודות (בתוך התחום האופקי של הטקסט שלה, וחוצה את קו הבסיס של אחת השורות שלה), וגם קו אופקי בין
    שתי שורות רצופות שלה. בטבלה בלי קווי מסגרת אין קו אנכי, גם כשיש בה קו תחת הכותרת או מעל שורת
    סכום; ובתוכן העניינים של MentorOS יש פס אנכי קצר ליד כל כותרת, אבל אין אף קו אופקי."""
    left = min(geometry[i].left for i in indices)
    right = max(geometry[i].right for i in indices)
    vertical = any(left < x < right and any(bottom < geometry[i].baseline < top for i in indices)
                   for x, bottom, top in verticals)
    return vertical and any(rule_between(geometry[i - 1], geometry[i], rules) for i in indices if i - 1 in indices)


def join_lines(texts: list[str]) -> str:
    """השורות של תא אחד (או של פסקה, markdown.py) כטקסט אחד: ברווח, חוץ מאחרי מקף או לוכסן שצמודים
    למילה שלפניהם (כמו "ל-" ו-"Bot/WebApp/"): שם שבירת שורה מותרת בלי רווח (UAX #14,
    https://www.unicode.org/reports/tr14/: אחרי HY ואחרי SY), ולכן השבירה הייתה בתוך המילה.

    עד סבב 5ב חובר בלי רווח גם טקסט שהשורה הקודמת שלו היא מילה אחת שממלאת את רוחב העמודה, כדי לאחות
    שמות משתנים שנשברו באמצע. הכלל ירד: השבירה באמצע מילה נבעה מהאופן שבו נבנה קובץ הטבלאות
    (overflow-wrap: anywhere), ומחוצה לו הוא טעה ב-41 מתוך 45 הפעמים שבהן הופעל (נספר בסבב 5).
    """
    text = ""
    for i, piece in enumerate(texts):
        if i == 0:
            text = piece
        else:
            before = texts[i - 1]
            inside_a_word = len(before) >= 2 and before[-1] in "-/" and before[-2] != " "
            text += ("" if inside_a_word else " ") + piece
    return text
