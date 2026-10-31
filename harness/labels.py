"""קריאת טבלת התיוג (testset/labels.md).

הקובץ נערך ביד, מטאבלט, ולכן הוא קלט חיצוני: כל שורה נבדקת, ושורה פגומה לא
נבלעת. היא חוזרת כ-LabelProblem עם מספר השורה בקובץ והסיבה, והדוח מציג אותה.
בעיה בקובץ כולו (אין טבלה, כותרת לא נכונה) זורקת LabelsFileError.

כללי הכתיבה בתאים הם של GitHub Flavored Markdown, כדי שמה שרואים בתצוגה של הקובץ
הוא מה שהקוד קורא: לוכסן הפוך לפני סימן פיסוק של ASCII מבטל את משמעותו (\\| הוא
התו |, ו-\\\\ הוא לוכסן הפוך אחד). | בלי לוכסן לפניו הוא גבול בין תאים.
"""

import re
import string
from dataclasses import dataclass

COLUMNS = ("מספר", "קובץ", "עמוד", "מה הכלי הוציא", "הטקסט הנכון", "סטטוס")

STATUS_PENDING = "ממתין לאישור"
STATUS_APPROVED = "מאושר"
STATUS_UNCLEAR = "לא ברור"
STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_UNCLEAR)

_ASCII_PUNCTUATION = frozenset(string.punctuation)
_DIGITS = re.compile("[0-9]+")
_DELIMITER_CELL = re.compile(":?-+:?")


class LabelsFileError(ValueError):
    """הקובץ כולו לא קריא כטבלת תיוג."""


@dataclass(frozen=True)
class Label:
    number: int
    file: str
    page: int
    tool_output: str
    expected: str
    status: str
    source_line: int  # מספר השורה ב-labels.md, להודעות שגיאה


@dataclass(frozen=True)
class LabelProblem:
    source_line: int
    message: str


def split_row(line: str) -> list[str]:
    """שורת טבלה לתאים, אחרי ביטול ה-escapes. הרווחים בקצוות כל תא יורדים.

    | בתחילת השורה חובה; | בסוף השורה לא חובה. לוכסן הפוך לפני תו שאינו פיסוק של
    ASCII נשאר כמו שהוא (כמו ב-GFM: "C:\\path" נשאר "C:\\path").
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        raise ValueError("שורת טבלה חייבת להתחיל ב-|")
    cells = []
    current = []
    ended_with_pipe = False
    i = 1
    while i < len(stripped):
        char = stripped[i]
        ended_with_pipe = False
        if char == "\\" and i + 1 < len(stripped) and stripped[i + 1] in _ASCII_PUNCTUATION:
            current.append(stripped[i + 1])
            i += 2
            continue
        if char == "|":
            cells.append("".join(current))
            current = []
            ended_with_pipe = True
        else:
            current.append(char)
        i += 1
    if not ended_with_pipe:
        cells.append("".join(current))
    return [cell.strip() for cell in cells]


def escape_cell(text: str) -> str:
    """טקסט לתא בטבלה: \\ ו-| מקבלים לוכסן הפוך. הפעולה ההפוכה של split_row."""
    return text.replace("\\", "\\\\").replace("|", "\\|")


def _is_delimiter_row(cells: list[str]) -> bool:
    return bool(cells) and all(_DELIMITER_CELL.fullmatch(cell) for cell in cells)


def parse_labels(text: str, known_files: frozenset[str]) -> tuple[list[Label], list[LabelProblem]]:
    """כל שורות התיוג התקינות, וכל הבעיות בשורות שאינן תקינות.

    known_files: שמות קובצי ה-PDF שבסט. קובץ שלא מופיע בהם הוא בעיה בשורה.
    טווח העמודים נבדק אצל מי שקורא את ה-PDF (harness/run.py), כי רק הוא יודע כמה
    עמודים יש בקובץ.
    """
    lines = text.split("\n")
    header_index = None
    for index, line in enumerate(lines):
        if line.strip().startswith("|") and tuple(split_row(line)) == COLUMNS:
            header_index = index
            break
    if header_index is None:
        raise LabelsFileError("לא נמצאה טבלה עם הכותרת: " + " | ".join(COLUMNS))
    delimiter_index = header_index + 1
    if delimiter_index >= len(lines) or not lines[delimiter_index].strip().startswith("|") \
            or not _is_delimiter_row(split_row(lines[delimiter_index])):
        raise LabelsFileError(f"שורה {delimiter_index + 1}: אחרי הכותרת חסרה שורת ההפרדה (|---|---|...)")
    # לפי GFM, כשמספר התאים בשורת ההפרדה שונה מהכותרת זו לא טבלה בכלל, ו-GitHub מציג את
    # הבלוק כפסקה רגילה. מקור: https://github.github.com/gfm/#tables-extension- (דוגמה 203)
    delimiter_cells = len(split_row(lines[delimiter_index]))
    if delimiter_cells != len(COLUMNS):
        raise LabelsFileError(
            f"שורה {delimiter_index + 1}: בשורת ההפרדה {delimiter_cells} תאים במקום {len(COLUMNS)}")

    labels: list[Label] = []
    problems: list[LabelProblem] = []
    seen_numbers: dict[int, int] = {}
    for index in range(header_index + 2, len(lines)):
        line = lines[index]
        if not line.strip().startswith("|"):
            break  # סוף הטבלה
        source_line = index + 1
        label, problem = _parse_row(split_row(line), source_line, known_files)
        if problem is not None:
            problems.append(problem)
            continue
        if label.number in seen_numbers:
            problems.append(LabelProblem(
                source_line, f"המספר {label.number} כבר מופיע בשורה {seen_numbers[label.number]}"))
            continue
        seen_numbers[label.number] = source_line
        labels.append(label)
    return labels, problems


def _parse_row(cells: list[str], source_line: int, known_files: frozenset[str]):
    if len(cells) != len(COLUMNS):
        return None, LabelProblem(
            source_line, f"{len(cells)} תאים במקום {len(COLUMNS)} (אולי | בתוך טקסט בלי \\ לפניו?)")
    number_cell, file_cell, page_cell, tool_output, expected, status = cells
    if not _DIGITS.fullmatch(number_cell) or int(number_cell) < 1:
        return None, LabelProblem(source_line, f"מספר לא תקין: '{number_cell}'")
    if file_cell not in known_files:
        return None, LabelProblem(source_line, f"קובץ לא מוכר בסט הבדיקה: '{file_cell}'")
    if not _DIGITS.fullmatch(page_cell) or int(page_cell) < 1:
        return None, LabelProblem(source_line, f"עמוד לא תקין: '{page_cell}'")
    if not expected:
        return None, LabelProblem(source_line, "הטקסט הנכון ריק")
    if status not in STATUSES:
        return None, LabelProblem(
            source_line, f"סטטוס לא מוכר: '{status}'. הערכים האפשריים: " + ", ".join(STATUSES))
    return Label(int(number_cell), file_cell, int(page_cell), tool_output, expected, status, source_line), None
