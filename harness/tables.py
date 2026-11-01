"""מדידת טבלאות מול דף תשובות אוטומטי (testset/ground_truth): תא מול תא.

דף התשובות נבנה מאותו מקור שממנו נבנה ה-PDF (tools/build_table_pdf.py), ולכן הטקסט שכל
תא מציג ידוע מראש, בלי תיוג ביד. דף תשובות שייך למקור ולא לקובץ: testset/ground_truth/<שם>.truth.json
שייך לכל PDF בשם testset/pdfs/<שם>_<תוכנה>.pdf (pdf_names), כי אותו מקור יכול להיות מודפס בכמה תוכנות.
המבנה שלו מתואר ב-testset/ground_truth/README.md: רשימת בלוקים לפי הסדר (harness/html_structure.py),
והטבלאות הן הבלוקים מסוג table.

יישור שורות: שורה בפלט מותאמת לשורה בדף התשובות לפי התא הראשון שלה, ולא לפי מקומה: שורה שנשברה או
נדבקה הייתה מזיזה את כל השאר. שורה בפלט היא שורה של הקורא, והתאים שלה הם Line.cells. כשכמה שורות
בפלט מתחילות באותו תא (למשל שם משתנה שמופיע לבד בשורה גם מחוץ לטבלה), נבחרת זו שהכי הרבה מהתאים
שלה זהים, ובתיקו הראשונה. כשאותו תא ראשון חוזר בכמה שורות של דף התשובות (במסמך האפיון "pdf_oxide טקסט"
פותח שורה בשתי טבלאות), כל שורה בפלט נספרת לשורה אחת לכל היותר: הזוגות עם הכי הרבה תאים זהים קודם,
ובתיקו לפי הסדר (_assign). שורת הכותרת (rows[0]) לא נמדדת: היא חוזרת בראש כל עמוד, והתא הראשון שלה
לא ייחודי.

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

from harness.html_structure import KINDS, HtmlBlock
from harness.textdiff import join_cells, normalize

TRUTH_SUFFIX = ".truth.json"
MIN_WHOLE_LENGTH = 4
EXCLUDED_FROM_WHOLE = frozenset({"כן", "לא", "-"})


class TruthFileError(ValueError):
    """קובץ דף התשובות לא במבנה הצפוי."""


@dataclass(frozen=True)
class TruthTable:
    section: str | None  # הכותרת האחרונה לפני הטבלה, אם יש
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]  # בלי שורת הכותרת


def source_stem(pdf: str) -> str:
    """השם של המקור של קובץ: השם בלי התוכנה שאחרי הקו התחתון האחרון (env-vars_weasyprint.pdf ← env-vars)."""
    stem = Path(pdf).stem
    return stem.rsplit("_", 1)[0] if "_" in stem else stem


def pdf_names(truth_path: Path, pdfs: Sequence[str]) -> list[str]:
    """הקבצים מתוך pdfs שדף התשובות שייך להם: <שם>.truth.json שייך לכל <שם>_<תוכנה>.pdf."""
    stem = truth_path.name[:-len(TRUTH_SUFFIX)]
    return [pdf for pdf in pdfs if "_" in Path(pdf).stem and source_stem(pdf) == stem]


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_blocks(path: Path) -> list[HtmlBlock]:
    """הבלוקים שבדף התשובות, לפי הסדר. זורקת TruthFileError עם הסיבה כשהמבנה לא תקין.

    הקובץ מגיע מחוץ לתהליך (נבנה בסקריפט ונשמר בריפו), ולכן כל שדה נבדק לפני השימוש: הטיפוס לפני
    כל השוואה או בדיקת שייכות, והתא הראשון של כל שורה, שעליו היישור נשען.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TruthFileError(f"{path.name}: לא JSON תקין ({exc.msg}, שורה {exc.lineno})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("blocks"), list) or not data["blocks"]:
        raise TruthFileError(f"{path.name}: חסרה רשימת blocks")
    blocks = []
    for number, block in enumerate(data["blocks"], 1):
        where = f"{path.name}, בלוק {number}"
        if not isinstance(block, dict):
            raise TruthFileError(f"{where}: לא אובייקט")
        kind = block.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise TruthFileError(f"{where}: kind אינו אחד מ-{sorted(KINDS)}")
        quote = block.get("quote", 0)
        if not _is_int(quote) or quote < 0:
            raise TruthFileError(f"{where}: quote אינו מספר שלם אי-שלילי")
        if kind == "table":
            blocks.append(HtmlBlock("table", quote=quote, rows=_table_rows(block.get("rows"), where)))
            continue
        text = block.get("text")
        if not isinstance(text, str):
            raise TruthFileError(f"{where}: text אינו טקסט")
        level = block.get("level", 0)
        if kind in ("heading", "item"):
            low, high = (1, 6) if kind == "heading" else (0, 100)
            if not _is_int(level) or not low <= level <= high:
                raise TruthFileError(f"{where}: level אינו מספר שלם בין {low} ל-{high}")
        blocks.append(HtmlBlock(kind, text, level if kind in ("heading", "item") else 0, quote))
    return blocks


def _table_rows(rows, where: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(rows, list) or not rows:
        raise TruthFileError(f"{where}: חסרה רשימת rows")
    for index, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(cell, str) for cell in row):
            raise TruthFileError(f"{where}, שורה {index}: לא רשימה של טקסטים")
    header = rows[0]
    if not header:
        raise TruthFileError(f"{where}: שורת הכותרת ריקה")
    for index, row in enumerate(rows[1:], 1):
        if len(row) != len(header):
            raise TruthFileError(f"{where}, שורה {index}: {len(row)} תאים במקום {len(header)}")
        if not normalize(row[0]):
            raise TruthFileError(f"{where}, שורה {index}: התא הראשון ריק, ואי אפשר ליישר לפיו")
    return tuple(tuple(row) for row in rows)


def load_truth(path: Path) -> list[TruthTable]:
    """הטבלאות שבדף התשובות (load_blocks), כל אחת עם הכותרת האחרונה לפניה. במסמך בלי טבלאות:
    רשימה ריקה, כי דף התשובות הוא של כל המבנה ומסמך בלי טבלאות נמדד במבנה בלבד."""
    tables = []
    section = None
    for block in load_blocks(path):
        if block.kind == "heading":
            section = block.text
        elif block.kind == "table":
            tables.append(TruthTable(section, block.rows[0], block.rows[1:]))
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
    truth_rows = [(table, tuple(normalize(cell) for cell in row)) for table in tables for row in table.rows]
    matched = _assign([truth for _, truth in truth_rows], rows_out)
    texts = [normalize(join_cells(row)) for row in rows_out]

    columns: dict[str, list[int]] = {}  # כותרת -> [תאים, זהים, נספרים לשלם, שלמים]
    for table in tables:
        for name in table.header:
            columns.setdefault(name, [0, 0, 0, 0])
    aligned = identical_rows = 0
    for (table, truth), best in zip(truth_rows, matched):
        same = _same_cells(best or (), truth)
        aligned += best is not None
        identical_rows += best is not None and len(best) == len(truth) and all(same)
        for name, cell, is_same in zip(table.header, truth, same):
            counts = columns[name]
            counts[0] += 1
            counts[1] += is_same
            if _counts_for_whole(cell):
                counts[2] += 1
                counts[3] += any(cell in text for text in texts)
    return TableScore(pdf, len(truth_rows), aligned, identical_rows,
                      tuple(ColumnScore(name, *counts) for name, counts in columns.items()))


def _assign(truth: Sequence[tuple[str, ...]], output: Sequence[tuple[str, ...]]) -> list[tuple[str, ...] | None]:
    """לכל שורה בדף התשובות: השורה בפלט שמותאמת לה (אותו תא ראשון), או None.

    לתא ראשון שמופיע בשורה אחת בדף התשובות: השורה בפלט עם הכי הרבה תאים זהים, ובתיקו הראשונה.
    לתא ראשון שחוזר בכמה שורות בדף התשובות: התאמה של אחד לאחד, מהזוג עם הכי הרבה תאים זהים, ובתיקו
    לפי הסדר בדף התשובות ואז בפלט. כך שורה אחת בפלט לא נספרת פעמיים."""
    by_first: dict[str, list[int]] = {}
    for index, row in enumerate(output):
        if row:
            by_first.setdefault(row[0], []).append(index)
    truth_by_first: dict[str, list[int]] = {}
    for index, row in enumerate(truth):
        truth_by_first.setdefault(row[0], []).append(index)
    matched: list[tuple[str, ...] | None] = [None] * len(truth)
    for first, truth_indices in truth_by_first.items():
        candidates = by_first.get(first, [])
        pairs = sorted(((-sum(_same_cells(output[o], truth[t])), t, o) for t in truth_indices for o in candidates))
        used_truth: set[int] = set()
        used_output: set[int] = set()
        for _, t, o in pairs:
            if t not in used_truth and o not in used_output:
                matched[t] = output[o]
                used_truth.add(t)
                used_output.add(o)
    return matched


def _same_cells(row: Sequence[str], truth: Sequence[str]) -> list[bool]:
    """לכל תא בדף התשובות: האם התא באותו מקום בשורה של הפלט זהה לו. תא שאין בפלט אינו זהה."""
    return [i < len(row) and row[i] == cell for i, cell in enumerate(truth)]
