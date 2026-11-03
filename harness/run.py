"""מערך הבדיקה: מריץ את הקורא על כל סט הבדיקה, משווה לשורות המתויגות ולדפי התשובות של
הטבלאות, וכותב דוח.

שימוש (מתיקיית הריפו):
    python -m harness                       # כותב testset/report.md
    python -m harness --output /tmp/new.md  # לדוח נפרד, למשל כדי להשוות שתי גרסאות

הדוח דטרמיניסטי: בלי תאריך ובלי זמני ריצה, ובסדר קבוע. לכן השוואה בין שתי הרצות
היא git diff על הקובץ, וכל שורה שהשתנתה בדוח היא שינוי אמיתי בתוצאה.

פרטיות: הטקסט שחולץ נכתב רק לקובץ הדוח, ורק לשורות המתויגות (שכבר נמצאות בטבלת
התיוג). מדידת הטבלאות נכתבת לדוח כמספרים בלבד. מה שמודפס למסך הוא מספרים בלבד.
"""

import argparse
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harness import calibration as calibration_mod
from harness import labels as labels_mod
from harness import markdown_check
from harness.display_check import displays_like_page
from harness.label_order import MISSING, NOT_CHECKED, OrderCheck, check_label_order
from harness.reader import read_pages
from harness.tables import TRUTH_SUFFIX, TableScore, TruthFileError, load_blocks, load_truth, pdf_names, score_tables
from harness.textdiff import CELL_BOUNDARY, closest_line, join_cells, normalize, split_lines, visible
from hebrew_pdf.lines import PageText
from hebrew_pdf.markdown import build_markdown, escape_text
from hebrew_pdf import score as score_mod
from hebrew_pdf.spacing import SpaceCounts
from hebrew_pdf.indirect_checks import score_final_letters, score_punct_at_start

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDFS = ROOT / "testset" / "pdfs"
DEFAULT_LABELS = ROOT / "testset" / "labels.md"
DEFAULT_TRUTH = ROOT / "testset" / "ground_truth"
# ה-Markdown של כל קובץ, לעין. התיקייה ב-.gitignore: יש בה טקסט של המסמכים
DEFAULT_MARKDOWN_DIR = ROOT / "output"
DEFAULT_OUTPUT = ROOT / "testset" / "report.md"

Reader = Callable[[Path], list[PageText]]


@dataclass(frozen=True)
class PageResult:
    page: int
    line_count: int
    skipped_chars: int
    unknown_brackets: int  # סוגריים שהצורה שלהם לא נקבעה מהציור (hebrew_pdf/bracket_shapes.py)
    display_failures: int  # שורות שלא עוברות את בדיקת התצוגה (harness/display_check.py)
    ambiguous_lines: int  # שורות שיותר מקריאה אחת שלהן נראית כמו העמוד
    final_letters: int | None
    punct_at_start: int | None
    spacing: SpaceCounts = SpaceCounts()  # הרווחים לפי הפער מול תווי הרווח שבקובץ (hebrew_pdf/spacing.py)


@dataclass(frozen=True)
class FileResult:
    name: str
    pages: list[PageResult]
    final_letters: int | None
    punct_at_start: int | None

    @property
    def display_failures(self) -> int:
        return sum(p.display_failures for p in self.pages)

    @property
    def ambiguous_lines(self) -> int:
        return sum(p.ambiguous_lines for p in self.pages)

    @property
    def spacing(self) -> SpaceCounts:
        return sum((p.spacing for p in self.pages), SpaceCounts())


@dataclass(frozen=True)
class LabelResult:
    label: labels_mod.Label
    distance: int
    closest: str  # השורה הקרובה ביותר, מנורמלת, עם CELL_BOUNDARY בין התאים (textdiff.join_cells)

    @property
    def exact(self) -> bool:
        return self.distance == 0


@dataclass(frozen=True)
class MarkdownResult:
    """ה-Markdown של קובץ (hebrew_pdf/markdown.py), ומה שהמפרסר האמיתי מוציא ממנו (harness/markdown_check.py)."""
    name: str
    text: str  # ה-Markdown עצמו: נכתב ל-output/, לא לדוח
    pages: int
    headings: int
    paragraphs: int
    items: int
    tables: int  # טבלאות ב-HTML של המפרסר
    completeness: markdown_check.Completeness
    direction: markdown_check.Direction


@dataclass(frozen=True)
class SourceScore:
    """קובץ עם דף תשובות מול המקור שלו, אחרי סיבוב מלא ב-Markdown (harness/markdown_check.py)."""
    pdf: str
    tables_source: int  # טבלאות בדף התשובות
    tables_output: int  # טבלאות שהמפרסר מצא ב-Markdown
    # התאים כמו שהמפרסר מוציא אותם, מול דף התשובות. None: במקור אין טבלאות, ואין מדד תאים (לא "0 מתוך 0");
    # שאר המבנה, כולל מספר הטבלאות ב-Markdown, נמדד ומוצג בכל מקרה
    cells: TableScore | None
    headings: markdown_check.BlockMatch
    items: markdown_check.BlockMatch
    paragraphs: markdown_check.BlockMatch


@dataclass(frozen=True)
class Evaluation:
    reader_name: str
    files: list[FileResult]
    approved: list[LabelResult]
    pending: list[labels_mod.Label]
    unclear: list[labels_mod.Label]
    problems: list[labels_mod.LabelProblem]
    # בדיקת הסדר של כל תיוג שנקרא, בכל סטטוס (harness/label_order.py), לפי מספר התיוג
    orders: dict[int, OrderCheck] = field(default_factory=dict)
    tables: list[TableScore] = field(default_factory=list)  # טבלאות מול דף תשובות (harness/tables.py)
    markdown: list[MarkdownResult] = field(default_factory=list)  # לכל קובץ, לפי הסדר
    sources: list[SourceScore] = field(default_factory=list)  # קבצים עם דף תשובות מול המקור, דרך ה-Markdown
    # הציון של כל עמוד (hebrew_pdf/score.py), לפי שם הקובץ, והכיול של הספים שלו (harness/calibration.py)
    scores: dict[str, list[score_mod.PageScore]] = field(default_factory=dict)
    calibration: calibration_mod.Calibration | None = None

    @property
    def order_ok_count(self) -> int:
        return sum(check.ok for check in self.orders.values())

    @property
    def exact_count(self) -> int:
        return sum(r.exact for r in self.approved)

    @property
    def total_distance(self) -> int:
        return sum(r.distance for r in self.approved)

    @property
    def skipped_chars(self) -> int:
        return sum(p.skipped_chars for f in self.files for p in f.pages)

    @property
    def unknown_brackets(self) -> int:
        return sum(p.unknown_brackets for f in self.files for p in f.pages)

    @property
    def line_count(self) -> int:
        return sum(p.line_count for f in self.files for p in f.pages)

    @property
    def display_failures(self) -> int:
        return sum(f.display_failures for f in self.files)

    @property
    def ambiguous_lines(self) -> int:
        return sum(f.ambiguous_lines for f in self.files)

    @property
    def total_chars(self) -> int:
        return sum(len(normalize(join_cells(r.label.expected))) for r in self.approved)


def creator_of(file_name: str) -> str:
    """התוכנה שיצרה את הקובץ, כפי שהיא כתובה בשם הקובץ אחרי הקו התחתון האחרון."""
    stem = Path(file_name).stem
    return stem.rsplit("_", 1)[1] if "_" in stem else "—"


def evaluate(pdf_dir: Path, labels_path: Path, reader: Reader = read_pages,
             truth_dir: Path | None = DEFAULT_TRUTH) -> Evaluation:
    """truth_dir: תיקיית דפי התשובות. כל דף תשובות חייב לפחות קובץ PDF אחד בסט (tables.pdf_names),
    אחרת TruthFileError. None: בלי מדידה מול דפי תשובות."""
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    known = frozenset(p.name for p in pdf_paths)
    all_labels, problems = labels_mod.parse_labels(labels_path.read_text(encoding="utf-8"), known)

    read_files: dict[str, list[PageText]] = {}
    files: list[FileResult] = []
    markdown: list[MarkdownResult] = []
    parsed_files: dict[str, markdown_check.ParsedHtml] = {}
    dropped: dict[str, frozenset] = {}  # Markdown.dropped של כל קובץ: מה שהציון לא בודק בסבירות
    scores: dict[str, list[score_mod.PageScore]] = {}
    for path in pdf_paths:
        read = reader(path)
        read_files[path.name] = read
        built = build_markdown(read)
        dropped[path.name] = frozenset(built.dropped)
        scores[path.name] = score_mod.score_document(read, built.dropped)
        parsed = markdown_check.parse(markdown_check.to_html(built.text))
        parsed_files[path.name] = parsed
        kinds = [block.kind for block in built.blocks]
        markdown.append(MarkdownResult(path.name, built.text, len(read), kinds.count("heading"),
                                       kinds.count("paragraph"), kinds.count("item"), len(parsed.tables),
                                       markdown_check.completeness(read, built, parsed),
                                       markdown_check.direction(parsed)))
        texts = [p.text for p in read]
        pages = [
            PageResult(i, sum(1 for l in split_lines(p.text) if normalize(l)), p.skipped_chars, p.unknown_brackets,
                       sum(1 for line in p.lines if normalize(line.visual) and not displays_like_page(line)),
                       p.ambiguous_lines, score_final_letters(p.text), score_punct_at_start(p.text), p.spacing)
            for i, p in enumerate(read, 1)
        ]
        whole = "\n".join(texts)
        files.append(FileResult(path.name, pages, score_final_letters(whole), score_punct_at_start(whole)))

    approved: list[LabelResult] = []
    pending: list[labels_mod.Label] = []
    unclear: list[labels_mod.Label] = []
    orders: dict[int, OrderCheck] = {}
    problems = list(problems)
    for label in sorted(all_labels, key=lambda l: l.number):
        page_count = len(read_files[label.file])
        if label.page > page_count:
            problems.append(labels_mod.LabelProblem(
                label.source_line, f"עמוד {label.page} לא קיים ב-{label.file} (יש בו {page_count} עמודים)"))
            continue
        lines = read_files[label.file][label.page - 1].lines
        orders[label.number] = check_label_order(label.expected, lines)
        if label.status == labels_mod.STATUS_PENDING:
            pending.append(label)
        elif label.status == labels_mod.STATUS_UNCLEAR:
            unclear.append(label)
        else:
            distance, closest = closest_line(join_cells(label.expected), _candidates(label, lines))
            approved.append(LabelResult(label, distance, closest))

    tables: list[TableScore] = []
    sources: list[SourceScore] = []
    truth_files: set[str] = set()  # הקבצים שיש להם דף תשובות: כל העמודים שלהם ידועים כנכונים לכיול
    if truth_dir is not None:
        for truth_path in sorted(truth_dir.glob("*" + TRUTH_SUFFIX)):
            names = pdf_names(truth_path, list(read_files))
            if not names:
                raise TruthFileError(f"{truth_path.name}: אין לו קובץ <שם>_<תוכנה>.pdf בתיקיית ה-PDF ({pdf_dir})")
            truth_files.update(names)
            truth = load_truth(truth_path)
            blocks = load_blocks(truth_path)
            for name in names:
                if truth:  # בלי טבלאות במקור אין ציון טבלאות (0 מתוך 0); המבנה נמדד בכל מקרה
                    output = [row for page in read_files[name] for row in page.rows]
                    tables.append(score_tables(name, truth, output))
                parsed = parsed_files[name]
                round_trip = (score_tables(name, truth, [row for table in parsed.tables for row in table])
                              if truth else None)
                structure = parsed.structure
                sources.append(SourceScore(name, len(truth), len(parsed.tables), round_trip,
                                           *(markdown_check.match_blocks(kind, blocks, structure)
                                             for kind in ("heading", "item", "paragraph"))))

    exact_by_page: dict[tuple[str, int], list[bool]] = {}
    for result in approved:
        exact_by_page.setdefault((result.label.file, result.label.page - 1), []).append(result.exact)
    good = calibration_mod.known_good(read_files, truth_files, exact_by_page)
    calibration = calibration_mod.calibrate(read_files, dropped, good, creator_of) if good else None

    reader_name = f"{reader.__module__}.{reader.__qualname__}"
    return Evaluation(reader_name, files, approved, pending, unclear, sorted(problems, key=lambda p: p.source_line),
                      orders, tables, markdown, sources, scores, calibration)


def _candidates(label: labels_mod.Label, lines: list) -> list[str]:
    """השורות בעמוד שמולן נמדד תיוג: כל שורה, עם התאים שלה. תיוג של תא אחד נמדד גם מול כל
    תא בנפרד, לפי "שורה אחת" ב-testset/labels.md: כשבשורה בעמוד יש כמה עמודות או תיבות,
    השורה המתויגת היא רק החלק של העמודה האחת."""
    candidates = [join_cells(line.cells) for line in lines]
    if len(label.expected) == 1:
        candidates += [cell for line in lines if len(line.cells) > 1 for cell in line.cells if cell]
    return candidates


def _cell(text: str) -> str:
    """טקסט לתא בדוח, שמוצג בדיוק כמו שהוא.

    $ מקבל טיפול נפרד: GitHub מציג $...$ כנוסחה, ולפי התיעוד שלו מחוץ לנוסחה עוטפים
    את ה-$ ב-span (https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions).
    זה לא שייך לכלל ההגנה של החבילה (hebrew_pdf.markdown.escape_text), כי הוא תלוי במציג: מחוץ ל-GitHub
    span הוא HTML שנכנס לטקסט, וה-Markdown שהחבילה בונה לא עוטף $. split_row לא מכיר span, והדוח לא
    נקרא בחזרה.
    """
    return escape_text(visible(text)).replace("$", "<span>$</span>")


def _cells(cells: list[str] | tuple[str, ...]) -> str:
    """תאים של שורה לתא בדוח: כל תא מוצג כמו שהוא, ו-<br> ביניהם, כמו בטבלת התיוג.

    <br> נשאר בלי escape, כדי ש-GitHub יציג כל תא בשורה משלו. "<" שבתוך טקסט עובר
    escape ב-_cell, ולכן טקסט "<br>" מוצג כטקסט ולא כגבול.
    """
    return " <br> ".join(_cell(cell) for cell in cells)


def _line_cells(joined: str) -> list[str]:
    """שורה מנורמלת עם CELL_BOUNDARY בין התאים (textdiff.join_cells), חזרה לתאים."""
    return [cell.strip(" ") for cell in joined.split(CELL_BOUNDARY)]


def _order(check: OrderCheck | None) -> str:
    if check is None:
        return "—"
    if check.ok:
        return f"✓ {check.kind}"
    if check.kind == MISSING:
        return f"✗ {check.kind}: {_cell(check.missing)}"
    if check.kind == NOT_CHECKED:
        return f"— {check.kind}"
    return f"✗ {check.kind}"


def _pct(value: int | None) -> str:
    return "—" if value is None else f"{value}%"


def _count_and_share(count: int, of: int) -> str:
    return f"{count} ({100 * count / of:.1f}%)" if of else str(count)


def _numbers(items: list[labels_mod.Label], orders: dict[int, OrderCheck]) -> str:
    """מספרי התיוגים, כל אחד עם תוצאת בדיקת הסדר שלו."""
    return ", ".join(f"{label.number} ({_order(orders.get(label.number))})" for label in items) if items else "אין"


def render_report(ev: Evaluation) -> str:
    n = len(ev.approved)
    out: list[str] = []
    add = out.append
    add("# דוח מערך הבדיקה")
    add("")
    add("> נוצר על ידי `python -m harness`. לא לערוך ביד: כל הרצה כותבת אותו מחדש. השוואה בין שתי הרצות היא git diff על הקובץ הזה.")
    add("")
    add(f"הקורא שנבדק: `{ev.reader_name}`")
    add("")
    add("## סיכום")
    add("")
    add("| | |")
    add("|---|---|")
    add(f"| שורות מאושרות שנספרו | {n} |")
    add(f"| זהות לתיוג | {ev.exact_count} מתוך {n} |")
    add(f"| מרחק תווים כולל | {ev.total_distance} |")
    cer = f"{100 * ev.total_distance / ev.total_chars:.1f}%" if ev.total_chars else "—"
    add(f"| שיעור שגיאת תווים (מרחק חלקי מספר התווים בטקסט הנכון) | {cer} |")
    add(f"| ממתינות לאישור (לא נספרות) | {len(ev.pending)} |")
    add(f"| לא ברורות (לא נספרות) | {len(ev.unclear)} |")
    add(f"| שורות פגומות בטבלת התיוג | {len(ev.problems)} |")
    add(f"| תיוגים שעוברים את בדיקת הסדר (בכל סטטוס) | {ev.order_ok_count} מתוך {len(ev.orders)} |")
    for score in ev.tables:
        add(f"| תאים זהים בטבלאות ({score.pdf}) | {_count_and_share(score.identical_cells, score.cells)} מתוך {score.cells} |")
        add(f"| שורות טבלה זהות ({score.pdf}) | {_count_and_share(score.identical_rows, score.rows)} מתוך {score.rows} |")
    if ev.markdown:
        complete = sum(m.completeness.ok for m in ev.markdown)
        add(f"| קבצים שה-Markdown שלהם שלם (כל האותיות של הקורא, ורק הן) | {complete} מתוך {len(ev.markdown)} |")
    for score in ev.sources:
        cells_name, cells = ("תאים זהים, ", f"{_count_and_share(score.cells.identical_cells, score.cells.cells)} "
                             f"מתוך {score.cells.cells}; ") if score.cells is not None else ("", "")
        add(f"| מבנה אחרי סיבוב ב-Markdown ({score.pdf}): {cells_name}טבלאות, כותרות, פריטים, פסקאות | "
            f"{cells}{score.tables_output} טבלאות מתוך {score.tables_source}; {_structure_counts(score)} |")
    if ev.scores:
        decisions = Counter(page.decision for pages in ev.scores.values() for page in pages)
        add(f"| ציון העמודים (בכל הסט): {' / '.join(score_mod.DECISIONS)} | "
            f"{' / '.join(str(decisions[d]) for d in score_mod.DECISIONS)} |")
    add(f"| אותיות שדולגו כי אין להן מיקום על הדף (בכל הסט) | {ev.skipped_chars} |")
    add(f"| סוגריים שהצורה שלהם לא נקבעה מהציור (בכל הסט) | {ev.unknown_brackets} |")
    add(f"| שורות שלא עוברות את בדיקת התצוגה (בכל הסט) | {ev.display_failures} מתוך {ev.line_count} |")
    add(f"| שורות דו-משמעיות (בכל הסט) | {ev.ambiguous_lines} |")
    add("")
    add("מרחק תווים: כמה הוספות, מחיקות או החלפות של תו בודד צריך כדי להגיע מהשורה הקרובה ביותר בעמוד לטקסט הנכון. 0 = זהה. רצף רווחים נחשב לרווח אחד.")
    add("")
    add("בדיקת התצוגה: כל שורה בסט, לא רק המתויגות, מוצגת באלגוריתם התצוגה של Unicode, בכיוון הפסקה שבו הקורא קרא אותה (כיוון אחד לכל המסמך, לפי רוב השורות, hebrew_pdf/logical_order.document_rtl; במסמך עברי כל שורה מימין לשמאל, גם שורה בלי עברית), ומושווית לסדר האותיות בעמוד. שורה עם כמה רכיבים (תאים, תיבות; hebrew_pdf/layout.py) נבדקת רכיב-רכיב, כי כל רכיב נקרא בנפרד. שורה שנכשלת היא שורה שהפלט שלה לא ייראה כמו העמוד. שורה דו-משמעית היא שורה שיותר מקריאה אחת שלה נראית בדיוק כמו העמוד (למשל \"1 Onboarding\" ו-\"Onboarding 1\"), והקורא בחר לפי ברירת מחדל. ההסבר המלא ב-harness/display_check.py וב-hebrew_pdf/logical_order.py.")
    add("")
    add("בדיקת הסדר של התיוגים: כל \"טקסט נכון\" מוצג באלגוריתם התצוגה של החבילה (hebrew_pdf/logical_order.drawn, כולל שיקוף סוגריים), כל תא בנפרד והתאים מימין לשמאל, ומושווה בלי רווחים לסדר האותיות בשורה בעמוד שיש לה הכי הרבה אותיות משותפות איתו. \"שורה שלמה\" ו-\"חלק מהשורה\" עוברות; \"סדר שונה\" הוא תיוג שגוי בסדר; \"חסר בעמוד\" הוא טקסט שאין בקובץ או שנוסף בתיוג. כך אדם בודק רק תוכן, והמכונה בודקת סדר. ההסבר המלא ב-harness/label_order.py.")
    add("")
    add("שורה עם כמה רכיבים מושווית לתיוג כתאים, עם <br> ביניהם. תיוג של תא אחד נמדד גם מול כל תא בנפרד, לפי \"שורה אחת\" ב-testset/labels.md: כשבשורה בעמוד יש כמה עמודות או תיבות, השורה המתויגת היא רק החלק של העמודה האחת.")
    add("")
    add("המרחק הוא גבול תחתון: כשהקורא שובר שורה מאוד (למשל מדביק אליה עמודה שכנה), שורה אחרת בעמוד יכולה להיות קרובה יותר מהשורה שלה, ואז המרחק קטן מהשגיאה האמיתית. בעמודה \"השורה הקרובה ביותר בפלט\" רואים מול איזו שורה נמדד. המדד הראשי הוא מספר השורות הזהות.")
    add("")

    if ev.problems:
        add("## שורות פגומות בטבלת התיוג")
        add("")
        add("השורות האלה לא נספרו. צריך לתקן אותן ב-testset/labels.md.")
        add("")
        add("| שורה בקובץ | הבעיה |")
        add("|---|---|")
        for problem in ev.problems:
            add(f"| {problem.source_line} | {_cell(problem.message)} |")
        add("")

    add("## שורות מתויגות")
    add("")
    if ev.approved:
        add("| מספר | קובץ | עמוד | תוצאה | מרחק | סדר התיוג | הטקסט הנכון | השורה הקרובה ביותר בפלט |")
        add("|---|---|---|---|---|---|---|---|")
        for r in ev.approved:
            result = "✓ זהה" if r.exact else "✗"
            closest = "" if r.exact else _cells(_line_cells(r.closest))
            add(f"| {r.label.number} | {r.label.file} | {r.label.page} | {result} | {r.distance} "
                f"| {_order(ev.orders.get(r.label.number))} | {_cells(r.label.expected)} | {closest} |")
    else:
        add("עדיין אין שורות מאושרות. שורה נספרת רק כשהסטטוס שלה ב-testset/labels.md הוא \"מאושר\".")
    add("")
    add(f"ממתינות לאישור: {_numbers(ev.pending, ev.orders)}")
    add("")
    add(f"לא ברורות: {_numbers(ev.unclear, ev.orders)}")
    add("")

    if ev.tables:
        add("## טבלאות מול דף תשובות")
        add("")
        add("כל קובץ ב-testset/ground_truth הוא דף התשובות של PDF בסט, שנבנה מאותו מקור (tools/build_table_pdf.py), ולכן הטקסט של כל תא ידוע. שורה בפלט מותאמת לשורה בדף התשובות לפי התא הראשון שלה (שם המשתנה, ייחודי), ולא לפי מקומה. תא זהה: באותה עמודה בשורה המותאמת, עם אותו טקסט; תא ריק בדף התשובות צריך להיות תא ריק בפלט. שורה זהה: כל התאים שלה זהים. \"שלם בשורה אחת\": התא מופיע ברצף בתוך שורה אחת של הפלט, בלי קשר לגבולות התאים; זה המדד של המדידה הראשונה (testset/ground_truth/README.md), והוא לא כולל תאים קצרים מ-4 תווים, \"כן\", \"לא\" ו-\"-\". ההסבר המלא ב-harness/tables.py.")
        add("")
        for score in ev.tables:
            add(f"### {score.pdf}")
            add("")
            add("| | |")
            add("|---|---|")
            add(f"| שורות בדף התשובות (בלי שורות כותרת) | {score.rows} |")
            add(f"| שורות שנמצאו בפלט לפי התא הראשון | {_count_and_share(score.aligned, score.rows)} |")
            add(f"| שורות זהות | {_count_and_share(score.identical_rows, score.rows)} |")
            add(f"| תאים זהים | {_count_and_share(score.identical_cells, score.cells)} מתוך {score.cells} |")
            add(f"| תאים שלמים בשורה אחת | {_count_and_share(score.whole, score.whole_counted)} מתוך {score.whole_counted} |")
            add("")
            add("| עמודה | תאים | זהים | שלמים בשורה אחת |")
            add("|---|---|---|---|")
            for column in score.columns:
                whole = f"{_count_and_share(column.whole, column.whole_counted)} מתוך {column.whole_counted}"
                add(f"| {_cell(column.name)} | {column.cells} | {_count_and_share(column.identical, column.cells)} | {whole} |")
            add("")

    if ev.markdown:
        _markdown_section(ev, add)

    if ev.scores:
        _score_section(ev, add)

    add("## לפי קובץ")
    add("")
    add("אותיות סופיות: אחוז המילים (מבין אלה שיש בהן אות סופית) שהאות הסופית לא בתחילתן; גבוה = טוב. פיסוק בתחילת שורה: אחוז השורות העבריות שמתחילות בסימן פיסוק; נמוך = טוב. שתיהן בדיקות עקיפות מהאב-טיפוס, ו-100% בהן אינו הוכחה שהפלט נכון.")
    add("")
    add("| קובץ | תוכנה | עמודים | אותיות סופיות | פיסוק בתחילת שורה | בדיקת תצוגה נכשלה | דו-משמעיות | מאושרות | זהות | מרחק |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for f in ev.files:
        mine = [r for r in ev.approved if r.label.file == f.name]
        add(f"| {f.name} | {creator_of(f.name)} | {len(f.pages)} | {_pct(f.final_letters)} | {_pct(f.punct_at_start)} "
            f"| {f.display_failures} | {f.ambiguous_lines} | {len(mine)} | {sum(r.exact for r in mine)} | {sum(r.distance for r in mine)} |")
    add("")

    add("## ריווח לפי תוכנה")
    add("")
    add("הרווחים בפלט נקבעים לפי הפערים בעמוד ולא לפי תווי הרווח שבקובץ: תווי הרווח יורדים, ורווח נכנס בכל פער בין שני תווים שגדול מהפער הרגיל בין אותיות באותה שורה, ועוד חצי רוחב רווח (hebrew_pdf/spacing.py). כל פער בין שני תווים סמוכים נספר פעם אחת. \"עם רווח בקובץ\": פערים שהיה בהם תו רווח בקובץ. \"ירדו\": מתוכם, פערים שלא נכנס בהם רווח. \"נוספו\": פערים בלי תו רווח בקובץ שנכנס בהם רווח. האחוזים הם מתוך הפערים עם רווח בקובץ.")
    add("")
    add("| תוכנה | קבצים | עם רווח בקובץ | ירדו | נוספו |")
    add("|---|---|---|---|---|")
    by_creator: dict[str, tuple[int, SpaceCounts]] = {}
    for f in ev.files:
        files, counts = by_creator.get(creator_of(f.name), (0, SpaceCounts()))
        by_creator[creator_of(f.name)] = (files + 1, counts + f.spacing)
    total = SpaceCounts()
    for creator, (files, counts) in sorted(by_creator.items()):
        total += counts
        add(f"| {creator} | {files} | {counts.in_file} | {_count_and_share(counts.dropped, counts.in_file)} "
            f"| {_count_and_share(counts.added, counts.in_file)} |")
    add(f"| סך הכול | {len(ev.files)} | {total.in_file} | {_count_and_share(total.dropped, total.in_file)} "
        f"| {_count_and_share(total.added, total.in_file)} |")
    add("")

    add("## לפי עמוד")
    add("")
    add("<details>")
    add("<summary>כל העמודים</summary>")
    add("")
    add("| קובץ | עמוד | שורות עם טקסט | אותיות שדולגו | סוגריים בלי צורה | בדיקת תצוגה נכשלה | דו-משמעיות | אותיות סופיות | פיסוק בתחילת שורה | ציון |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for f in ev.files:
        page_scores = ev.scores.get(f.name, [])
        for p in f.pages:
            lines = str(p.line_count) if p.line_count else "0 (אין טקסט)"
            decision = page_scores[p.page - 1].decision if p.page <= len(page_scores) else "—"
            add(f"| {f.name} | {p.page} | {lines} | {p.skipped_chars} | {p.unknown_brackets} | {p.display_failures} | {p.ambiguous_lines} "
                f"| {_pct(p.final_letters)} | {_pct(p.punct_at_start)} | {decision} |")
    add("")
    add("</details>")
    add("")
    return "\n".join(out)


def _structure_counts(score: SourceScore) -> str:
    """"כותרות 5/9, פריטים 3/3, פסקאות 10/14": הזהים באותו סדר, מתוך מה שבדף התשובות."""
    return ", ".join(f"{name} {match.in_order}/{match.source}" for name, match in
                     (("כותרות", score.headings), ("פריטים", score.items), ("פסקאות", score.paragraphs)))


def _markdown_section(ev: Evaluation, add) -> None:
    add("## Markdown")
    add("")
    add("ה-Markdown של כל קובץ נבנה מהמבנה שהקורא מוציא (hebrew_pdf/markdown.py), ונקרא בחזרה במפרסר GFM אמיתי, cmark-gfm, שבו GitHub מציג Markdown (harness/markdown_check.py). הקובץ עצמו נכתב ל-output/, ולא לדוח.")
    add("")
    add("שלמות: האותיות שהמפרסר מציג, בלי רווחים, מול האותיות של הקורא בכל המסמך, חוץ משלושה דברים שנספרים כאן: כותרות עליונות ותחתונות שירדו (שורה או רכיב שחוזרים כמעט זהים באותו גובה, ברצף של עמודים או ברוב העמודים; hebrew_pdf/markdown.py, סעיף 1), שורות כותרת חוזרות של טבלה שהתאחדה עם העמוד הקודם, וסימני פריטים שהפכו לתחביר של רשימה (תבליט ומספר). ✓: אף אות לא נעלמה ולא נוספה, ומספר הפריטים ב-HTML שווה למספר הפריטים שנבנו. \"מתחילים באות לטינית\": פסקאות, כותרות ופריטים (ובנפרד תאים) שהאות החזקה הראשונה בהם לטינית, ולכן מציג שקובע כיוון לפי האות הראשונה יציג אותם משמאל לימין, אף שהמסמך עברי.")
    add("")
    add("| קובץ | עמודים | כותרות | פסקאות | פריטים | טבלאות | כותרות עליונות ותחתונות שירדו | כותרות חוזרות של טבלה שירדו | סימני פריטים | שלמות | מתחילים באות לטינית (מתוך פסקאות, כותרות ופריטים) | תאים שמתחילים באות לטינית |")
    add("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in ev.markdown:
        c, d = m.completeness, m.direction
        if c.ok:
            complete = "✓"
        else:
            parts = []
            if c.missing:
                parts.append(f"חסרות {sum(c.missing.values())}")
            if c.extra:
                parts.append(f"נוספו {sum(c.extra.values())}")
            if c.items != c.expected_items:
                parts.append(f"פריטים {c.items} מתוך {c.expected_items}")
            complete = "✗ " + ", ".join(parts)
        add(f"| {m.name} | {m.pages} | {m.headings} | {m.paragraphs} | {m.items} | {m.tables} | {c.dropped_units} "
            f"| {c.repeated_headers} | {c.list_markers} | {complete} | {d.ltr_blocks} מתוך {d.blocks} | {d.ltr_cells} מתוך {d.cells} |")
    add("")
    if ev.sources:
        add("### מבנה מול דף התשובות")
        add("")
        add("לכל קובץ שיש לו דף תשובות (testset/ground_truth): המבנה שהמפרסר מוציא מה-Markdown, מול המבנה שבדף התשובות, שנגזר מה-HTML שממנו נבנה ה-PDF (harness/html_structure.py, אותו פירוק בשני הצדדים). \"זהים\": באותו סדר (התת-סדרה המשותפת הארוכה ביותר), עם אותו טקסט ובאותה רמה: בכותרת h1 עד h6, ובפריט עומק הקינון. פסקה בתוך ציטוט נמדדת כפסקה. התאים: כמו בסעיף הטבלאות, אבל מהתאים שהמפרסר מוציא מה-Markdown.")
        add("")
    for score in ev.sources:
        add(f"#### {score.pdf}")
        add("")
        add("| | |")
        add("|---|---|")
        add(f"| טבלאות (במקור / ב-Markdown) | {score.tables_source} / {score.tables_output} |")
        for name, match in (("כותרות", score.headings), ("פריטי רשימה", score.items), ("פסקאות", score.paragraphs)):
            add(f"| {name} במקור / ב-Markdown | {match.source} / {match.output} |")
            add(f"| {name} זהות באותו סדר | {_count_and_share(match.in_order, match.source)} מתוך {match.source} |")
            if match.kind != "paragraph":
                add(f"| כנ\"ל, בלי תנאי על הרמה | {_count_and_share(match.in_order_any_level, match.source)} מתוך {match.source} |")
        if score.cells is not None:
            add(f"| תאים זהים אחרי סיבוב ב-Markdown | "
                f"{_count_and_share(score.cells.identical_cells, score.cells.cells)} מתוך {score.cells.cells} |")
            add(f"| שורות זהות אחרי סיבוב ב-Markdown | {_count_and_share(score.cells.identical_rows, score.cells.rows)} |")
        add("")


def _score_section(ev: Evaluation, add) -> None:
    add("## ציון וסימון")
    add("")
    add("לכל עמוד: החלטה (תקין, לא בטוח, נפסל) וסיבות (hebrew_pdf/score.py). נפסל, בלי ציון: עמוד בלי טקסט, טקסט מסובב, או תו שלא ממופה בקובץ (תו בקרה, אזור השימוש הפרטי, U+FFFD, או תו ש-PDFium מסמן כחסר ערך Unicode). לא בטוח: אחד משלושת הצירים נכשל. סבירות: שורה שלא מוצגת כמו העמוד, או שיעור נמוך של מילים סבירות (הגבול התחתון של Wilson), רק במה שמגיע ל-Markdown. שלמות: התווים של הפלט, בלי סדר, מול כל התווים של העמוד לפי PDFium. מאמץ תיקון: שיעור ההחלטות של הקורא ששינו את הקובץ (רווחים וסוגריים). \"הסיבות הנפוצות\": בכמה עמודים של הקובץ מופיעה כל סיבה.")
    add("")
    add(f"| קובץ | עמודים | {' | '.join(score_mod.DECISIONS)} | הסיבות הנפוצות |")
    add("|---|---|---|---|---|---|")
    for name, pages in ev.scores.items():
        decisions = Counter(page.decision for page in pages)
        kinds = Counter(kind for page in pages for kind in {reason.kind for reason in page.reasons})
        common = ", ".join(f"{score_mod.REASON_KINDS[kind]} ({count})" for kind, count in
                           sorted(kinds.items(), key=lambda item: (-item[1], item[0]))[:3]) or "—"
        add(f"| {name} | {len(pages)} | {' | '.join(str(decisions[d]) for d in score_mod.DECISIONS)} | {common} |")
    add("")
    add("### עמודים שלא יצאו תקין")
    add("")
    add("| קובץ | עמוד | החלטה | סיבות |")
    add("|---|---|---|---|")
    for name, pages in ev.scores.items():
        for number, page in enumerate(pages, 1):
            if page.decision != score_mod.OK:
                add(f"| {name} | {number} | {page.decision} | {_cell('; '.join(reason.text for reason in page.reasons))} |")
    add("")
    if ev.calibration is not None:
        _calibration_section(ev.calibration, add)


def _share(count: int, of: int) -> str:
    return f"{count} ({100 * count / of:.0f}%)" if of else "—"


def _calibration_section(cal: calibration_mod.Calibration, add) -> None:
    add("### כיול")
    add("")
    add(f"הספים נקבעים כאן ולא ביד (harness/calibration.py). עמודים שהפלט שלהם ידוע כנכון: {cal.known_good} (כל העמודים של הקבצים שיש להם דף תשובות, ועמודים שכל השורות המתויגות בהם זהות). מתוכם {cal.clean} בלי כשל ודאי (פסילה, שורה שלא מוצגת כמו העמוד, תו שחסר או נוסף), ועליהם נמדדות ההשחתות. ההשחתה היא של הטקסט שהקורא הוציא, ומה שבעמוד ורשימת התווים של PDFium לא משתנים, חוץ מ\"תווי בקרה במקום אותיות\", שהוא כשל של הקובץ. עוצמה: רכיב אחד בעמוד, או כל הרכיבים שהצורה חלה עליהם.")
    add("")
    add("#### שגיאות מכוונות: כמה נתפסו")
    add("")
    add("\"נתפסו\": העמוד לא יצא תקין. בעמודות שאחריה: לפי איזה כלל (עמוד יכול להיתפס ביותר מאחד).")
    add("")
    add("| צורה | עוצמה | עמודים | נתפסו | נפסל | שורה שלא מוצגת כמו העמוד | סימנים (סבירות) | שלמות | מאמץ |")
    add("|---|---|---|---|---|---|---|---|---|")
    for form, intensity, count, hits in calibration_mod.catch_table(cal):
        add(f"| {calibration_mod.form_name(form)} | {calibration_mod.intensity_name(intensity)} | {count} | {_share(hits['כלשהו'], count)} "
            f"| {_share(hits['נפסל'], count)} | {_share(hits['תצוגה'], count)} | {_share(hits['סימנים'], count)} "
            f"| {_share(hits['שלמות'], count)} | {_share(hits['מאמץ'], count)} |")
    add("")
    good, clean = cal.known_good_flagged, cal.clean_flagged
    add(f"עמודים לא מושחתים שסומנו: מתוך {cal.known_good} העמודים הידועים כנכונים, {good['כלשהו']} לא יצאו תקין: "
        f"{good['תצוגה']} בגלל שורה שלא מוצגת כמו העמוד, {good['שלמות']} בגלל תו שחסר או נוסף, {good['סימנים']} בגלל "
        f"הסימנים של הסבירות, {good['מאמץ']} בגלל מאמץ התיקון, ו-{good['נפסל']} נפסלו. מתוך {cal.clean} העמודים בלי "
        f"כשל ודאי, שעליהם נמדדו ההשחתות: {clean['כלשהו']} ({clean['סימנים']} בסימנים, {clean['מאמץ']} במאמץ).")
    add("")
    add("#### הספים")
    add("")
    add("| סף | ערך | הטווח שבו ההחלטות והסיבות בכל הסט זהות | איך נקבע |")
    add("|---|---|---|---|")
    if cal.plausible_choice is not None:
        plausible_how = (f"הדרישה: האחוזון ה-95 של הציון של עמודים שכל השורות בהם הפוכות (היפוך שורה שלמה, היפוך אותיות "
                         f"בתוך מילה): {cal.required_plausible:.3f}. הטווח היציב הראשון שכולו מעליה: "
                         f"{cal.plausible_choice.low:.3f} עד {cal.plausible_choice.high:.3f}, והערך באמצע שלו")
    else:
        plausible_how = "אין עמודים מושחתים לכיול בסט הזה, והכיול לא בוחר ערך"
    if cal.effort_choice is not None:
        effort_how = (f"המאמץ הגבוה ביותר בעמוד ידוע כנכון: {cal.envelope:.3f}. הטווח היציב שמכיל אותו: "
                      f"{cal.effort_choice.low:.3f} עד {cal.effort_choice.high:.3f}, והערך באמצע שלו")
    else:
        effort_how = "אין עמוד ידוע כנכון בסט הזה, והכיול לא בוחר ערך"
    add(f"| MIN_PLAUSIBLE | {score_mod.MIN_PLAUSIBLE:.3f} | {cal.plausible_range.low:.3f} עד {cal.plausible_range.high:.3f} "
        f"| {plausible_how} |")
    add(f"| MAX_EFFORT | {score_mod.MAX_EFFORT:.3f} | {cal.effort_range.low:.3f} עד {cal.effort_range.high:.3f} | {effort_how} |")
    for label, counts in cal.count_rules.items():
        spread = ", ".join(f"{k if k < 3 else '3 ומעלה'}: {counts[k]}" for k in sorted(counts)) or "אין"
        add(f"| {label} | 1 | — | כל אחד הוא כשל ודאי. עמודים בסט לפי המספר: {spread} |")
    add("")
    for name, value, chosen in (("MIN_PLAUSIBLE", score_mod.MIN_PLAUSIBLE, cal.plausible_choice),
                                ("MAX_EFFORT", score_mod.MAX_EFFORT, cal.effort_choice)):
        if chosen is not None and abs(value - chosen.middle) > 0.0005:
            add(f"> [!WARNING]\n> {name} הוא {value:.3f}, והכיול בוחר {chosen.middle:.3f}. צריך לעדכן את הקבוע ב-hebrew_pdf/score.py.")
            add("")
    add("#### השארת תוכנה אחת בחוץ")
    add("")
    add("לכל תוכנה: הספים מחושבים מהעמודים של שאר התוכנות, ונבדקים על העמודים שלה. סבירות: הדרישה (האחוזון ה-95 של העמודים המושחתים של שאר התוכנות), כמה מהעמודים המושחתים של התוכנה הסימנים תפסו בה, וכמה מהעמודים הנקיים שלה סומנו בה. מאמץ: המאמץ הגבוה ביותר בעמוד ידוע כנכון של שאר התוכנות, וכמה מהעמודים של התוכנה מעליו.")
    add("")
    add("| תוכנה | עמודים נקיים ידועים | דרישה לסבירות | עמודים הפוכים שנתפסו | עמודים נקיים שסומנו | מעטפת המאמץ | עמודים מעליה |")
    add("|---|---|---|---|---|---|---|")
    for fold in cal.folds:
        required = f"{fold.required:.3f}" if fold.required is not None else "—"
        envelope = f"{fold.envelope:.3f}" if fold.envelope is not None else "—"
        add(f"| {fold.producer} | {fold.pages} | {required} | {fold.caught[0]} מתוך {fold.caught[1]} | {fold.flagged[0]} מתוך {fold.flagged[1]} "
            f"| {envelope} | {fold.over[0]} מתוך {fold.over[1]} |")
    add("")


def main(argv: list[str] | None = None, reader: Reader = read_pages) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness", description="מערך הבדיקה של בונה השורות")
    parser.add_argument("--pdfs", type=Path, default=DEFAULT_PDFS, help="תיקיית קובצי ה-PDF")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="טבלת התיוג")
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH, help="תיקיית דפי התשובות של הטבלאות")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="לאן לכתוב את הדוח")
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR,
                        help="לאן לכתוב את ה-Markdown של כל קובץ (<שם>.md)")
    args = parser.parse_args(argv)

    ev = evaluate(args.pdfs, args.labels, reader, args.truth)
    args.output.write_text(render_report(ev), encoding="utf-8")
    args.markdown_dir.mkdir(parents=True, exist_ok=True)
    for m in ev.markdown:
        (args.markdown_dir / (Path(m.name).stem + ".md")).write_text(m.text, encoding="utf-8")

    n = len(ev.approved)
    print(f"מאושרות: {n} | זהות: {ev.exact_count} | מרחק תווים: {ev.total_distance} | "
          f"ממתינות: {len(ev.pending)} | לא ברורות: {len(ev.unclear)} | פגומות: {len(ev.problems)}")
    print(f"בדיקת הסדר של התיוגים: {ev.order_ok_count} מתוך {len(ev.orders)}")
    if ev.tables:
        cells = sum(s.cells for s in ev.tables)
        rows = sum(s.rows for s in ev.tables)
        print(f"טבלאות: תאים זהים {sum(s.identical_cells for s in ev.tables)} מתוך {cells} | "
              f"שורות זהות {sum(s.identical_rows for s in ev.tables)} מתוך {rows}")
    if ev.markdown:
        print(f"Markdown: שלם ב-{sum(m.completeness.ok for m in ev.markdown)} מתוך {len(ev.markdown)} קבצים | "
              f"נכתב ל-{args.markdown_dir}")
    for score in ev.sources:
        cells = (f"תאים זהים {score.cells.identical_cells} מתוך {score.cells.cells} | "
                 if score.cells is not None else "")
        print(f"מבנה ({score.pdf}): {cells}טבלאות {score.tables_output} מתוך {score.tables_source} | "
              f"{_structure_counts(score)}")
    print(f"הדוח: {args.output}")
    if ev.problems:
        print(f"יש {len(ev.problems)} שורות פגומות בטבלת התיוג; הפירוט בדוח.", file=sys.stderr)
        return 1
    return 0
