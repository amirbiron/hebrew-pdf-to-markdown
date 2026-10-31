"""קיבוץ אותיות לשורות, ובניית הטקסט של כל שורה."""

from dataclasses import dataclass

from hebrew_pdf.chars import Char, page_chars
from hebrew_pdf.logical_order import document_rtl, to_logical
from hebrew_pdf.spacing import SpaceCounts, space_by_gaps

BASELINE_TOLERANCE = 2.0  # נקודות PDF: אותיות שקו הבסיס שלהן קרוב עד כדי זה באותה שורה


@dataclass(frozen=True)
class Line:
    text: str  # הסדר הלוגי: הסדר שבו קוראים את השורה
    # התווים כמו שהם מופיעים בעמוד, משמאל לימין, עם הרווחים לפי הפערים ולא תווי הרווח
    # שבקובץ (spacing.py). לבדיקת התצוגה
    visual: str
    # כיוון הפסקה שבה השורה נקראה (logical_order.to_logical). בדיקת התצוגה מציגה את
    # הטקסט באותו כיוון, ולא מחשבת כיוון משלה
    rtl: bool
    # יותר מקריאה אחת מוצגת בדיוק כמו השורה בעמוד, וברירת המחדל הכריעה (logical_order.py)
    ambiguous: bool = False
    # כמה הרווחים לפי הפער שונים מתווי הרווח שבקובץ (spacing.py). build_line ממלא תמיד
    spacing: SpaceCounts = SpaceCounts()


@dataclass(frozen=True)
class PageText:
    lines: list[Line]
    skipped_chars: int  # אותיות שדולגו כי אין להן מיקום (ראו chars.page_chars)
    unknown_brackets: int = 0  # סוגריים שהצורה שלהם לא נקבעה מהציור (bracket_shapes.py)

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


def group_rows(chars: list[Char]) -> list[list[Char]]:
    """קיבוץ אותיות לשורות לפי קו הבסיס, מלמעלה למטה (ב-PDF ציר y עולה כלפי מעלה)."""
    rows: list[list[Char]] = []
    for c in sorted(chars, key=lambda c: -c.baseline):
        if rows and abs(rows[-1][0].baseline - c.baseline) <= BASELINE_TOLERANCE:
            rows[-1].append(c)
        else:
            rows.append([c])
    return rows


def build_line(row: list[Char], rtl_document: bool) -> Line:
    """השורה בסדר הלוגי, מהאותיות שלה לפי מיקומן בעמוד (ראו logical_order.py).

    rtl_document: כיוון הפסקה של המסמך (logical_order.document_rtl).
    """
    # הרווחים לפי הפערים בעמוד ולא לפי הקובץ (spacing.py): רווח אחד בכל פער בין מילים,
    # ואף פעם לא בקצה השורה, ולכן אין רצפים לאחד ואין מה להוריד מהקצוות
    spaced = space_by_gaps(sorted(row, key=lambda c: c.x))
    reading = to_logical(spaced.chars, lambda c: c.text, rtl_document)
    return Line("".join(reading.texts), "".join(c.text for c in spaced.chars), reading.rtl, reading.ambiguous,
                spaced.counts)


def read_document(pdf) -> list[PageText]:
    """הטקסט של כל עמוד במסמך, לפי סדר העמודים.

    כיוון הפסקה נקבע פעם אחת, מכל האותיות במסמך (logical_order.document_rtl), ולכן
    קודם נקראות האותיות של כל העמודים ורק אחר כך נבנות השורות.
    """
    pages = [page_chars(page) for page in pdf]
    rtl = document_rtl(c.text for found in pages for c in found.chars)
    return [PageText([build_line(row, rtl) for row in group_rows(found.chars)], found.skipped, found.unknown_brackets)
            for found in pages]
