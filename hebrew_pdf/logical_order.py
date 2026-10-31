"""מסדר ויזואלי לסדר לוגי, לפי אלגוריתם הכיוון של Unicode (UAX #9).

הקלט הוא האותיות של שורה אחת בסדר שבו הן מופיעות בעמוד, משמאל לימין (להלן V).
הפלט הוא הסדר הלוגי, כלומר הסדר שבו קוראים את השורה. ההגדרה של "נכון":

    פלט נכון הוא פלט שאם מציגים אותו בפסקה עברית, הוא נראה בדיוק כמו השורה בעמוד.

אלגוריתם התצוגה (UAX #9) לוקח טקסט לוגי, נותן לכל תו "רמה" (1 = מימין לשמאל,
2 = משמאל לימין בתוך פסקה עברית), ומסדר: הופך כל רצף ברמה 2, ואז את כל השורה
(כלל L2). הקובץ הזה עושה את הדרך ההפוכה, בשלושה שלבים:

1. סוג לכל תו לפי Unicode: עברית (R), לטינית (L), ספרה (EN), מפריד בתוך מספר
   (CS, ES), סימן שצמוד למספר כמו % (ET), וניטרלי (רווח, סוגריים, חץ, מקף ארוך).
   כללי UAX #9 קובעים לאיזה כיוון שייך כל תו חלש או ניטרלי, ומזה הרמה שלו (I2).
2. ההיפוך של L2: קוראים את V מימין לשמאל, וכל רצף ברמה 2 נשאר משמאל לימין.
3. אימות: מציגים את התוצאה באלגוריתם התצוגה עצמו (display_order), ובודקים שיוצא V.

למה צריך אימות. הכללים נכתבו לטקסט לוגי, ורובם לא תלויים בכיוון הקריאה. כלל אחד
כן: W7 ("מספר שלפניו, בסדר הלוגי, מילה באנגלית, שייך לה"). מספר שבעמוד צמוד, דרך
רווחים או סימנים, למילה באנגלית שמשמאלו, יכול להיות המשך שלה ("Python 3.12",
"IAS 34") או פריט נפרד שבא לפניה בקריאה מימין לשמאל ("(360dialog / Twilio)",
"1. Onboarding"). לכל מספר כזה נבדקות שתי הקריאות, ונשארות רק אלה שהתצוגה שלהן
היא V. מבין הקריאות שנשארו:
- קודם כל טיפוגרפיה: סימן פיסוק שלפניו רווח ושצמוד למילה שאחריו (" .1",
  " :Database") הוא סימן שהקריאה הפוכה.
- ואם עדיין יש יותר מאחת, ברירת המחדל: המספר שייך למילה האנגלית שמשמאלו (כלל W7
  כשקוראים את V משמאל לימין). השורה מסומנת אז "דו-משמעית" (Line.ambiguous):
  התווים לבדם לא מכריעים. דוגמה מהסט: "1 Onboarding" ו-"Onboarding 1" (שורה 9)
  מוצגים זהה לגמרי.

מקור הכללים: https://www.unicode.org/reports/tr9/ (גרסה 52, Unicode 18.0.0).

מה לא ממומש, ולמה:
- L4 (שיקוף): התו של הסוגר נשאר כמו שהוא בקובץ. בקבצים התו הזה לא אמין: יש יוצרים
  ששומרים את הצורה שנראית, יש ששומרים את התו הלוגי, ויש ששומרים את שני הצדדים של
  אותו זוג כאותו תו.
- X1-X10 (הטבעות ובידודים מפורשים): אין תווים כאלה בסט הבדיקה, ואין להם מיקום
  משלהם בעמוד. כל השורה היא פסקה אחת ברמה 1 בלי הטבעות, ולכן sos ו-eos הם R (X10).
- זוגות סוגריים (BD16) רק עבור ( ) [ ] { }, לפי BidiBrackets.txt (גרסה 18.0.0:
  "0028; 0029; o", "005B; 005D; o", "007B; 007D; o"). בקובץ יש 65 זוגות; האחרים
  (למשל 〈 〉) נפתרים כאן כמו כל ניטרלי.
- ב-N0, הכלל על NSM שבא מיד אחרי סוגר: בסט יש שני תווי NSM בלבד, ושניהם אחרי אימוג'י.
"""

import itertools
import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

RTL_LEVEL = 1  # רמת הפסקה העברית
LTR_LEVEL = 2  # אנגלית ומספרים בתוך פסקה עברית (I2)

_NEUTRAL = frozenset({"ON", "WS", "S"})
# BidiBrackets.txt: הסוגר הפותח והסוגר הסוגר שלו
_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}
_CLOSING = frozenset(_BRACKET_PAIRS.values())
_BD16_STACK = 63  # BD16: "Create a fixed-size stack for exactly 63 elements"
_PUNCTUATION = frozenset(".,:;!?")
# כמה מספרים דו-משמעיים בשורה נבדקים בכל הצירופים (2^6 = 64 קריאות לכל היותר).
# מעבר לזה נבדקות רק קריאות שהופכות עד שני מספרים. בסט הבדיקה המקסימום הוא 4.
_FULL_SEARCH_LIMIT = 6


def bidi_class(text: str) -> str:
    """הסוג של התו לפי Unicode (Bidi_Class), מהתו הראשון של הטקסט.

    כמה סוגים מאוחדים, כי בתוך שורה אחת בעמוד הם מתנהגים כמו סוג אחר:
    - B (מפריד פסקאות) בתוך שורה הוא לא סוף פסקה, כי השורה היא שורה אחת בעמוד.
      בסט הבדיקה אלה תווי בקרה שהקובץ מיפה אליהם אותיות בטעות (GPS בפלאייר).
      הוא מטופל כמו S: מפריד שחוזר לרמת הפסקה (L1).
    - BN (תווים בלתי נראים, כמו U+0007): UAX #9 מסיר אותם (X9); כאן הם ניטרליים.
    - תו ש-unicodedata לא מכיר (מחרוזת ריקה): ניטרלי. זו בחירה שלנו, לא של התקן.
    """
    if not text:
        return "ON"
    kind = unicodedata.bidirectional(text[0])
    if kind == "B":
        return "S"
    if kind in ("BN", ""):
        return "ON"
    return kind


def is_rtl(kinds: Sequence[str]) -> bool:
    """האם השורה עברית: יש בה תו חזק מימין לשמאל (R או AL).

    שורה בלי עברית בכלל נשארת משמאל לימין, כמו באב-טיפוס. הכיוון של שורה כזו
    במסמך עברי הוא החלטה פתוחה במסמך האפיון, ולא נקבע כאן.
    """
    return any(kind in ("R", "AL") for kind in kinds)


# ---------- הכללים עצמם, על רצף טיפוסים בסדר נתון ----------

def _strong_before(t: list[str], i: int, strong: tuple[str, ...]) -> str:
    """W2, W7, N0: "Search backward ... until the first strong type ... or sos"."""
    for j in range(i - 1, -1, -1):
        if t[j] in strong:
            return t[j]
    return "R"  # sos של פסקה ברמה 1 בלי הטבעות (X10)


def _weak_rules(kinds: Sequence[str]) -> list[str]:
    """W1-W6, על הרצף בסדר שבו הוא נמסר. W7 נפרד, כי רק הוא תלוי בכיוון הקריאה."""
    t = list(kinds)
    n = len(t)
    # W1: NSM מקבל את הסוג של התו הקודם, או sos בתחילת השורה
    for i in range(n):
        if t[i] == "NSM":
            t[i] = t[i - 1] if i > 0 else "R"
    # W2: EN אחרי AL הוא AN
    for i in range(n):
        if t[i] == "EN" and _strong_before(t, i, ("R", "L", "AL")) == "AL":
            t[i] = "AN"
    # W3: AL הוא R
    t = ["R" if kind == "AL" else kind for kind in t]
    # W4: מפריד בודד בין שני מספרים מאותו סוג הופך לסוג שלהם
    for i in range(1, n - 1):
        if t[i] == "ES" and t[i - 1] == "EN" and t[i + 1] == "EN":
            t[i] = "EN"
        elif t[i] == "CS" and t[i - 1] == t[i + 1] and t[i - 1] in ("EN", "AN"):
            t[i] = t[i - 1]
    # W5: רצף של ET שצמוד ל-EN הופך ל-EN
    for start, end in _runs(t, lambda kind: kind == "ET"):
        if (start > 0 and t[start - 1] == "EN") or (end < n and t[end] == "EN"):
            t[start:end] = ["EN"] * (end - start)
    # W6: שאר המפרידים הם ניטרליים
    return ["ON" if kind in ("ES", "ET", "CS") else kind for kind in t]


def _neutral_rules(t: list[str]) -> list[str]:
    """N1, N2: רצף ניטרלים מקבל את הכיוון שמשני צדדיו כשהוא זהה (EN ו-AN נחשבים R),
    ואחרת את כיוון הפסקה (R). בקצוות השורה: sos ו-eos, שניהם R."""
    resolved = list(t)
    n = len(t)
    for start, end in _runs(t, lambda kind: kind in _NEUTRAL):
        before = _as_strong(t[start - 1]) if start > 0 else "R"
        after = _as_strong(t[end]) if end < n else "R"
        resolved[start:end] = [before if before == after else "R"] * (end - start)
    return resolved


def _levels(resolved: list[str], weak: list[str], trailing_whitespace: str) -> list[int]:
    """I2 ו-L1. trailing_whitespace: באיזה צד של הרצף נמצא "סוף השורה" של L1."""
    levels = [LTR_LEVEL if kind in ("L", "EN", "AN") else RTL_LEVEL for kind in resolved]
    n = len(weak)
    for i in range(n):
        if weak[i] == "S":
            levels[i] = RTL_LEVEL
            for j in _whitespace_next_to(weak, i):
                levels[j] = RTL_LEVEL
    edge = range(n - 1, -1, -1) if trailing_whitespace == "end" else range(n)
    for i in edge:
        if weak[i] != "WS":
            break
        levels[i] = RTL_LEVEL
    return levels


def _as_strong(kind: str) -> str:
    return "R" if kind in ("R", "EN", "AN") else kind


def _runs(t: list[str], member: Callable[[str], bool]) -> list[tuple[int, int]]:
    """הרצפים המקסימליים של איברים שמקיימים את התנאי: (התחלה, סוף לא כולל)."""
    runs = []
    i = 0
    while i < len(t):
        if not member(t[i]):
            i += 1
            continue
        end = i
        while end < len(t) and member(t[end]):
            end += 1
        runs.append((i, end))
        i = end
    return runs


def _whitespace_next_to(t: list[str], i: int) -> list[int]:
    """L1: הרווחים שלפני מפריד. בסדר של העמוד "לפני" תלוי ברמה, ולכן שני הצדדים."""
    found = []
    for step in (-1, 1):
        j = i + step
        while 0 <= j < len(t) and t[j] == "WS":
            found.append(j)
            j += step
    return found


# ---------- הכיוון הרגיל: מטקסט לוגי לתצוגה ----------

def _bracket_pairs(texts: Sequence[str], t: list[str]) -> list[tuple[int, int]]:
    """BD16: זוגות הסוגריים בסדר הלוגי, לפי מיקום הסוגר הפותח."""
    stack: list[tuple[str, int]] = []
    pairs = []
    for i, text in enumerate(texts):
        if t[i] != "ON" or not text:
            continue
        char = text[0]
        if char in _BRACKET_PAIRS:
            if len(stack) == _BD16_STACK:
                return []
            stack.append((_BRACKET_PAIRS[char], i))
        elif char in _CLOSING:
            for depth in range(len(stack) - 1, -1, -1):
                if stack[depth][0] == char:
                    pairs.append((stack[depth][1], i))
                    del stack[depth:]
                    break
    return sorted(pairs)


def _bracket_rule(texts: Sequence[str], t: list[str]) -> list[str]:
    """N0: זוג סוגריים מקבל כיוון לפי מה שבתוכו ומה שלפניו (EN ו-AN נחשבים R)."""
    t = list(t)
    for opening, closing in _bracket_pairs(texts, t):
        inside = {_as_strong(kind) for kind in t[opening + 1:closing]}
        if "R" in inside:  # כיוון ההטבעה (פסקה ברמה 1) הוא R
            direction = "R"
        elif "L" in inside:
            context = [_as_strong(kind) for kind in t[:opening]]
            direction = "L" if _strong_before(context, opening, ("L", "R")) == "L" else "R"
        else:
            continue
        t[opening] = t[closing] = direction
    return t


def display_levels(texts: Sequence[str]) -> list[int]:
    """הרמה של כל תו בטקסט לוגי, בפסקה עברית (רמה 1)."""
    t = _weak_rules([bidi_class(text) for text in texts])
    for i in range(len(t)):  # W7
        if t[i] == "EN" and _strong_before(t, i, ("R", "L")) == "L":
            t[i] = "L"
    weak = list(t)
    resolved = _neutral_rules(_bracket_rule(texts, t))
    return _levels(resolved, weak, trailing_whitespace="end")


def display_order(levels: Sequence[int]) -> list[int]:
    """L2: האינדקסים של הטקסט הלוגי לפי הסדר שבו הם מוצגים, משמאל לימין."""
    order = list(range(len(levels)))
    for level in (LTR_LEVEL, RTL_LEVEL):
        i = 0
        while i < len(order):
            if levels[order[i]] < level:
                i += 1
                continue
            end = i
            while end < len(order) and levels[order[end]] >= level:
                end += 1
            order[i:end] = order[i:end][::-1]
            i = end
    return order


# ---------- הכיוון ההפוך: מהעמוד לסדר לוגי ----------

@dataclass(frozen=True)
class Reading(Generic[T]):
    logical: list[T]
    ambiguous: bool  # היו כמה קריאות תקינות, וברירת המחדל הכריעה


def _numbers(weak: list[str]) -> list[tuple[int, int]]:
    """המספרים בשורה (רצפי EN אחרי W1-W6) שצמודים, דרך ניטרלים בלבד, לאות לטינית.

    רק אצלם W7 משנה משהו: מספר שלא צמוד לאות לטינית מוצג באותו מקום בכל מקרה.
    """
    def neighbor(i: int, step: int) -> str:
        while 0 <= i < len(weak) and weak[i] in _NEUTRAL:
            i += step
        return weak[i] if 0 <= i < len(weak) else "R"
    return [(start, end) for start, end in _runs(weak, lambda kind: kind == "EN")
            if "L" in (neighbor(start - 1, -1), neighbor(end, 1))]


def _visual_levels(weak: list[str], promoted: set[tuple[int, int]]) -> list[int]:
    t = list(weak)
    for start, end in promoted:
        t[start:end] = ["L"] * (end - start)
    return _levels(_neutral_rules(t), weak, trailing_whitespace="start")


def _invert_l2(visual: Sequence[T], levels: list[int]) -> list[T]:
    """ההיפוך של L2: מימין לשמאל, וכל רצף ברמה 2 נשאר משמאל לימין."""
    logical: list[T] = []
    i = len(visual) - 1
    while i >= 0:
        if levels[i] == RTL_LEVEL:
            logical.append(visual[i])
            i -= 1
            continue
        start = i
        while start > 0 and levels[start - 1] == LTR_LEVEL:
            start -= 1
        logical.extend(visual[start:i + 1])
        i = start - 1
    return logical


def _displays_as_visual(logical_ids: list[int], texts_by_id: Sequence[str]) -> bool:
    """האם התצוגה של הקריאה מחזירה בדיוק את הסדר שבעמוד. רק רווחים בקצות השורה
    לא נספרים: כלל L1 מזיז אותם, והם יורדים מהפלט בכל מקרה."""
    def inner(ids: list[int]) -> list[int]:
        spaces = [bidi_class(texts_by_id[i]) == "WS" for i in ids]
        start = spaces.index(False) if False in spaces else len(ids)
        end = len(ids) - spaces[::-1].index(False) if False in spaces else start
        return ids[start:end]
    texts = [texts_by_id[i] for i in logical_ids]
    shown = [logical_ids[i] for i in display_order(display_levels(texts))]
    return inner(shown) == inner(sorted(shown))


def _punctuation_errors(text: str) -> int:
    """סימני פיסוק שלפניהם רווח ושצמודים למילה שאחריהם: " .1", " :Database".

    רק התו רווח נחשב רווח: isspace() מחשיב גם את U+001C עד U+001F, שבקבצים הם
    אותיות שמופו בטעות (ראו harness/textdiff.py)."""
    return sum(1 for i in range(1, len(text) - 1)
               if text[i] in _PUNCTUATION and text[i - 1] == " " and text[i + 1] != " ")


def to_logical(visual: Sequence[T], text_of: Callable[[T], str]) -> Reading[T]:
    """הסדר הלוגי של שורה, מהאיברים שלה בסדר שבו הם בעמוד משמאל לימין.

    text_of מחזיר את הטקסט של כל איבר. שורה בלי עברית נשארת כמו שהיא.
    """
    texts = [text_of(item) for item in visual]
    kinds = [bidi_class(text) for text in texts]
    if not is_rtl(kinds):
        return Reading(list(visual), ambiguous=False)
    weak = _weak_rules(kinds)
    numbers = _numbers(weak)
    # ברירת המחדל: W7 כשקוראים את V משמאל לימין (המספר שייך לאנגלית שמשמאלו)
    default = {number for number in numbers if _strong_before(weak, number[0], ("R", "L")) == "L"}

    candidates = {}  # קריאות שונות בלבד: היפוך של מספר שצמוד לאות בלי ניטרלים לא משנה כלום
    for flipped in _flip_sets(numbers):
        promoted = default.symmetric_difference(flipped)
        ids = tuple(_invert_l2(list(range(len(visual))), _visual_levels(weak, promoted)))
        if ids in candidates:
            continue
        valid = _displays_as_visual(list(ids), texts)
        errors = _punctuation_errors(re.sub(" +", " ", "".join(texts[i] for i in ids)))
        candidates[ids] = (not valid, errors, len(flipped))
    ranked = sorted(candidates.items(), key=lambda item: item[1])
    best_ids, (invalid, errors, _flips) = ranked[0]
    ties = [ids for ids, rank in ranked if rank[:2] == (invalid, errors)]
    return Reading([visual[i] for i in best_ids], ambiguous=not invalid and len(ties) > 1)


def _flip_sets(numbers: list[tuple[int, int]]):
    """כל קבוצות המספרים שאפשר להפוך בהן את ברירת המחדל, מהקטנה לגדולה."""
    largest = len(numbers) if len(numbers) <= _FULL_SEARCH_LIMIT else 2
    for size in range(largest + 1):
        for flipped in itertools.combinations(numbers, size):
            yield set(flipped)
