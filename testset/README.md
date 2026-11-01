# סט הבדיקה

12 קובצי PDF אמיתיים בעברית, משמונה תוכנות יצירה שונות, 141 עמודים בסך הכול, ועוד שלושה קבצים שנבנו משני מקורות ידועים, כך שהמבנה של כל עמוד בהם ידוע מראש: קובץ טבלאות (26 עמודים), ומסמך האפיון של הפרויקט משתי תוכנות (9 עמודים בכל אחת). התוכנה שיצרה כל קובץ מופיעה בשם הקובץ, אחרי הקו התחתון, כי היא המשתנה החשוב: היא קובעת איך העברית ממוקמת בקובץ.

| קובץ | תוכנה | עמודים | מה מיוחד בו |
|---|---|---|---|
| `chatbot-spec-form_gdocs.pdf` | Google Docs | 4 | טבלאות של שאלה ותשובה; סוגריים בכותרת |
| `doc-6p_gdocs.pdf` | Google Docs | 6 | |
| `mentoros-overview_weasyprint.pdf` | WeasyPrint | 8 | הרבה עברית-אנגלית מעורבת ("AI", "Deep Dive", "Amir Biron"); שורת נתונים עם תאים צמודים; תוכן עניינים |
| `price-quote_weasyprint.pdf` | WeasyPrint | 7 | הצעת מחיר: תאריכים, טלפון, כתובת אתר ומייל בתוך עברית; כותרת עם ריווח אותיות |
| `social-publisher-setup_weasyprint.pdf` | WeasyPrint | 2 | |
| `doc-4p_weasyprint.pdf` | WeasyPrint | 4 | |
| `doc-2p_weasyprint.pdf` | WeasyPrint | 2 | |
| `gps-book_indesign.pdf` | InDesign | 16 | ספר תדמית; הכריכה היא תמונה בלי טקסט (עמוד שצריך לסמן) |
| `marketing-flyer_illustrator.pdf` | Illustrator | 1 | פלאייר עם כמה עמודות; רווחים במקום לא נכון ("ומהא יתך") |
| `presentation_canva.pdf` | Canva (Ghostscript) | 24 | מצגת |
| `optimization_chrome.pdf` | Chrome | 1 | |
| `financial-report-q2-2025_aspose.pdf` | Aspose | 66 | דוח כספי רבעוני ציבורי (מאיה). עמוד 35 הוא דוח רווח והפסד: 7 עמודות, כותרות בשלוש שורות, מספרים שליליים בסוגריים, כוכביות |
| `env-vars_weasyprint.pdf` | WeasyPrint | 26 | קובץ הטבלאות: רפרנס משתני הסביבה של CodeBot, לרוחב, 6 טבלאות ו-468 שורות, עם תאים שנשברים לכמה שורות (ברווח, אחרי מקף או אחרי לוכסן; לא באמצע מילה). נבנה מ-`sources/env-vars.md` ב-`tools/build_table_pdf.py`, ודף התשובות שלו ב-`ground_truth/env-vars.truth.json`. לא חלק מ-40 השורות המתויגות: נמדד תא מול תא ובלוק מול בלוק |
| `spec_weasyprint.pdf` | WeasyPrint | 9 | מסמך האפיון של הפרויקט (עותק קבוע, `sources/spec.md`): כותרות בשלוש רמות, פסקאות, רשימות (גם פנימית), ציטוטים ו-7 טבלאות קצרות. דף התשובות שלו, המבנה כולו, ב-`ground_truth/spec.truth.json` |
| `spec_chrome.pdf` | Chrome | 9 | אותו מקור ואותו HTML, מודפס ב-Chrome, עם אותו דף תשובות. כך רואים אם כשל תלוי בתוכנה: ב-Chrome התבליטים של רשימה מצוירים כצורה ולא כתו |

שורות מתויגות מתוך הקבצים האלה נמצאות ב-`labels.md`, דפי התשובות של הקבצים שנבנו ממקור ידוע ב-`ground_truth/` (ההסבר ב-`ground_truth/README.md`), והדוח של מערך הבדיקה ב-`report.md`.

> הסט כולל מסמכים אישיים ומסמכי לקוח, ולכן הריפו פרטי. לא להוסיף קבצים אמיתיים חדשים בלי לבדוק קודם שמותר.
