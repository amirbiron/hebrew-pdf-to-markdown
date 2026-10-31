"""כיוון הפסקה נקבע לפי המסמך, לא לפי השורה (hebrew_pdf/logical_order.py, document_rtl).

שורה בלי עברית במסמך עברי היא חלק מפסקה עברית. בעמוד של הצעת המחיר הכתובת נראית
"/https://amirbiron.github.io/Automation-made-easy": הלוכסן שבסוף הכתובת מצויר בקצה
השמאלי, כי כך מוצגת כתובת שמסתיימת בלוכסן בפסקה מימין לשמאל. כשהשורה נקראה כפסקה
משמאל לימין, הלוכסן קפץ לתחילת הכתובת (שורה 16 ב-testset/labels.md).

מילה אחת באנגלית ("OSMentor", שורה 7) נראית זהה בשני הכיוונים, ולכן לא משתנה.

הבדיקות שעל הקבצים עוברות דרך הקורא של מערך הבדיקה (harness/reader.py), כמו הדוח.
"""

import unittest

from harness.display_check import displays_like_page
from harness.reader import read_pages
from harness.run import DEFAULT_PDFS
from harness.textdiff import normalize


def page_lines(file_name: str, page: int):
    return read_pages(DEFAULT_PDFS / file_name)[page - 1].lines


class HebrewDocumentTest(unittest.TestCase):
    def test_slash_at_the_end_of_an_address_stays_at_the_end(self):  # שורה 16
        lines = page_lines("price-quote_weasyprint.pdf", 1)
        texts = [normalize(line.text) for line in lines]
        self.assertIn("https://amirbiron.github.io/Automation-made-easy/", texts)
        self.assertNotIn("/https://amirbiron.github.io/Automation-made-easy", texts)

    def test_the_display_check_uses_the_direction_of_the_reader(self):
        # הכתובת, כשמציגים אותה בפסקה מימין לשמאל, נראית כמו בעמוד. בדיקה שמחשבת כיוון
        # משלה (משמאל לימין לשורה בלי עברית) הייתה מכשילה את הפלט הנכון
        line = next(line for line in page_lines("price-quote_weasyprint.pdf", 1)
                    if "Automation-made-easy" in line.text)
        self.assertTrue(line.rtl)
        self.assertTrue(displays_like_page(line))

    def test_one_english_word_is_unchanged(self):  # שורה 7
        texts = [normalize(line.text) for line in page_lines("mentoros-overview_weasyprint.pdf", 1)]
        self.assertIn("OSMentor", texts)


if __name__ == "__main__":
    unittest.main()
