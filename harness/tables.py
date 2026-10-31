"""מדידת טבלאות מול דף תשובות אוטומטי (testset/ground_truth): תא מול תא.

דף התשובות נבנה מאותו מקור שממנו נבנה ה-PDF (tools/build_table_pdf.py), ולכן הטקסט שכל
תא מציג ידוע מראש, בלי תיוג ביד. הקובץ testset/ground_truth/<שם>.truth.json שייך ל-PDF
testset/pdfs/<שם>.pdf. המבנה שלו מתואר ב-testset/ground_truth/README.md.

יישור שורות: התא הראשון של כל שורה בדף התשובות ייחודי (שם המשתנה), ולכן שורה בפלט
מותאמת לשורה בדף התשובות לפי התא הראשון שלה, ולא לפי מקומה: שורה שנשברה או נדבקה הייתה
מזיזה את כל השאר. שורה בפלט היא שורה של הקורא, והתאים שלה הם Line.cells. כשכמה שורות
בפלט מתחילות באותו תא (למשל שם משתנה שמופיע לבד בשורה גם מחוץ לטבלה), נבחרת זו שהכי
הרבה מהתאים שלה זהים, ובתיקו הראשונה. שורת הכותרת (rows[0]) לא נמדדת: היא חוזרת בראש
כל עמוד, והתא הראשון שלה לא ייחודי.

תא זהה: באותו מקום בשורה המותאמת (העמודה ה-i), עם אותו טקסט אחרי איחוד רווחים
(textdiff.normalize). תא ריק בדף התשובות צריך להיות תא ריק בפלט, כמו "תא ריק נשאר ריק"
בטבלת התיוג: בלעדיו כל התאים שאחריו זזים מקום. שורה זהה: אותו מספר תאים, וכולם זהים.

ועוד מדד, של המדידה הראשונה שתועדה ב-testset/ground_truth/README.md: תא "שלם בשורה אחת"
הוא תא שהטקסט שלו מופיע ברצף בתוך שורה אחת של הפלט, בכל מקום בקובץ, בלי קשר לגבולות
התאים. הוא מקל, ולא מחליף את ההשוואה תא מול תא: הוא מראה בנפרד את הבעיה של תאים שנשברים
לכמה שורות, גם כשהקורא עוד לא מפריד בין תאים. טקסט קצר מופיע בקלות בתוך תא אחר, ולכן
תאים קצרים מ-4 תווים, "כן", "לא" ו-"-" לא נספרים בו (EXCLUDED_FROM_WHOLE).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from harness.textdiff import join_cells, normalize

TRUTH_SUFFIX = ".truth.json"
MIN_WHOLE_LENGTH = 4
EXCLUDED_FROM_WHOLE = frozenset({"כן", "לא", "-"})


class TruthFileError(ValueError):
    """קובץ דף התשובות לא במבנה הצפוי."""


@dataclass(frozen=True)
class TruthTable:
    section: str | None  # כותרת הסעיף שמעל הטבלה, אם יש
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]  # בלי שורת הכותרת


def pdf_name(truth_path: Path) -> str:
    """שם קובץ ה-PDF שדף התשובות שייך לו: <שם>.truth.json שייך ל-<שם>.pdf."""
    return truth_path.name[:-len(TRUTH_SUFFIX)] + ".pdf"


def load_truth(path: Path) -> list[TruthTable]:
    """הטבלאות שבדף התשובות. זורקת TruthFileError עם הסיבה כשהמבנה לא תקין.

    הקובץ מגיע מחוץ לתהליך (נבנה בסקריפט ונשמר בריפו), ולכן כל שדה נבדק לפני השימוש,
    כולל הייחודיות של התא הראשון, שעליה היישור נשען.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TruthFileError(f"{path.name}: לא JSON תקין ({exc.msg}, שורה {exc.lineno})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tables"), list) or not data["tables"]:
        raise TruthFileError(f"{path.name}: חסרה רשימת tables")
    tables = []
    seen: dict[str, int] = {}
    for number, table in enumerate(data["tables"], 1):
        where = f"{path.name}, טבלה {number}"
        if not isinstance(table, dict):
            raise TruthFileError(f"{where}: לא אובייקט")
        section = table.get("section")
        if section is not None and not isinstance(section, str):
            raise TruthFileError(f"{where}: section אינו טקסט")
        rows = table.get("rows")
        if not isinstance(rows, list) or not rows:
            raise TruthFileError(f"{where}: חסרה רשימת rows")
        for index, row in enumerate(rows):
            if not isinstance(row, list) or not all(isinstance(cell, str) for cell in row):
                raise TruthFileError(f"{where}, שורה {index}: לא רשימה של טקסטים")
        header = tuple(rows[0])
        if not header:
            raise TruthFileError(f"{where}: שורת הכותרת ריקה")
        for index, row in enumerate(rows[1:], 1):
            if len(row) != len(header):
                raise TruthFileError(f"{where}, שורה {index}: {len(row)} תאים במקום {len(header)}")
            first = normalize(row[0])
            if not first:
                raise TruthFileError(f"{where}, שורה {index}: התא הראשון ריק, ואי אפשר ליישר לפיו")
            if first in seen:
                raise TruthFileError(f"{where}, שורה {index}: התא הראשון '{first}' כבר מופיע בטבלה {seen[first]}")
            seen[first] = number
        tables.append(TruthTable(section, header, tuple(tuple(row) for row in rows[1:])))
    return tables


@dataclass(frozen=True)
class ColumnScore:
    name: str  # הכותרת של העמודה; עמודות עם אותה כותרת בכמה טבלאות נספרות יחד
    cells: int = 0
    identical: int = 0
    whole_counted: int = 0  # תאים שנספרים במדד "שלם בשורה אחת"
    whole: int = 0


@dataclass(frozen=True)
class TableScore:
    pdf: str
    rows: int  # שורות בדף התשובות, בלי שורות הכותרת
    aligned: int  # מתוכן: שורות שנמצאה להן שורה בפלט לפי התא הראשון
    identical_rows: int
    columns: tuple[ColumnScore, ...]

    @property
    def cells(self) -> int:
        return sum(c.cells for c in self.columns)

    @property
    def identical_cells(self) -> int:
        return sum(c.identical for c in self.columns)

    @property
    def whole_counted(self) -> int:
        return sum(c.whole_counted for c in self.columns)

    @property
    def whole(self) -> int:
        return sum(c.whole for c in self.columns)


def _counts_for_whole(cell: str) -> bool:
    return len(cell) >= MIN_WHOLE_LENGTH and cell not in EXCLUDED_FROM_WHOLE


def score_tables(pdf: str, tables: Sequence[TruthTable], output: Sequence[Sequence[str]]) -> TableScore:
    """הציון של הפלט מול דף התשובות.

    output: השורות של הקורא בכל הקובץ, לפי הסדר, כל אחת כתאים לפי סדר הקריאה (Line.cells).
    """
    rows_out = [tuple(normalize(cell) for cell in row) for row in output]
    by_first: dict[str, list[int]] = {}
    for index, row in enumerate(rows_out):
        if row:
            by_first.setdefault(row[0], []).append(index)
    texts = [normalize(join_cells(row)) for row in rows_out]

    columns: dict[str, list[int]] = {}  # כותרת -> [תאים, זהים, נספרים לשלם, שלמים]
    rows = aligned = identical_rows = 0
    for table in tables:
        for name in table.header:
            columns.setdefault(name, [0, 0, 0, 0])
        for truth_row in table.rows:
            truth = tuple(normalize(cell) for cell in truth_row)
            rows += 1
            candidates = [rows_out[i] for i in by_first.get(truth[0], [])]
            best: tuple[str, ...] = max(candidates, key=lambda row: sum(_same_cells(row, truth)), default=())
            same = _same_cells(best, truth)
            aligned += bool(candidates)
            identical_rows += bool(candidates) and len(best) == len(truth) and all(same)
            for name, cell, is_same in zip(table.header, truth, same):
                counts = columns[name]
                counts[0] += 1
                counts[1] += is_same
                if _counts_for_whole(cell):
                    counts[2] += 1
                    counts[3] += any(cell in text for text in texts)
    return TableScore(pdf, rows, aligned, identical_rows,
                      tuple(ColumnScore(name, *counts) for name, counts in columns.items()))


def _same_cells(row: Sequence[str], truth: Sequence[str]) -> list[bool]:
    """לכל תא בדף התשובות: האם התא באותו מקום בשורה של הפלט זהה לו. תא שאין בפלט אינו זהה."""
    return [i < len(row) and row[i] == cell for i, cell in enumerate(truth)]
