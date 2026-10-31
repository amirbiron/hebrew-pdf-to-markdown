# דוח מערך הבדיקה

> נוצר על ידי `python -m harness`. לא לערוך ביד: כל הרצה כותבת אותו מחדש. השוואה בין שתי הרצות היא git diff על הקובץ הזה.

הקורא שנבדק: `harness.reader.read_pages`

## סיכום

| | |
|---|---|
| שורות מאושרות שנספרו | 0 |
| זהות לתיוג | 0 מתוך 0 |
| מרחק תווים כולל | 0 |
| שיעור שגיאת תווים (מרחק חלקי מספר התווים בטקסט הנכון) | — |
| ממתינות לאישור (לא נספרות) | 39 |
| לא ברורות (לא נספרות) | 1 |
| שורות פגומות בטבלת התיוג | 0 |

מרחק תווים: כמה הוספות, מחיקות או החלפות של תו בודד צריך כדי להגיע מהשורה הקרובה ביותר בעמוד לטקסט הנכון. 0 = זהה. רצף רווחים נחשב לרווח אחד.

המרחק הוא גבול תחתון: כשהקורא שובר שורה מאוד (למשל מדביק אליה עמודה שכנה), שורה אחרת בעמוד יכולה להיות קרובה יותר מהשורה שלה, ואז המרחק קטן מהשגיאה האמיתית. בעמודה "השורה הקרובה ביותר בפלט" רואים מול איזו שורה נמדד. המדד הראשי הוא מספר השורות הזהות.

## שורות מתויגות

עדיין אין שורות מאושרות. שורה נספרת רק כשהסטטוס שלה ב-testset/labels.md הוא "מאושר".

ממתינות לאישור: 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40

לא ברורות: 7

## לפי קובץ

אותיות סופיות: אחוז המילים (מבין אלה שיש בהן אות סופית) שהאות הסופית לא בתחילתן; גבוה = טוב. פיסוק בתחילת שורה: אחוז השורות העבריות שמתחילות בסימן פיסוק; נמוך = טוב. שתיהן בדיקות עקיפות מהאב-טיפוס, ו-100% בהן אינו הוכחה שהפלט נכון.

| קובץ | תוכנה | עמודים | אותיות סופיות | פיסוק בתחילת שורה | מאושרות | זהות | מרחק |
|---|---|---|---|---|---|---|---|
| chatbot-spec-form_gdocs.pdf | gdocs | 4 | 100% | 0% | 0 | 0 | 0 |
| doc-2p_weasyprint.pdf | weasyprint | 2 | 100% | 0% | 0 | 0 | 0 |
| doc-4p_weasyprint.pdf | weasyprint | 4 | 100% | 0% | 0 | 0 | 0 |
| doc-6p_gdocs.pdf | gdocs | 6 | 100% | 0% | 0 | 0 | 0 |
| financial-report-q2-2025_aspose.pdf | aspose | 66 | 100% | 0% | 0 | 0 | 0 |
| gps-book_indesign.pdf | indesign | 16 | 100% | 0% | 0 | 0 | 0 |
| marketing-flyer_illustrator.pdf | illustrator | 1 | 100% | 0% | 0 | 0 | 0 |
| mentoros-overview_weasyprint.pdf | weasyprint | 8 | 100% | 0% | 0 | 0 | 0 |
| optimization_chrome.pdf | chrome | 1 | 100% | 0% | 0 | 0 | 0 |
| presentation_canva.pdf | canva | 24 | 100% | 0% | 0 | 0 | 0 |
| price-quote_weasyprint.pdf | weasyprint | 7 | 100% | 0% | 0 | 0 | 0 |
| social-publisher-setup_weasyprint.pdf | weasyprint | 2 | 100% | 0% | 0 | 0 | 0 |

## לפי עמוד

<details>
<summary>כל העמודים</summary>

| קובץ | עמוד | שורות עם טקסט | אותיות סופיות | פיסוק בתחילת שורה |
|---|---|---|---|---|
| chatbot-spec-form_gdocs.pdf | 1 | 18 | 100% | 0% |
| chatbot-spec-form_gdocs.pdf | 2 | 15 | 100% | 0% |
| chatbot-spec-form_gdocs.pdf | 3 | 17 | 100% | 0% |
| chatbot-spec-form_gdocs.pdf | 4 | 7 | 100% | 0% |
| doc-2p_weasyprint.pdf | 1 | 28 | 100% | 0% |
| doc-2p_weasyprint.pdf | 2 | 4 | 100% | 0% |
| doc-4p_weasyprint.pdf | 1 | 31 | 100% | 0% |
| doc-4p_weasyprint.pdf | 2 | 28 | 100% | 0% |
| doc-4p_weasyprint.pdf | 3 | 33 | 100% | 0% |
| doc-4p_weasyprint.pdf | 4 | 1 | 100% | 0% |
| doc-6p_gdocs.pdf | 1 | 36 | 100% | 0% |
| doc-6p_gdocs.pdf | 2 | 34 | 100% | 0% |
| doc-6p_gdocs.pdf | 3 | 34 | 100% | 0% |
| doc-6p_gdocs.pdf | 4 | 38 | 100% | 0% |
| doc-6p_gdocs.pdf | 5 | 36 | 100% | 0% |
| doc-6p_gdocs.pdf | 6 | 32 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 1 | 2 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 2 | 8 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 3 | 2 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 4 | 24 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 5 | 37 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 6 | 40 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 7 | 35 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 8 | 32 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 9 | 43 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 10 | 38 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 11 | 38 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 12 | 25 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 13 | 61 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 14 | 39 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 15 | 23 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 16 | 44 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 17 | 49 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 18 | 44 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 19 | 49 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 20 | 35 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 21 | 33 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 22 | 41 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 23 | 28 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 24 | 17 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 25 | 38 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 26 | 49 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 27 | 32 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 28 | 2 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 29 | 3 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 30 | 15 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 31 | 26 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 32 | 17 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 33 | 25 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 34 | 41 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 35 | 48 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 36 | 30 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 37 | 31 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 38 | 18 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 39 | 46 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 40 | 45 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 41 | 32 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 42 | 36 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 43 | 22 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 44 | 40 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 45 | 27 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 46 | 39 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 47 | 31 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 48 | 19 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 49 | 33 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 50 | 31 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 51 | 13 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 52 | 2 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 53 | 5 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 54 | 12 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 55 | 22 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 56 | 25 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 57 | 35 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 58 | 42 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 59 | 50 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 60 | 45 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 61 | 17 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 62 | 21 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 63 | 42 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 64 | 1 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 65 | 39 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 66 | 43 | 100% | 0% |
| gps-book_indesign.pdf | 1 | 0 (אין טקסט) | — | — |
| gps-book_indesign.pdf | 2 | 24 | 100% | 0% |
| gps-book_indesign.pdf | 3 | 0 (אין טקסט) | — | — |
| gps-book_indesign.pdf | 4 | 18 | 100% | 0% |
| gps-book_indesign.pdf | 5 | 20 | 100% | 0% |
| gps-book_indesign.pdf | 6 | 43 | 100% | 0% |
| gps-book_indesign.pdf | 7 | 6 | — | — |
| gps-book_indesign.pdf | 8 | 31 | 100% | 0% |
| gps-book_indesign.pdf | 9 | 12 | 100% | 0% |
| gps-book_indesign.pdf | 10 | 35 | 100% | 0% |
| gps-book_indesign.pdf | 11 | 7 | — | — |
| gps-book_indesign.pdf | 12 | 21 | 100% | 0% |
| gps-book_indesign.pdf | 13 | 24 | 100% | 0% |
| gps-book_indesign.pdf | 14 | 9 | — | — |
| gps-book_indesign.pdf | 15 | 3 | 100% | — |
| gps-book_indesign.pdf | 16 | 5 | 100% | 0% |
| marketing-flyer_illustrator.pdf | 1 | 65 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 1 | 9 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 2 | 15 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 3 | 19 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 4 | 19 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 5 | 19 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 6 | 19 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 7 | 8 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 8 | 12 | 100% | 0% |
| optimization_chrome.pdf | 1 | 14 | 100% | 0% |
| presentation_canva.pdf | 1 | 4 | 100% | 0% |
| presentation_canva.pdf | 2 | 15 | 100% | 0% |
| presentation_canva.pdf | 3 | 19 | 100% | 0% |
| presentation_canva.pdf | 4 | 16 | 100% | 0% |
| presentation_canva.pdf | 5 | 21 | 100% | 0% |
| presentation_canva.pdf | 6 | 16 | 100% | 0% |
| presentation_canva.pdf | 7 | 23 | 100% | 0% |
| presentation_canva.pdf | 8 | 31 | 100% | 0% |
| presentation_canva.pdf | 9 | 20 | 100% | 0% |
| presentation_canva.pdf | 10 | 28 | 100% | 0% |
| presentation_canva.pdf | 11 | 18 | 100% | 0% |
| presentation_canva.pdf | 12 | 18 | 100% | 0% |
| presentation_canva.pdf | 13 | 25 | 100% | 0% |
| presentation_canva.pdf | 14 | 23 | 100% | 0% |
| presentation_canva.pdf | 15 | 23 | 100% | 0% |
| presentation_canva.pdf | 16 | 20 | 100% | 5% |
| presentation_canva.pdf | 17 | 22 | 100% | 0% |
| presentation_canva.pdf | 18 | 21 | 100% | 0% |
| presentation_canva.pdf | 19 | 25 | 100% | 0% |
| presentation_canva.pdf | 20 | 17 | 100% | 0% |
| presentation_canva.pdf | 21 | 22 | 100% | 0% |
| presentation_canva.pdf | 22 | 11 | 100% | 0% |
| presentation_canva.pdf | 23 | 20 | 100% | 0% |
| presentation_canva.pdf | 24 | 13 | 100% | 0% |
| price-quote_weasyprint.pdf | 1 | 15 | 100% | 0% |
| price-quote_weasyprint.pdf | 2 | 18 | 100% | 0% |
| price-quote_weasyprint.pdf | 3 | 40 | 100% | 0% |
| price-quote_weasyprint.pdf | 4 | 39 | 100% | 0% |
| price-quote_weasyprint.pdf | 5 | 40 | 100% | 0% |
| price-quote_weasyprint.pdf | 6 | 42 | 100% | 0% |
| price-quote_weasyprint.pdf | 7 | 20 | 100% | 0% |
| social-publisher-setup_weasyprint.pdf | 1 | 24 | 100% | 0% |
| social-publisher-setup_weasyprint.pdf | 2 | 6 | 100% | 0% |

</details>
