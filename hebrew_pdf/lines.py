"""קיבוץ אותיות לשורות, ובניית הטקסט של כל שורה."""

import re

from hebrew_pdf.chars import page_chars

HEBREW = re.compile(r"[֐-׿]")
# רצף של אנגלית / מספרים, כולל פיסוק פנימי ומילים נוספות באנגלית אחרי רווח
LTR_RUN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9.,:/\-_@%+#&']*[A-Za-z0-9])?(?: [A-Za-z][A-Za-z0-9.\-]*)*"
)
BASELINE_TOLERANCE = 2.0  # נקודות PDF: אותיות שקו הבסיס שלהן קרוב עד כדי זה באותה שורה


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
