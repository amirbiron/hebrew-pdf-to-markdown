"""קיבוץ אותיות לשורות, ובניית הטקסט של כל שורה."""

import re
from dataclasses import dataclass

from hebrew_pdf.chars import Char, page_chars
from hebrew_pdf.logical_order import to_logical

BASELINE_TOLERANCE = 2.0  # נקודות PDF: אותיות שקו הבסיס שלהן קרוב עד כדי זה באותה שורה


@dataclass(frozen=True)
class Line:
    text: str  # הסדר הלוגי: הסדר שבו קוראים את השורה
    visual: str  # האותיות כמו שהן מופיעות בעמוד, משמאל לימין (לבדיקת התצוגה)
    # יותר מקריאה אחת מוצגת בדיוק כמו השורה בעמוד, וברירת המחדל הכריעה (logical_order.py)
    ambiguous: bool = False


@dataclass(frozen=True)
class PageText:
    lines: list[Line]
    skipped_chars: int  # אותיות שדולגו כי אין להן מיקום (ראו chars.page_chars)
    unknown_brackets: int = 0  # סוגריים שהצורה שלהם לא נקבעה מהציור (bracket_shapes.py)

    @property
    def ambiguous_lines(self) -> int:
        return sum(line.ambiguous for line in self.lines)

    @property
    def text(self) -> str:
        """השורות של העמוד, מופרדות ב-"\\n"."""
        return "\n".join(line.text for line in self.lines)


def group_rows(chars: list[Char]) -> list[list[Char]]:
    """קיבוץ אותיות לשורות לפי קו הבסיס, מלמעלה למטה (ב-PDF ציר y עולה כלפי מעלה)."""
    rows: list[list[Char]] = []
    for c in sorted(chars, key=lambda c: -c.baseline):
        if rows and abs(rows[-1][0].baseline - c.baseline) <= BASELINE_TOLERANCE:
            rows[-1].append(c)
        else:
            rows.append([c])
    return rows


def build_line(row: list[Char]) -> Line:
    """השורה בסדר הלוגי, מהאותיות שלה לפי מיקומן בעמוד (ראו logical_order.py)."""
    visual = sorted(row, key=lambda c: c.x)
    reading = to_logical(visual, lambda c: c.text)
    # רק התו רווח יורד מהקצוות, כמו שרק הוא מאוחד. strip() בלי ארגומנט מוחק גם את
    # U+001C עד U+001F, שבקבצים הם אותיות שמופו בטעות (ה-? של "ומה איתך?" בפלאייר).
    text = re.sub(r" {2,}", "  ", "".join(reading.texts)).strip(" ")
    return Line(text, "".join(c.text for c in visual), reading.ambiguous)


def read_page(page) -> PageText:
    found = page_chars(page)
    return PageText([build_line(r) for r in group_rows(found.chars)], found.skipped, found.unknown_brackets)
