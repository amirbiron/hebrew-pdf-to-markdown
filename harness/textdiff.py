"""השוואת טקסט: פיצול לשורות, נרמול רווחים, מרחק תווים, והצגה של תווים בלתי נראים."""

import re
import unicodedata

# כל תווי הרווח של Unicode (קטגוריה Zs) ועוד טאב. בכוונה לא \s ולא str.split():
# שניהם מחשיבים גם את U+001C עד U+001F לרווח, ואלה בדיוק התווים שהפלאייר מוציא
# במקום אותיות שלא מופו (GPS, סימן שאלה). נרמול שהופך אותם לרווח היה מסתיר כשל.
_SPACE_RUN = re.compile("[\t\u0020\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+")


def split_lines(page_text: str) -> list[str]:
    """פיצול עמוד לשורות לפי "\\n" בלבד.

    לא splitlines(): הוא שובר שורה גם על U+001C עד U+001E, U+0085 ו-U+2028,
    וכך שורה אחת מהפלאייר הופכת לשלוש.
    """
    return page_text.split("\n")


def normalize(text: str) -> str:
    """רצף רווחים הופך לרווח אחד, ורווחים בקצוות יורדים. שום תו אחר לא משתנה.

    מספר הרווחים לא נראה בתמונה ולא משנה ב-Markdown, ולכן הוא לא נספר כשגיאה.
    המיקום של הרווח כן נשמר: "ומהא יתך" מול "ומה איתך" נשאר שונה.
    """
    return _SPACE_RUN.sub(" ", text).strip(" ")


def levenshtein(a: str, b: str, limit: int | None = None) -> int:
    """מרחק עריכה ברמת התו (הוספה, מחיקה, החלפה, כל אחת במחיר 1).

    limit: כשכל השורה בטבלה כבר גדולה ממנו, אין סיכוי לרדת מתחתיו, והפונקציה
    מחזירה limit + 1 בלי להמשיך. זה רק קיצור דרך לחיפוש המינימום על פני שורות העמוד.
    """
    if len(a) < len(b):
        a, b = b, a
    if limit is not None and len(a) - len(b) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (char_a != char_b),
            ))
        if limit is not None and min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def closest_line(expected: str, lines: list[str]) -> tuple[int, str]:
    """השורה בעמוד שהכי קרובה לטקסט הנכון: (מרחק, השורה). בתיקו, הראשונה מלמעלה.

    שני הצדדים מנורמלים לפני ההשוואה. עמוד בלי שורות מחזיר את אורך הטקסט הנכון
    (כל התווים חסרים) ושורה ריקה.
    """
    target = normalize(expected)
    best_distance = len(target)
    best_line = ""
    for line in lines:
        candidate = normalize(line)
        distance = levenshtein(target, candidate, limit=best_distance)
        if distance < best_distance or (distance == best_distance and not best_line):
            best_distance, best_line = distance, candidate
        if best_distance == 0:
            break
    return best_distance, best_line


def visible(text: str) -> str:
    """תווי בקרה ותווי עיצוב בלתי נראים מוצגים כ-⟨U+XXXX⟩, כדי שיופיעו בדוח ובטבלה.

    קטגוריה Cc (למשל U+001D, U+009A) ו-Cf (למשל U+200F, U+FEFF). בלעדיה שורה
    שנראית זהה לתיוג יכולה להיות שונה ממנו, ואין דרך לראות למה.
    """
    return "".join(
        f"⟨U+{ord(ch):04X}⟩" if unicodedata.category(ch) in ("Cc", "Cf") else ch
        for ch in text
    )
