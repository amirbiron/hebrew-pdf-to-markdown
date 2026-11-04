"""בדיקות עקיפות: סימנים לסדר שבור, בלי טקסט נכון להשוואה.

הן לא אמת. 100% בהן אינו הוכחה שהפלט נכון (ראו CLAUDE.md).
"""

import re


FINAL_LETTERS = "ךםןףץ"
HEBREW = re.compile(r"[\u0590-\u05ff]")


def score_final_letters(text):
    """אחוז המילים (מבין אלה שיש בהן אות סופית) שהאות הסופית לא בתחילתן."""
    words = [w for w in re.findall(r"[א-ת]{2,}", text) if any(c in FINAL_LETTERS for c in w)]
    if not words:
        return None
    return round(100 * sum(w[0] not in FINAL_LETTERS for w in words) / len(words))


def score_punct_at_start(text):
    """אחוז השורות העבריות שמתחילות בסימן פיסוק — סימן לסדר שבור. נמוך = טוב."""
    lines = [l for l in text.splitlines() if counts_for_punct(l)]
    if not lines:
        return None
    return round(100 * sum(punct_at_start(l) for l in lines) / len(lines))


def counts_for_punct(line: str) -> bool:
    """שורה שנבדקת לפיסוק בתחילתה: יש בה עברית, והיא ארוכה מ-8 תווים."""
    return bool(HEBREW.search(line)) and len(line) > 8


def punct_at_start(line: str) -> bool:
    """שורה עברית (counts_for_punct) שמתחילה בסימן פיסוק. גם הציון של העמוד בודק כך (score.py)."""
    return counts_for_punct(line) and bool(re.match(r"^[.,:;!?]", line))
