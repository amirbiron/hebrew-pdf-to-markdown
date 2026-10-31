"""בדיקות עקיפות: סימנים לסדר שבור, בלי טקסט נכון להשוואה.

הן לא אמת. 100% בהן אינו הוכחה שהפלט נכון (ראו CLAUDE.md).
"""

import re

from hebrew_pdf.lines import HEBREW

FINAL_LETTERS = "ךםןףץ"


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
