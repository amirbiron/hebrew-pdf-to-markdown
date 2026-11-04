"""הפונקציה הציבורית של החבילה: מהעמודים שנקראו לתוצאה שלמה, ה-Markdown ולכל עמוד החלטה, סיבות והערות.

זה המסלול היחיד מהקריאה לתוצאה: convert_pages. מערך הבדיקה (harness/run.py) קורא לה ישירות, עם העמודים שהקורא
שלו הוציא, והשירות (web/) קורא ל-convert_document, שקוראת את המסמך ב-lines.read_document ואז ל-convert_pages. כך אין
שני מסלולים שיכולים להתפצל: מה שהדוח מודד הוא מה שהמשתמש מקבל. הקורא עצמו נשאר נפרד, כי מערך הבדיקה מחליף אותו
בקורא שבור בכוונה כדי להוכיח שהוא מסוגל להיכשל (tests/test_harness_can_fail.py).

הציון נבנה מה-Markdown ולא בנפרד ממנו: מה שירד ככותרת עליונה או תחתונה (Markdown.dropped) לא מגיע למשתמש, ולכן
גם לא נבדק בציר הסבירות (score.py).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from hebrew_pdf.lines import PageText, read_document
from hebrew_pdf.markdown import Markdown, build_markdown
from hebrew_pdf.score import PageScore, score_document


@dataclass(frozen=True)
class Conversion:
    pages: tuple[PageText, ...]  # מה שהקורא הוציא, עמוד לעמוד
    markdown: Markdown
    scores: tuple[PageScore, ...]  # לכל עמוד, לפי הסדר: החלטה, סיבות והערות


def convert_pages(pages: Sequence[PageText]) -> Conversion:
    """ה-Markdown והציון של מסמך שכבר נקרא (כל העמודים, לפי הסדר)."""
    built = build_markdown(pages)
    return Conversion(tuple(pages), built, tuple(score_document(pages, built.dropped)))


def convert_document(pdf) -> Conversion:
    """התוצאה של מסמך פתוח (pypdfium2.PdfDocument). הפתיחה, הסגירה וכל מגבלה על המסמך (גודל, מספר עמודים) הן של
    מי שקורא לפונקציה. PdfiumError שהקורא לא מטפל בו בעצמו (lines.page_rules ו-page_marks מדלגים על אובייקט בלי
    מיקום) עולה כמו שהוא."""
    return convert_pages(read_document(pdf))
