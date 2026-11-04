"""כיול הספים של הציון (hebrew_pdf/score.py), בשלושת הכלים של מסמך האפיון ("כיול ומדידה"):

1. שגיאות מכוונות. לוקחים עמודים שהפלט שלהם ידוע כנכון (known_good: כל העמודים של הקבצים שיש להם דף
   תשובות, ועמודים שכל השורות המתויגות בהם זהות), ומשחיתים את הפלט בכל צורות הכשל שראינו (FORMS). ההשחתה היא
   של הטקסט שהקורא הוציא, ולא של הקורא: היא לא תלויה באיך הקורא הגיע לפלט. מה שבעמוד (Component.visual) ורשימת
   התווים של PDFium (PageText.reference) נשארים, כמו כשקורא שבור מוציא פלט שגוי מקובץ תקין. יוצא מזה רק "תווי
   בקרה במקום אותיות", שהוא כשל של הקובץ ולא של הקורא, ולכן התו משתנה גם ברשימת התווים של PDFium. כל צורה בשתי
   עוצמות: רכיב אחד בעמוד (one), וכל הרכיבים שהצורה חלה עליהם (all), כמו קורא שנכשל בכל הקובץ.
   נמדד רק על עמודים שאין בהם כשל ודאי לפני ההשחתה (_hard_failure): אחרת "נתפס" אינו אומר כלום.
2. השארת תוכנה אחת בחוץ (leave_one_out): לכל תוכנה, הספים מחושבים מהעמודים של שאר התוכנות, ונבדקים על העמודים
   שלה. סף שמשתנה מאוד בין התוכנות הוא דגל, לא ערך.
3. רגישות (stable_range): לכל סף, הטווח שבו ההחלטה והסיבות של כל עמוד בסט לא משתנות.

איך נקבע כל סף (ההסבר המלא והמספרים ליד הקבועים ב-hebrew_pdf/score.py):
- MIN_PLAUSIBLE: הסימנים של הסבירות הם גיבוי לבדיקת התצוגה, ובנויים לתפוס היפוך של אותיות עבריות (אות סופית
  במקום לא נכון). הדרישה (required_plausible): שהם לבדם יתפסו 95% מהעמודים שכל השורות בהם הפוכות, בשתי
  הצורות שהם בנויים להן (SIGNAL_TARGETS): האחוזון ה-95 של הציון של העמודים המושחתים (ההתייעצות על מדידה, סעיף
  1.6). הערך: האמצע של הטווח היציב הראשון שכולו מעל הדרישה.
- MAX_EFFORT: השחתה של הפלט לא משנה את מאמץ התיקון (הוא נמדד מול הקובץ), ולכן אין לו שגיאות מכוונות. הכלל
  (effort_envelope): המאמץ הגבוה ביותר בעמוד שהפלט שלו ידוע כנכון. עד שם יש ראיה שהתיקונים של הקורא עובדים, ומעבר
  לזה אין. הערך: האמצע של הטווח היציב שמכיל אותו.

פרטיות: הכיול נשען על הטקסט של העמודים, אבל מה שיוצא ממנו הוא מספרים בלבד.
"""

import dataclasses
import math
import random
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from hebrew_pdf import score as score_mod
from hebrew_pdf.lines import Component, PageText

# ---------- צורות ההשחתה ----------

_LTR_RUN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.,:/_+\-]*[A-Za-z0-9])?")
_CONTROL = "\x1d"  # תו בקרה, כמו האותיות של GPS בפלאייר (U+001D עד U+001F)


def _reverse_line(text: str, rng: random.Random) -> str:
    """כל השורה הפוכה תו-תו, כמו "תוריכממ תוסנכה" במקום "הכנסות ממכירות"."""
    return text[::-1]


def _reverse_ltr(text: str, rng: random.Random) -> str:
    """כל רצף של אנגלית או מספר הפוך ("noriB rimA", "5202"), והעברית במקומה."""
    return _LTR_RUN.sub(lambda m: m.group(0)[::-1], text)


def _reverse_letters(text: str, rng: random.Random) -> str:
    """האותיות של כל מילה עברית הפוכות, וסדר המילים נשמר."""
    return score_mod._WORD.sub(lambda m: m.group(0)[::-1], text)


def _reverse_words(text: str, rng: random.Random) -> str:
    """סדר המילים הפוך והאותיות נכונות, כמו poppler ("100% באותיות, אבל סדר המילים בשורה הפוך")."""
    return " ".join(reversed(text.split(" ")))


def _punct_to_start(text: str, rng: random.Random) -> str:
    """סימן הפיסוק שבסוף השורה עובר לתחילתה (".זה מנטור שזוכר")."""
    stripped = text.rstrip(" ")
    if len(stripped) > 1 and stripped[-1] in ".,:;!?":
        return stripped[-1] + stripped[:-1]
    return text


def _drop_char(text: str, rng: random.Random) -> str:
    """תו אחד (לא רווח) נשמט."""
    positions = [k for k, char in enumerate(text) if char != " "]
    if not positions:
        return text
    k = rng.choice(positions)
    return text[:k] + text[k + 1:]


def _control_char(text: str, rng: random.Random) -> str:
    """אות אחת הופכת לתו בקרה."""
    positions = [k for k, char in enumerate(text) if char.isalpha()]
    if not positions:
        return text
    k = rng.choice(positions)
    return text[:k] + _CONTROL + text[k + 1:]


@dataclass(frozen=True)
class Form:
    key: str
    name: str  # השם בעברית, לדוח
    change: Callable[[str, random.Random], str] | None  # None: צורה של שורה ולא של טקסט (הדבקה)
    in_file: bool = False  # כשל של הקובץ: התו משתנה גם ברשימת התווים של PDFium


FORMS = (
    Form("reverse_line", "היפוך שורה שלמה", _reverse_line),
    Form("reverse_ltr", "היפוך רצפי אנגלית ומספרים", _reverse_ltr),
    Form("reverse_letters", "היפוך אותיות בתוך מילה", _reverse_letters),
    Form("reverse_words", "היפוך סדר המילים", _reverse_words),
    Form("punct_to_start", "הזזת פיסוק לתחילת השורה", _punct_to_start),
    Form("glue", "הדבקת שתי עמודות", None),
    Form("drop", "השמטת תווים", _drop_char),
    Form("control", "תווי בקרה במקום אותיות", _control_char, in_file=True),
)
INTENSITIES = (("one", "רכיב אחד"), ("all", "כל הרכיבים"))
# הצורות שהסימנים של הסבירות בנויים להן: היפוך של אותיות עבריות, שמזיז אותיות סופיות. לפיהן נקבעת הדרישה
# ל-MIN_PLAUSIBLE. שאר הצורות נמדדות ומוצגות, אבל הסימנים לא נועדו להן (בדיקת התצוגה והשלמות כן)
SIGNAL_TARGETS = ("reverse_line", "reverse_letters")
CATCH_SHARE = 0.95  # הסימנים לבדם תופסים לפחות כך מהעמודים המושחתים (ההתייעצות על מדידה, סעיף 1.6)


def _rebuild(page: PageText, new: dict[tuple[int, int], str], glued: set[int]) -> PageText:
    """העמוד עם טקסט אחר לרכיבים new ((שורה, רכיב): טקסט), ושורות glued שכל הרכיבים שלהן נדבקו לרכיב אחד.

    מה שבעמוד (visual, הגיאומטריה, הרווחים, רשימת התווים) לא משתנה. התאים של שורה בטבלה, ושל שורת טבלה
    שאוחדה (PageText.rows), מורכבים מהטקסטים של הרכיבים, ולכן הטקסט הישן מוחלף בהם בחדש."""
    lines = []
    for i, line in enumerate(page.lines):
        if i in glued:
            visual_order = line.parts[::-1] if page.rtl_document else line.parts
            text = " ".join(part.text for part in visual_order)
            lines.append(dataclasses.replace(line, text=text, components=(Component(text, line.visual, line.rtl),)))
            continue
        components = tuple(dataclasses.replace(part, text=new.get((i, j), part.text))
                           for j, part in enumerate(line.parts))
        columns = line.columns
        if columns is not None:
            columns = _swapped(columns, [(part.text, new[(i, j)]) for j, part in enumerate(line.parts)
                                         if (i, j) in new])
        lines.append(dataclasses.replace(line, text=" ".join(c.text for c in components), components=components,
                                         columns=columns))
    rows = []
    for cells, source in zip(page.rows, page.sources):
        if source.table is None:
            rows.append(lines[source.lines[0]].cells)
        else:
            rows.append(_swapped(cells, [(part.text, new[(i, j)]) for i in source.lines
                                         for j, part in enumerate(page.lines[i].parts) if (i, j) in new]))
    return dataclasses.replace(page, lines=lines, table_rows=rows)


def _swapped(cells: Sequence[str], changes: list[tuple[str, str]]) -> tuple[str, ...]:
    """בכל החלפה, המופע הראשון של הטקסט הישן בתא הראשון שמכיל אותו. רכיב הוא חלק מהתא שלו (התאים מחוברים
    מהרכיבים), כך שהוא תמיד נמצא; כשאותו טקסט חוזר בשני תאים בשורה, ייתכן שהוחלף בתא הלא נכון, וזה לא משנה
    את הספירות של הציון (אותם תווים ואותן מילים)."""
    out = list(cells)
    for old, new in changes:
        for k, cell in enumerate(out):
            if old in cell:
                out[k] = cell.replace(old, new, 1)
                break
    return tuple(out)


def corrupt(page: PageText, dropped: frozenset, form: Form, intensity: str, rng: random.Random) -> PageText | None:
    """העמוד אחרי ההשחתה, או None כשהצורה לא חלה על אף רכיב בעמוד (אין שורה שמסתיימת בפיסוק, וכו').
    רק מה שמגיע ל-Markdown מושחת (לא מה שב-dropped). הדבקה חלה על שורה מחוץ לטבלה עם שני רכיבים לפחות."""
    if form.change is None:
        table_lines = {i for source in page.sources if source.table is not None for i in source.lines}
        eligible = [i for i, line in enumerate(page.lines) if len(line.parts) >= 2 and i not in table_lines
                    and not any((i, j) in dropped for j in range(len(line.parts)))]
        if not eligible:
            return None
        chosen = eligible if intensity == "all" else [rng.choice(eligible)]
        return _rebuild(page, {}, set(chosen))
    probe = random.Random(0)
    eligible = [(i, j) for i, line in enumerate(page.lines) for j, part in enumerate(line.parts)
                if (i, j) not in dropped and form.change(part.text, probe) != part.text]
    if not eligible:
        return None
    chosen = eligible if intensity == "all" else [rng.choice(eligible)]
    new = {(i, j): form.change(page.lines[i].parts[j].text, rng) for i, j in chosen}
    corrupted = _rebuild(page, new, set())
    if form.in_file:
        reference = page.reference or ""
        for (i, j), text in new.items():
            old = page.lines[i].parts[j].text
            lost = (Counter(old) - Counter(text))
            for char in lost.elements():
                reference = reference.replace(char, _CONTROL, 1)
        corrupted = dataclasses.replace(corrupted, reference=reference)
    return corrupted


# ---------- ההחלטה, כפונקציה של הספים ----------

@dataclass(frozen=True)
class Outcome:
    """מה שהציון מוצא בעמוד, בלי הספים: מזה ההחלטה מחושבת לכל סף (decide)."""
    rejected: bool
    display_failures: int = 0
    plausible: float = 1.0  # Signals.score
    complete: bool = True
    effort: float = 0.0  # Effort.score


def outcome(page: PageText, dropped: frozenset) -> Outcome:
    scored = score_mod.score_page(page, dropped)
    if scored.decision == score_mod.REJECTED:
        return Outcome(True)
    plausibility = scored.plausibility
    return Outcome(False, plausibility.display_failures, plausibility.signals.score, scored.completeness.ok,
                   scored.effort.score)


def decide(out: Outcome, min_plausible: float, max_effort: float) -> tuple[bool, ...]:
    """(נפסל, תצוגה, סימנים, שלמות, מאמץ): אילו כללים מסמנים את העמוד בספים האלה. תקין: אף אחד."""
    if out.rejected:
        return (True, False, False, False, False)
    return (False, out.display_failures > 0, out.plausible < min_plausible, not out.complete,
            out.effort > max_effort)


def _hard_failure(out: Outcome) -> bool:
    """כשל שאינו תלוי באף סף שמכיילים: פסילה, שורה שלא מוצגת כמו העמוד, או תו שחסר או נוסף."""
    return out.rejected or out.display_failures > 0 or not out.complete


# ---------- הכיול ----------

@dataclass(frozen=True)
class Corrupted:
    producer: str
    form: str
    intensity: str
    outcome: Outcome
    baseline: Outcome  # אותו עמוד לפני ההשחתה


@dataclass(frozen=True)
class Range:
    """טווח של ערכי סף שבו ההחלטות והסיבות בכל הסט זהות: low לא כולל, high כולל (או ההפך, לפי הכלל)."""
    low: float
    high: float

    @property
    def middle(self) -> float:
        return (self.low + self.high) / 2


@dataclass(frozen=True)
class Fold:
    producer: str
    pages: int  # עמודים ידועים כנכונים של התוכנה, בלי כשל ודאי
    required: float | None  # הדרישה ל-MIN_PLAUSIBLE מהעמודים של שאר התוכנות
    caught: tuple[int, int]  # עמודים מושחתים של התוכנה (SIGNAL_TARGETS, all) שהסימנים תפסו בדרישה הזו, מתוך
    flagged: tuple[int, int]  # עמודים נקיים של התוכנה שסומנו בדרישה הזו, מתוך
    envelope: float | None  # המאמץ הגבוה ביותר בעמוד ידוע כנכון של שאר התוכנות
    over: tuple[int, int]  # עמודים של התוכנה (כל העמודים שלא נפסלו) מעל המעטפת הזו, מתוך


@dataclass(frozen=True)
class Calibration:
    known_good: int  # עמודים ידועים כנכונים
    clean: int  # מתוכם, בלי כשל ודאי: עליהם נמדדות ההשחתות
    clean_flagged: Counter  # מהעמודים הנקיים, כמה סומנו בספים של הציון, לפי הכלל (סימנים / מאמץ)
    known_good_flagged: Counter  # מכל העמודים הידועים כנכונים, כמה סומנו, לפי הכלל
    corrupted: list[Corrupted]
    # None בשלושת השדות שאחרי זה, ובשתי הבחירות: אין ראיה (אין עמוד מושחת בצורות של SIGNAL_TARGETS, או אין עמוד
    # ידוע כנכון שלא נפסל), למשל בסט של קובץ אחד. אז הכיול לא בוחר ערך, והדוח אומר את זה
    required_plausible: float | None  # האחוזון ה-95 של הציון של העמודים המושחתים ב-SIGNAL_TARGETS
    envelope: float | None  # המאמץ הגבוה ביותר בעמוד ידוע כנכון
    plausible_range: Range  # הטווח היציב סביב MIN_PLAUSIBLE
    effort_range: Range  # הטווח היציב סביב MAX_EFFORT
    plausible_choice: Range | None  # הטווח היציב הראשון שכולו מעל required_plausible: MIN_PLAUSIBLE באמצע שלו
    effort_choice: Range | None  # הטווח היציב שמכיל את envelope: MAX_EFFORT באמצע שלו
    folds: list[Fold] = field(default_factory=list)
    count_rules: dict = field(default_factory=dict)  # לכלל של ספירה: כמה עמודים בסט עם 1, 2, 3 ומעלה


def known_good(read_files: dict[str, list[PageText]], truth_files: set[str],
               exact_by_page: dict[tuple[str, int], list[bool]]) -> list[tuple[str, int]]:
    """(קובץ, אינדקס עמוד מ-0) של העמודים שהפלט שלהם ידוע כנכון: כל העמודים של קובץ שיש לו דף תשובות, ועמודים
    שיש בהם לפחות שורה מתויגת ומאושרת אחת וכולן זהות. exact_by_page: לכל (קובץ, אינדקס עמוד), האם כל תיוג זהה."""
    good = {(name, i) for name in truth_files for i in range(len(read_files[name]))}
    good |= {key for key, exact in exact_by_page.items() if exact and all(exact)}
    return sorted(good)


def _percentile(values: Sequence[float], share: float) -> float:
    """הערך שחלק share מהערכים קטנים ממנו או שווים לו (האחוזון, בלי אינטרפולציה)."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(share * len(ordered)) - 1))]


def required_plausible(corrupted: Sequence[Corrupted]) -> float | None:
    """הדרישה ל-MIN_PLAUSIBLE: הגבוה מבין האחוזונים ה-95 של הציון של העמודים המושחתים, בכל צורה ב-SIGNAL_TARGETS
    בעוצמה all. סף מעליו תופס, בסימנים לבדם, לפחות 95% מהעמודים בכל אחת מהצורות. None: אין עמודים כאלה."""
    found = []
    for form in SIGNAL_TARGETS:
        scores = [c.outcome.plausible for c in corrupted if c.form == form and c.intensity == "all"
                  and not c.outcome.rejected]
        if scores:
            found.append(_percentile(scores, CATCH_SHARE))
    return max(found) if found else None


def stable_range(values: Sequence[float], at: float, flagged_below: bool) -> Range:
    """הטווח של ערכי הסף סביב at שבו אף עמוד לא עובר צד. flagged_below: עמוד מסומן כשהציון שלו קטן מהסף
    (סבירות); אחרת כשהוא גדול ממנו (מאמץ). values: הציונים של כל העמודים בסט."""
    distinct = sorted(set(values))
    if flagged_below:  # מסומן אם value < at: יציב עבור at ב-(הגדול שקטן מ-at, הקטן שגדול או שווה ל-at]
        low = max((v for v in distinct if v < at), default=0.0)
        high = min((v for v in distinct if v >= at), default=1.0)
    else:  # מסומן אם value > at: יציב עבור at ב-[הגדול שקטן או שווה ל-at, הקטן שגדול מ-at)
        low = max((v for v in distinct if v <= at), default=0.0)
        high = min((v for v in distinct if v > at), default=1.0)
    return Range(low, high)


def first_range_above(values: Sequence[float], required: float) -> Range:
    """הטווח היציב הראשון (flagged_below) שכולו מעל required: מהציון הראשון בסט שגדול או שווה ל-required."""
    above = sorted(v for v in set(values) if v >= required)
    low = above[0] if above else required
    high = above[1] if len(above) > 1 else 1.0
    return Range(low, high)


def calibrate(read_files: dict[str, list[PageText]], dropped_by_file: dict[str, frozenset],
              good: Sequence[tuple[str, int]], producer_of: Callable[[str], str],
              min_plausible: float = score_mod.MIN_PLAUSIBLE, max_effort: float = score_mod.MAX_EFFORT) -> Calibration:
    """dropped_by_file: markdown.Markdown.dropped של כל קובץ (עמוד מ-1, שורה, רכיב)."""
    def dropped_on(name: str, index: int) -> frozenset:
        return frozenset((line, part) for page, line, part in dropped_by_file.get(name, ()) if page == index + 1)

    outcomes = {(name, i): outcome(page, dropped_on(name, i))
                for name, pages in read_files.items() for i, page in enumerate(pages)}
    clean = [key for key in good if not _hard_failure(outcomes[key])]
    corrupted: list[Corrupted] = []
    for name, i in clean:
        page, dropped = read_files[name][i], dropped_on(name, i)
        baseline = outcomes[(name, i)]
        for form in FORMS:
            for intensity, _ in INTENSITIES:
                rng = random.Random(f"{name}|{i}|{form.key}|{intensity}")
                changed = corrupt(page, dropped, form, intensity, rng)
                if changed is not None:
                    corrupted.append(Corrupted(producer_of(name), form.key, intensity, outcome(changed, dropped),
                                               baseline))

    required = required_plausible(corrupted)
    envelope = max((outcomes[key].effort for key in good if not outcomes[key].rejected), default=None)
    live = [o for o in outcomes.values() if not o.rejected]
    plausible_values = [o.plausible for o in live]
    effort_values = [o.effort for o in live]

    def rule_counts(keys) -> Counter:
        counts: Counter = Counter()
        for key in keys:
            names = ("נפסל", "תצוגה", "סימנים", "שלמות", "מאמץ")
            for name, hit in zip(names, decide(outcomes[key], min_plausible, max_effort)):
                counts[name] += hit
            counts["כלשהו"] += any(decide(outcomes[key], min_plausible, max_effort))
        return counts

    folds = []
    for producer in sorted({producer_of(name) for name in read_files}):
        own_clean = [key for key in clean if producer_of(key[0]) == producer]
        others = [c for c in corrupted if c.producer != producer]
        fold_required = required_plausible(others)
        own_corrupted = [c for c in corrupted if c.producer == producer and c.form in SIGNAL_TARGETS
                         and c.intensity == "all" and not c.outcome.rejected]
        caught = sum(c.outcome.plausible < fold_required for c in own_corrupted) if fold_required is not None else 0
        flagged = sum(outcomes[key].plausible < fold_required for key in own_clean) if fold_required is not None else 0
        other_good = [outcomes[key].effort for key in good
                      if producer_of(key[0]) != producer and not outcomes[key].rejected]
        fold_envelope = max(other_good) if other_good else None
        own_pages = [key for key in outcomes if producer_of(key[0]) == producer and not outcomes[key].rejected]
        over = sum(outcomes[key].effort > fold_envelope for key in own_pages) if fold_envelope is not None else 0
        folds.append(Fold(producer, len(own_clean), fold_required, (caught, len(own_corrupted)),
                          (flagged, len(own_clean)), fold_envelope, (over, len(own_pages))))

    pages = list(read_files)
    count_rules = {}
    for label, count_of in (("תווים לא ממופים", lambda p: sum(score_mod.unmapped_char(c) for c in score_mod._all_text(p))
                             + p.marked_unmapped),
                            ("תווים בטקסט מסובב", lambda p: p.rotated_chars)):
        counts = [count_of(page) for name in pages for page in read_files[name]]
        count_rules[label] = Counter(min(c, 3) for c in counts if c)
    for label, count_of in (("שורות שלא מוצגות כמו העמוד", lambda o: o.display_failures),):
        count_rules[label] = Counter(min(count_of(o), 3) for o in live if count_of(o))
    missing = Counter()
    for name in pages:
        for i, page in enumerate(read_files[name]):
            if not outcomes[(name, i)].rejected:
                lost = sum(score_mod._completeness(page).missing.values()) + sum(score_mod._completeness(page).extra.values())
                if lost:
                    missing[min(lost, 3)] += 1
    count_rules["תווים שחסרים או נוספו"] = missing

    return Calibration(
        len(good), len(clean), rule_counts(clean), rule_counts(good), corrupted, required, envelope,
        stable_range(plausible_values, min_plausible, True), stable_range(effort_values, max_effort, False),
        first_range_above(plausible_values, required) if required is not None else None,
        stable_range(effort_values, envelope, False) if envelope is not None else None, folds, count_rules)


def catch_table(calibration: Calibration, min_plausible: float = score_mod.MIN_PLAUSIBLE,
                max_effort: float = score_mod.MAX_EFFORT) -> list[tuple[str, str, int, Counter]]:
    """לכל צורה ועוצמה: (צורה, עוצמה, מספר העמודים המושחתים, כמה נתפסו לפי כל כלל ובסך הכול). רק עמודים שיצאו
    תקין לפני ההשחתה בספים האלה: עמוד שכבר סומן "נתפס" בלי קשר להשחתה."""
    names = ("נפסל", "תצוגה", "סימנים", "שלמות", "מאמץ")
    rows = []
    for form in FORMS:
        for intensity, _ in INTENSITIES:
            found = [c for c in calibration.corrupted if c.form == form.key and c.intensity == intensity
                     and not any(decide(c.baseline, min_plausible, max_effort))]
            counts: Counter = Counter()
            for c in found:
                hits = decide(c.outcome, min_plausible, max_effort)
                for name, hit in zip(names, hits):
                    counts[name] += hit
                counts["כלשהו"] += any(hits)
            rows.append((form.key, intensity, len(found), counts))
    return rows


def form_name(key: str) -> str:
    return next(form.name for form in FORMS if form.key == key)


def intensity_name(key: str) -> str:
    return dict(INTENSITIES)[key]
