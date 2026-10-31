"""
אב-טיפוס: ממיר PDF עברי לטקסט, שבונה כל שורה לפי מיקום האותיות על הדף.

הרעיון: לא סומכים על הסדר שהקוראים הקיימים מחזירים. לוקחים מ-pypdfium2 כל אות
עם המיקום שלה וקו הבסיס שלה, מקבצים אותיות לשורות לפי קו הבסיס, ובכל שורה שיש בה
עברית מסדרים מימין לשמאל לפי המיקום. רצפים של אנגלית ומספרים הופכים בחזרה
לשמאל-לימין.

תוצאות על 12 קבצי הבדיקה (בדיקות עקיפות, לא אמת מתויגת):
עברית 100%, אנגלית 100%, ואפס שורות עבריות שמתחילות בסימן פיסוק, בכל הקבצים.
0.01 עד 0.04 שניות לעמוד.

כשלים ידועים שעוד לא מטופלים כאן:
- תאים צמודים בשורה אחת נדבקים ("2∞+409")
- סוגריים הפוכים ("לצ׳טבוט) לפני דיאגרמה)")
- ריווח: כותרת עם ריווח אותיות ("ה צ ע ת מ ח י ר"), רווחים במקום לא נכון ("ומהא יתך")
- שורה רק באנגלית בתוך מסמך עברי ("OSMentor" במקום "MentorOS")
- פיסוק בקצה של רצף אנגלי ("/https://...")
- טבלאות: סדר העמודות מתהפך, כוכביות נצמדות לצד הלא נכון. צריך נתיב נפרד.

התקנה: pip install pypdfium2   (רישיון BSD / Apache 2.0)

שימוש:
    python hebrew_pdf_prototype.py FILE.pdf            # מדפיס את הטקסט של כל העמודים
    python hebrew_pdf_prototype.py --score DIR          # ציונים לכל קובץ PDF בתיקייה
"""

import ctypes
import re
import sys
import time
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

HEBREW = re.compile(r"[֐-׿]")
# רצף של אנגלית / מספרים, כולל פיסוק פנימי ומילים נוספות באנגלית אחרי רווח
LTR_RUN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9.,:/\-_@%+#&']*[A-Za-z0-9])?(?: [A-Za-z][A-Za-z0-9.\-]*)*"
)
FINAL_LETTERS = "ךםןףץ"
BASELINE_TOLERANCE = 2.0  # נקודות PDF: אותיות שקו הבסיס שלהן קרוב עד כדי זה באותה שורה


def page_chars(page):
    """כל האותיות בעמוד: (תו, מרכז אופקי, קו בסיס).

    חשוב: קו הבסיס ולא תחתית האות. אותיות שיורדות מתחת לשורה (ק ך ן ף ץ)
    נופלות לשורה אחרת אם מקבצים לפי תחתית התיבה.
    """
    textpage = page.get_textpage()
    x = ctypes.c_double()
    y = ctypes.c_double()
    chars = []
    for i in range(textpage.count_chars()):
        ch = textpage.get_text_range(i, 1)
        if not ch or ch in "\r\n":
            continue
        left, _bottom, right, _top = textpage.get_charbox(i)
        pdfium_raw.FPDFText_GetCharOrigin(textpage, i, x, y)
        chars.append((ch, (left + right) / 2, y.value))
    return chars


def group_rows(chars):
    """קיבוץ אותיות לשורות לפי קו הבסיס, מלמעלה למטה (ב-PDF ציר y עולה כלפי מעלה)."""
    rows = []
    for c in sorted(chars, key=lambda c: -c[2]):
        if rows and abs(rows[-1][0][2] - c[2]) <= BASELINE_TOLERANCE:
            rows[-1].append(c)
        else:
            rows.append([c])
    return rows


def build_line(row):
    """שורה עם עברית: מימין לשמאל, ואז רצפי אנגלית/מספרים בחזרה לשמאל-לימין."""
    if any(HEBREW.match(c[0]) for c in row):
        text = "".join(c[0] for c in sorted(row, key=lambda c: -c[1]))
        text = LTR_RUN.sub(lambda m: m.group(0)[::-1], text)
    else:
        text = "".join(c[0] for c in sorted(row, key=lambda c: c[1]))
    return re.sub(r" {2,}", "  ", text).strip()


def page_text(page):
    return "\n".join(build_line(r) for r in group_rows(page_chars(page)))


# ---------- בדיקות עקיפות ----------

def score_final_letters(text):
    """אחוז המילים (מבין אלה שיש בהן אות סופית) שהאות הסופית לא בתחילתן."""
    words = [w for w in re.findall(r"[א-ת]{2,}", text) if any(c in FINAL_LETTERS for c in w)]
    if not words:
        return None
    return round(100 * sum(w[0] not in FINAL_LETTERS for w in words) / len(words))


def score_punct_at_start(text):
    """אחוז השורות העבריות שמתחילות בסימן פיסוק — סימן לסדר שבור. נמוך = טוב."""
    lines = [l for l in text.splitlines() if HEBREW.search(l) and len(l) > 8]
    if not lines:
        return None
    return round(100 * sum(bool(re.match(r"^[.,:;!?]", l)) for l in lines) / len(lines))


def main(argv):
    if len(argv) == 3 and argv[1] == "--score":
        print("file | final-letters % | punct-at-line-start % | sec/page")
        for path in sorted(Path(argv[2]).glob("*.pdf")):
            pdf = pdfium.PdfDocument(str(path))
            t0 = time.time()
            text = "\n".join(page_text(p) for p in pdf)
            per_page = (time.time() - t0) / max(len(pdf), 1)
            print(f"{path.name[:30]} | {score_final_letters(text)} | {score_punct_at_start(text)} | {per_page:.3f}")
    elif len(argv) == 2:
        pdf = pdfium.PdfDocument(argv[1])
        for i, page in enumerate(pdf, 1):
            print(f"\n<!-- עמוד {i} -->\n")
            print(page_text(page))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
