"""קריאת טבלת התיוג (testset/labels.md).

הקובץ נערך ביד, מטאבלט, ולכן הוא קלט חיצוני: כל שורה נבדקת, ושורה פגומה לא
נבלעת. היא חוזרת כ-LabelProblem עם מספר השורה בקובץ והסיבה, והדוח מציג אותה.
בעיה בקובץ כולו (אין טבלה, כותרת לא נכונה) זורקת LabelsFileError.

כללי הכתיבה בתאים הם של GitHub Flavored Markdown, כדי שמה שרואים בתצוגה של הקובץ
הוא מה שהקוד קורא: לוכסן הפוך לפני סימן פיסוק של ASCII מבטל את משמעותו (\\| הוא
התו |, ו-\\\\ הוא לוכסן הפוך אחד). | בלי לוכסן לפניו הוא גבול בין תאים.

גבול בין תאים בתוך "הטקסט הנכון" (שורת טבלה, או תיבות זו לצד זו) הוא <br>: תג HTML
שבתוך תא בטבלה של GitHub מוצג כמעבר שורה, כך שכל תא מופיע בשורה משלו. ב-GFM תוכן התא
מפוענח כ-inlines ("Each row consists of cells containing arbitrary text, in which [inlines]
are parsed", https://github.github.com/gfm/#tables-extension-), ותג HTML הוא inline
("Text between < and > that looks like an HTML tag is parsed as a raw HTML tag",
https://github.github.com/gfm/#raw-html). GitHub משאיר את br אחרי הסינון (html-pipeline,
lib/html_pipeline/sanitization_filter.rb, ברשימת האלמנטים המותרים). <br> לא יכול להיות טקסט
של מסמך, כי טקסט "<br>" נכתב \\<br> (הלוכסן ההפוך מבטל את משמעות ה-<), ובתצוגה הוא נראה
כטקסט. לכן אין התנגשות עם התו | עצמו, שנכתב \\| ונשאר חלק מהטקסט.

גם גבול הטבלה הוא של GFM: הטבלה נגמרת בשורה הריקה הראשונה או בתחילת מבנה אחר
(כותרת, ציטוט, רשימה, בלוק קוד), וכל שורה עד אז היא שורה בטבלה, גם בלי | בהתחלה.
מקור: https://github.github.com/gfm/#tables-extension- (דוגמאות 199, 201, 202).
שורת תיוג שנמצאת אחרי סוף הטבלה לא נקראת, אבל מדווחת, כדי שלא תיעלם בשקט.
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
# תחילת מבנה אחר שקוטעת טבלה ב-GFM: כותרת, ציטוט, בלוק קוד, רשימה, HTML, קו מפריד
_BLOCK_START = re.compile(
    r" {0,3}(?:#{1,6}(?:[ \t]|$)|>|```|~~~|[-*+](?:[ \t]|$)|[0-9]{1,9}[.)](?:[ \t]|$)|<"
    r"|(?:\*[ \t]*){3,}$|(?:-[ \t]*){3,}$|(?:_[ \t]*){3,}$)")
# גבול בין תאים ב"הטקסט הנכון": תג br, כמו ש-GFM מזהה תג פתיחה (https://github.github.com/gfm/#open-tag):
# "<", שם התג, אולי תכונות, אולי רווח, אולי "/", ו-">". שמות תגים ב-HTML לא תלויים באותיות
# גדולות, ולכן גם <BR>. כל אלה מוצגים ב-GitHub כמעבר שורה: <br>, <br/>, <br />, <br class="x">
_CELL_BREAK = re.compile(r"<br(?:[ \t][^<>]*)?/?>", re.IGNORECASE)


class LabelsFileError(ValueError):
    """הקובץ כולו לא קריא כטבלת תיוג."""


@dataclass(frozen=True)
class Label:
    number: int
    file: str
    page: int
    tool_output: str
    # הטקסט הנכון, כתאים לפי סדר הקריאה (מימין לשמאל). שורה רגילה היא תא אחד. תא ריק נשאר
    # ריק. להשוואה כמחרוזת אחת: harness.textdiff.join_cells
    expected: tuple[str, ...]
    status: str
    source_line: int  # מספר השורה ב-labels.md, להודעות שגיאה


@dataclass(frozen=True)
class LabelProblem:
    source_line: int
    message: str


def _split_raw(line: str) -> list[str]:
    """שורת טבלה לתאים, בלי לבטל את ה-escapes ובלי להוריד רווחים: \\| נשאר \\| בתוך התא.

    | בתחילת השורה ובסופה לא חובה, כמו ב-GFM. | בלי לוכסן הפוך לפניו הוא גבול בין תאים.
    """
    stripped = line.strip()
    cells = []
    current = []
    ended_with_pipe = False
    i = 1 if stripped.startswith("|") else 0
    while i < len(stripped):
        char = stripped[i]
        ended_with_pipe = False
        if char == "\\" and i + 1 < len(stripped) and stripped[i + 1] in _ASCII_PUNCTUATION:
            current.append(stripped[i:i + 2])
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
    return cells


def _unescape_parts(raw: str, boundary: re.Pattern | None = None) -> list[str]:
    """ביטול ה-escapes של GFM: לוכסן הפוך לפני סימן פיסוק של ASCII הופך אותו לתו רגיל.
    לוכסן הפוך לפני תו שאינו פיסוק של ASCII נשאר כמו שהוא (כמו ב-GFM: "C:\\path" נשאר).

    boundary: כשנמסר, הטקסט מתפצל בכל מופע שלו שאינו חלק מ-escape. הסריקה משמאל לימין,
    ולכן \\<br> הוא "<br>" כטקסט, ו-\\\\<br> הוא לוכסן הפוך ואחריו גבול, כמו ש-GitHub מציג.
    """
    parts: list[str] = []
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw) and raw[i + 1] in _ASCII_PUNCTUATION:
            out.append(raw[i + 1])
            i += 2
            continue
        found = boundary.match(raw, i) if boundary is not None else None
        if found:
            parts.append("".join(out))
            out = []
            i = found.end()
            continue
        out.append(raw[i])
        i += 1
    parts.append("".join(out))
    return parts


def split_row(line: str) -> list[str]:
    """שורת טבלה לתאים, אחרי ביטול ה-escapes. הרווחים בקצוות כל תא יורדים."""
    return [_unescape_parts(cell)[0].strip() for cell in _split_raw(line)]


def split_cells(raw: str) -> tuple[str, ...]:
    """תא של "הטקסט הנכון", כמו שהוא כתוב בקובץ (לפני ביטול ה-escapes), לתאים של השורה
    שבעמוד: גבול בכל <br> (_CELL_BREAK). הרווחים בקצוות כל תא יורדים."""
    return tuple(part.strip() for part in _unescape_parts(raw, _CELL_BREAK))


def _looks_like_label_row(line: str) -> bool:
    cells = split_row(line)
    return len(cells) == len(COLUMNS) and bool(_DIGITS.fullmatch(cells[0]))


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
        if "|" in line and tuple(split_row(line)) == COLUMNS:
            header_index = index
            break
    if header_index is None:
        raise LabelsFileError("לא נמצאה טבלה עם הכותרת: " + " | ".join(COLUMNS))
    delimiter_index = header_index + 1
    if delimiter_index >= len(lines) or not _is_delimiter_row(split_row(lines[delimiter_index])):
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
    table_end = len(lines)
    for index in range(header_index + 2, len(lines)):
        line = lines[index]
        if not line.strip() or _BLOCK_START.match(line):
            table_end = index  # סוף הטבלה, כמו ב-GFM
            break
        source_line = index + 1
        label, problem = _parse_row(_split_raw(line), source_line, known_files)
        if problem is not None:
            problems.append(problem)
            continue
        if label.number in seen_numbers:
            problems.append(LabelProblem(
                source_line, f"המספר {label.number} כבר מופיע בשורה {seen_numbers[label.number]}"))
            continue
        seen_numbers[label.number] = source_line
        labels.append(label)

    for index in range(table_end, len(lines)):
        if _looks_like_label_row(lines[index]):
            problems.append(LabelProblem(
                index + 1, "שורת תיוג מחוץ לטבלה: שורה ריקה או טקסט אחר מפרידים בינה לבין הטבלה, "
                           "ולכן גם GitHub לא מציג אותה בטבלה. היא לא נקראה"))
    return labels, problems


def _parse_row(raw_cells: list[str], source_line: int, known_files: frozenset[str]):
    if len(raw_cells) != len(COLUMNS):
        return None, LabelProblem(
            source_line, f"{len(raw_cells)} תאים במקום {len(COLUMNS)} (אולי | בתוך טקסט בלי \\ לפניו?)")
    number_cell, file_cell, page_cell, tool_output, _, status = (_unescape_parts(cell)[0].strip() for cell in raw_cells)
    expected = split_cells(raw_cells[4])
    if not _DIGITS.fullmatch(number_cell) or int(number_cell) < 1:
        return None, LabelProblem(source_line, f"מספר לא תקין: '{number_cell}'")
    if file_cell not in known_files:
        return None, LabelProblem(source_line, f"קובץ לא מוכר בסט הבדיקה: '{file_cell}'")
    if not _DIGITS.fullmatch(page_cell) or int(page_cell) < 1:
        return None, LabelProblem(source_line, f"עמוד לא תקין: '{page_cell}'")
    if not any(expected):
        return None, LabelProblem(source_line, "הטקסט הנכון ריק")
    if status not in STATUSES:
        return None, LabelProblem(
            source_line, f"סטטוס לא מוכר: '{status}'. הערכים האפשריים: " + ", ".join(STATUSES))
    return Label(int(number_cell), file_cell, int(page_cell), tool_output, expected, status, source_line), None
