"""מערך הבדיקה: מריץ את הקורא על כל סט הבדיקה, משווה לשורות המתויגות, וכותב דוח.

שימוש (מתיקיית הריפו):
    python -m harness                       # כותב testset/report.md
    python -m harness --output /tmp/new.md  # לדוח נפרד, למשל כדי להשוות שתי גרסאות

הדוח דטרמיניסטי: בלי תאריך ובלי זמני ריצה, ובסדר קבוע. לכן השוואה בין שתי הרצות
היא git diff על הקובץ, וכל שורה שהשתנתה בדוח היא שינוי אמיתי בתוצאה.

פרטיות: הטקסט שחולץ נכתב רק לקובץ הדוח, ורק לשורות המתויגות (שכבר נמצאות בטבלת
התיוג). מה שמודפס למסך הוא מספרים בלבד.
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from harness import labels as labels_mod
from harness.reader import read_pages
from harness.textdiff import closest_line, normalize, split_lines, visible
from hebrew_pdf.lines import PageText
from hebrew_pdf.indirect_checks import score_final_letters, score_punct_at_start

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDFS = ROOT / "testset" / "pdfs"
DEFAULT_LABELS = ROOT / "testset" / "labels.md"
DEFAULT_OUTPUT = ROOT / "testset" / "report.md"

Reader = Callable[[Path], list[PageText]]


@dataclass(frozen=True)
class PageResult:
    page: int
    line_count: int
    skipped_chars: int
    final_letters: int | None
    punct_at_start: int | None


@dataclass(frozen=True)
class FileResult:
    name: str
    pages: list[PageResult]
    final_letters: int | None
    punct_at_start: int | None


@dataclass(frozen=True)
class LabelResult:
    label: labels_mod.Label
    distance: int
    closest: str

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
    def total_chars(self) -> int:
        return sum(len(normalize(r.label.expected)) for r in self.approved)


def creator_of(file_name: str) -> str:
    """התוכנה שיצרה את הקובץ, כפי שהיא כתובה בשם הקובץ אחרי הקו התחתון האחרון."""
    stem = Path(file_name).stem
    return stem.rsplit("_", 1)[1] if "_" in stem else "—"


def evaluate(pdf_dir: Path, labels_path: Path, reader: Reader = read_pages) -> Evaluation:
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    known = frozenset(p.name for p in pdf_paths)
    all_labels, problems = labels_mod.parse_labels(labels_path.read_text(encoding="utf-8"), known)

    page_texts: dict[str, list[str]] = {}
    files: list[FileResult] = []
    for path in pdf_paths:
        read = reader(path)
        texts = [p.text for p in read]
        page_texts[path.name] = texts
        pages = [
            PageResult(i, sum(1 for l in split_lines(p.text) if normalize(l)), p.skipped_chars,
                       score_final_letters(p.text), score_punct_at_start(p.text))
            for i, p in enumerate(read, 1)
        ]
        whole = "\n".join(texts)
        files.append(FileResult(path.name, pages, score_final_letters(whole), score_punct_at_start(whole)))

    approved: list[LabelResult] = []
    pending: list[labels_mod.Label] = []
    unclear: list[labels_mod.Label] = []
    problems = list(problems)
    for label in sorted(all_labels, key=lambda l: l.number):
        page_count = len(page_texts[label.file])
        if label.page > page_count:
            problems.append(labels_mod.LabelProblem(
                label.source_line, f"עמוד {label.page} לא קיים ב-{label.file} (יש בו {page_count} עמודים)"))
            continue
        if label.status == labels_mod.STATUS_PENDING:
            pending.append(label)
        elif label.status == labels_mod.STATUS_UNCLEAR:
            unclear.append(label)
        else:
            lines = split_lines(page_texts[label.file][label.page - 1])
            distance, closest = closest_line(label.expected, lines)
            approved.append(LabelResult(label, distance, closest))

    reader_name = f"{reader.__module__}.{reader.__qualname__}"
    return Evaluation(reader_name, files, approved, pending, unclear, sorted(problems, key=lambda p: p.source_line))


def _cell(text: str) -> str:
    """טקסט לתא בדוח, שמוצג בדיוק כמו שהוא.

    $ מקבל טיפול נפרד: GitHub מציג $...$ כנוסחה, ולפי התיעוד שלו מחוץ לנוסחה עוטפים
    את ה-$ ב-span (https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions).
    זה לא שייך ל-escape_cell, כי הדוח לא נקרא בחזרה ו-split_row לא מכיר span.
    """
    return labels_mod.escape_cell(visible(text)).replace("$", "<span>$</span>")


def _pct(value: int | None) -> str:
    return "—" if value is None else f"{value}%"


def _numbers(items: list[labels_mod.Label]) -> str:
    return ", ".join(str(label.number) for label in items) if items else "אין"


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
    add(f"| אותיות שדולגו כי אין להן מיקום על הדף (בכל הסט) | {ev.skipped_chars} |")
    add("")
    add("מרחק תווים: כמה הוספות, מחיקות או החלפות של תו בודד צריך כדי להגיע מהשורה הקרובה ביותר בעמוד לטקסט הנכון. 0 = זהה. רצף רווחים נחשב לרווח אחד.")
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
        add("| מספר | קובץ | עמוד | תוצאה | מרחק | הטקסט הנכון | השורה הקרובה ביותר בפלט |")
        add("|---|---|---|---|---|---|---|")
        for r in ev.approved:
            result = "✓ זהה" if r.exact else "✗"
            closest = "" if r.exact else _cell(r.closest)
            add(f"| {r.label.number} | {r.label.file} | {r.label.page} | {result} | {r.distance} | {_cell(r.label.expected)} | {closest} |")
    else:
        add("עדיין אין שורות מאושרות. שורה נספרת רק כשהסטטוס שלה ב-testset/labels.md הוא \"מאושר\".")
    add("")
    add(f"ממתינות לאישור: {_numbers(ev.pending)}")
    add("")
    add(f"לא ברורות: {_numbers(ev.unclear)}")
    add("")

    add("## לפי קובץ")
    add("")
    add("אותיות סופיות: אחוז המילים (מבין אלה שיש בהן אות סופית) שהאות הסופית לא בתחילתן; גבוה = טוב. פיסוק בתחילת שורה: אחוז השורות העבריות שמתחילות בסימן פיסוק; נמוך = טוב. שתיהן בדיקות עקיפות מהאב-טיפוס, ו-100% בהן אינו הוכחה שהפלט נכון.")
    add("")
    add("| קובץ | תוכנה | עמודים | אותיות סופיות | פיסוק בתחילת שורה | מאושרות | זהות | מרחק |")
    add("|---|---|---|---|---|---|---|---|")
    for f in ev.files:
        mine = [r for r in ev.approved if r.label.file == f.name]
        add(f"| {f.name} | {creator_of(f.name)} | {len(f.pages)} | {_pct(f.final_letters)} | {_pct(f.punct_at_start)} "
            f"| {len(mine)} | {sum(r.exact for r in mine)} | {sum(r.distance for r in mine)} |")
    add("")

    add("## לפי עמוד")
    add("")
    add("<details>")
    add("<summary>כל העמודים</summary>")
    add("")
    add("| קובץ | עמוד | שורות עם טקסט | אותיות שדולגו | אותיות סופיות | פיסוק בתחילת שורה |")
    add("|---|---|---|---|---|---|")
    for f in ev.files:
        for p in f.pages:
            lines = str(p.line_count) if p.line_count else "0 (אין טקסט)"
            add(f"| {f.name} | {p.page} | {lines} | {p.skipped_chars} | {_pct(p.final_letters)} | {_pct(p.punct_at_start)} |")
    add("")
    add("</details>")
    add("")
    return "\n".join(out)


def main(argv: list[str] | None = None, reader: Reader = read_pages) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness", description="מערך הבדיקה של בונה השורות")
    parser.add_argument("--pdfs", type=Path, default=DEFAULT_PDFS, help="תיקיית קובצי ה-PDF")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="טבלת התיוג")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="לאן לכתוב את הדוח")
    args = parser.parse_args(argv)

    ev = evaluate(args.pdfs, args.labels, reader)
    args.output.write_text(render_report(ev), encoding="utf-8")

    n = len(ev.approved)
    print(f"מאושרות: {n} | זהות: {ev.exact_count} | מרחק תווים: {ev.total_distance} | "
          f"ממתינות: {len(ev.pending)} | לא ברורות: {len(ev.unclear)} | פגומות: {len(ev.problems)}")
    print(f"הדוח: {args.output}")
    if ev.problems:
        print(f"יש {len(ev.problems)} שורות פגומות בטבלת התיוג; הפירוט בדוח.", file=sys.stderr)
        return 1
    return 0
