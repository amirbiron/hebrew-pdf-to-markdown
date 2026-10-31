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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harness import labels as labels_mod
from harness.display_check import displays_like_page
from harness.label_order import MISSING, NOT_CHECKED, OrderCheck, check_label_order
from harness.reader import read_pages
from harness.tables import TRUTH_SUFFIX, TableScore, TruthFileError, load_truth, pdf_name, score_tables
from harness.textdiff import CELL_BOUNDARY, closest_line, join_cells, normalize, split_lines, visible
from hebrew_pdf.lines import PageText
from hebrew_pdf.spacing import SpaceCounts
from hebrew_pdf.indirect_checks import score_final_letters, score_punct_at_start

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDFS = ROOT / "testset" / "pdfs"
DEFAULT_LABELS = ROOT / "testset" / "labels.md"
DEFAULT_TRUTH = ROOT / "testset" / "ground_truth"
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
    """truth_dir: תיקיית דפי התשובות של הטבלאות. כל דף תשובות חייב קובץ PDF בסט
    (tables.pdf_name), אחרת TruthFileError. None: בלי מדידת טבלאות."""
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    known = frozenset(p.name for p in pdf_paths)
    all_labels, problems = labels_mod.parse_labels(labels_path.read_text(encoding="utf-8"), known)

    read_files: dict[str, list[PageText]] = {}
    files: list[FileResult] = []
    for path in pdf_paths:
        read = reader(path)
        read_files[path.name] = read
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
            distance, closest = closest_line(join_cells(label.expected), [join_cells(line.cells) for line in lines])
            approved.append(LabelResult(label, distance, closest))

    tables: list[TableScore] = []
    if truth_dir is not None:
        for truth_path in sorted(truth_dir.glob("*" + TRUTH_SUFFIX)):
            name = pdf_name(truth_path)
            if name not in read_files:
                raise TruthFileError(f"{truth_path.name}: אין קובץ {name} בתיקיית ה-PDF ({pdf_dir})")
            output = [line.cells for page in read_files[name] for line in page.lines]
            tables.append(score_tables(name, load_truth(truth_path), output))

    reader_name = f"{reader.__module__}.{reader.__qualname__}"
    return Evaluation(reader_name, files, approved, pending, unclear, sorted(problems, key=lambda p: p.source_line),
                      orders, tables)


def _cell(text: str) -> str:
    """טקסט לתא בדוח, שמוצג בדיוק כמו שהוא.

    $ מקבל טיפול נפרד: GitHub מציג $...$ כנוסחה, ולפי התיעוד שלו מחוץ לנוסחה עוטפים
    את ה-$ ב-span (https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions).
    זה לא שייך ל-escape_cell, כי הדוח לא נקרא בחזרה ו-split_row לא מכיר span.
    """
    return labels_mod.escape_cell(visible(text)).replace("$", "<span>$</span>")


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
    add(f"| אותיות שדולגו כי אין להן מיקום על הדף (בכל הסט) | {ev.skipped_chars} |")
    add(f"| סוגריים שהצורה שלהם לא נקבעה מהציור (בכל הסט) | {ev.unknown_brackets} |")
    add(f"| שורות שלא עוברות את בדיקת התצוגה (בכל הסט) | {ev.display_failures} מתוך {ev.line_count} |")
    add(f"| שורות דו-משמעיות (בכל הסט) | {ev.ambiguous_lines} |")
    add("")
    add("מרחק תווים: כמה הוספות, מחיקות או החלפות של תו בודד צריך כדי להגיע מהשורה הקרובה ביותר בעמוד לטקסט הנכון. 0 = זהה. רצף רווחים נחשב לרווח אחד.")
    add("")
    add("בדיקת התצוגה: כל שורה בסט, לא רק המתויגות, מוצגת באלגוריתם התצוגה של Unicode, בכיוון הפסקה שבו הקורא קרא אותה (Line.rtl: כיוון אחד לכל המסמך, לפי hebrew_pdf/logical_order.document_rtl; במסמך עברי כל שורה מימין לשמאל, גם שורה בלי עברית), ומושווית לסדר האותיות בעמוד. שורה שנכשלת היא שורה שהפלט שלה לא ייראה כמו העמוד. שורה דו-משמעית היא שורה שיותר מקריאה אחת שלה נראית בדיוק כמו העמוד (למשל \"1 Onboarding\" ו-\"Onboarding 1\"), והקורא בחר לפי ברירת מחדל. ההסבר המלא ב-harness/display_check.py וב-hebrew_pdf/logical_order.py.")
    add("")
    add("בדיקת הסדר של התיוגים: כל \"טקסט נכון\" מוצג באלגוריתם התצוגה של החבילה (hebrew_pdf/logical_order.drawn, כולל שיקוף סוגריים), כל תא בנפרד והתאים מימין לשמאל, ומושווה בלי רווחים לסדר האותיות בשורה בעמוד שיש לה הכי הרבה אותיות משותפות איתו. \"שורה שלמה\" ו-\"חלק מהשורה\" עוברות; \"סדר שונה\" הוא תיוג שגוי בסדר; \"חסר בעמוד\" הוא טקסט שאין בקובץ או שנוסף בתיוג. כך אדם בודק רק תוכן, והמכונה בודקת סדר. ההסבר המלא ב-harness/label_order.py.")
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
    add("| קובץ | עמוד | שורות עם טקסט | אותיות שדולגו | סוגריים בלי צורה | בדיקת תצוגה נכשלה | דו-משמעיות | אותיות סופיות | פיסוק בתחילת שורה |")
    add("|---|---|---|---|---|---|---|---|---|")
    for f in ev.files:
        for p in f.pages:
            lines = str(p.line_count) if p.line_count else "0 (אין טקסט)"
            add(f"| {f.name} | {p.page} | {lines} | {p.skipped_chars} | {p.unknown_brackets} | {p.display_failures} | {p.ambiguous_lines} "
                f"| {_pct(p.final_letters)} | {_pct(p.punct_at_start)} |")
    add("")
    add("</details>")
    add("")
    return "\n".join(out)


def main(argv: list[str] | None = None, reader: Reader = read_pages) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness", description="מערך הבדיקה של בונה השורות")
    parser.add_argument("--pdfs", type=Path, default=DEFAULT_PDFS, help="תיקיית קובצי ה-PDF")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="טבלת התיוג")
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH, help="תיקיית דפי התשובות של הטבלאות")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="לאן לכתוב את הדוח")
    args = parser.parse_args(argv)

    ev = evaluate(args.pdfs, args.labels, reader, args.truth)
    args.output.write_text(render_report(ev), encoding="utf-8")

    n = len(ev.approved)
    print(f"מאושרות: {n} | זהות: {ev.exact_count} | מרחק תווים: {ev.total_distance} | "
          f"ממתינות: {len(ev.pending)} | לא ברורות: {len(ev.unclear)} | פגומות: {len(ev.problems)}")
    print(f"בדיקת הסדר של התיוגים: {ev.order_ok_count} מתוך {len(ev.orders)}")
    if ev.tables:
        cells = sum(s.cells for s in ev.tables)
        rows = sum(s.rows for s in ev.tables)
        print(f"טבלאות: תאים זהים {sum(s.identical_cells for s in ev.tables)} מתוך {cells} | "
              f"שורות זהות {sum(s.identical_rows for s in ev.tables)} מתוך {rows}")
    print(f"הדוח: {args.output}")
    if ev.problems:
        print(f"יש {len(ev.problems)} שורות פגומות בטבלת התיוג; הפירוט בדוח.", file=sys.stderr)
        return 1
    return 0
