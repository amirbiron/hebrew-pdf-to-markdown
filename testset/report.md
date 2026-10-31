# דוח מערך הבדיקה

> נוצר על ידי `python -m harness`. לא לערוך ביד: כל הרצה כותבת אותו מחדש. השוואה בין שתי הרצות היא git diff על הקובץ הזה.

הקורא שנבדק: `harness.reader.read_pages`

## סיכום

| | |
|---|---|
| שורות מאושרות שנספרו | 40 |
| זהות לתיוג | 20 מתוך 40 |
| מרחק תווים כולל | 158 |
| שיעור שגיאת תווים (מרחק חלקי מספר התווים בטקסט הנכון) | 8.8% |
| ממתינות לאישור (לא נספרות) | 0 |
| לא ברורות (לא נספרות) | 0 |
| שורות פגומות בטבלת התיוג | 0 |
| אותיות שדולגו כי אין להן מיקום על הדף (בכל הסט) | 0 |
| סוגריים שהצורה שלהם לא נקבעה מהציור (בכל הסט) | 0 |
| שורות שלא עוברות את בדיקת התצוגה (בכל הסט) | 2 מתוך 3541 |
| שורות דו-משמעיות (בכל הסט) | 46 |

מרחק תווים: כמה הוספות, מחיקות או החלפות של תו בודד צריך כדי להגיע מהשורה הקרובה ביותר בעמוד לטקסט הנכון. 0 = זהה. רצף רווחים נחשב לרווח אחד.

בדיקת התצוגה: כל שורה בסט, לא רק המתויגות, מוצגת באלגוריתם התצוגה של Unicode (שורה עם עברית בפסקה מימין לשמאל, שורה בלי עברית משמאל לימין) ומושווית לסדר האותיות בעמוד. שורה שנכשלת היא שורה שהפלט שלה לא ייראה כמו העמוד. שורה דו-משמעית היא שורה שיותר מקריאה אחת שלה נראית בדיוק כמו העמוד (למשל "1 Onboarding" ו-"Onboarding 1"), והקורא בחר לפי ברירת מחדל. ההסבר המלא ב-harness/display_check.py וב-hebrew_pdf/logical_order.py.

המרחק הוא גבול תחתון: כשהקורא שובר שורה מאוד (למשל מדביק אליה עמודה שכנה), שורה אחרת בעמוד יכולה להיות קרובה יותר מהשורה שלה, ואז המרחק קטן מהשגיאה האמיתית. בעמודה "השורה הקרובה ביותר בפלט" רואים מול איזו שורה נמדד. המדד הראשי הוא מספר השורות הזהות.

## שורות מתויגות

| מספר | קובץ | עמוד | תוצאה | מרחק | הטקסט הנכון | השורה הקרובה ביותר בפלט |
|---|---|---|---|---|---|---|
| 1 | chatbot-spec-form_gdocs.pdf | 1 | ✗ | 2 | הסבר על טופס איפיון ראשוני לצ׳טבוט (לפני דיאגרמה) | הסבר על טופס איפיון ראשוני לצ׳טבוט( לפני דיאגרמה) |
| 2 | chatbot-spec-form_gdocs.pdf | 1 | ✗ | 2 | שאלה? \| תשובת הלקוח | שאלה? תשובת הלקוח |
| 3 | chatbot-spec-form_gdocs.pdf | 1 | ✓ זהה | 0 | (לדוגמה: סינון לידים, קביעת פגישות, תמיכה טכנית, |  |
| 4 | doc-6p_gdocs.pdf | 1 | ✓ זהה | 0 | הארכיטקטורה של המערכת ב-Backend וב-Frontend בנויה בצורה הבאה, שלב אחרי שלב: |  |
| 5 | doc-6p_gdocs.pdf | 1 | ✗ | 2 | 1. חיבור פייסבוק (Meta OAuth): המשתמש נכנס למערכת ומבצע FB Connect. ה-Backend | 1. חיבור פייסבוק( Meta OAuth): המשתמש נכנס למערכת ומבצע FB Connect. ה-Backend |
| 6 | doc-6p_gdocs.pdf | 1 | ✓ זהה | 0 | שומר את ה-Access Token המאובטח ב-Supabase DB. |  |
| 7 | mentoros-overview_weasyprint.pdf | 1 | ✓ זהה | 0 | OSMentor |  |
| 8 | mentoros-overview_weasyprint.pdf | 1 | ✗ | 9 | מודולים מרכזיים \| שאלות Deep Dive \| זיכרון ארוך טווח \| שכבות בטיחות | מודולים מרכזייםשאלות Deep Diveזיכרון ארוך טווחשכבות בטיחות |
| 9 | mentoros-overview_weasyprint.pdf | 3 | ✗ | 4 | 1 Onboarding אישי — 10 שאלות | Onboarding 1 אישי — 10 שאלות |
| 10 | mentoros-overview_weasyprint.pdf | 4 | ✓ זהה | 0 | כל החלטה נשמרת ואפשר לעקוב: פתוחה ← הוחלט ← נבחנה בדיעבד |  |
| 11 | mentoros-overview_weasyprint.pdf | 8 | ✗ | 17 | Backend \| FastAPI + Python 3.12 \| שרת API מהיר, async, type-safe | FastAPI + Python 3.12 Backend שרת API מהיר, async, type-safe |
| 12 | price-quote_weasyprint.pdf | 1 | ✗ | 6 | הצעת מחיר QT-00011 | ה צ ע ת מ ח י ר QT-00011 |
| 13 | price-quote_weasyprint.pdf | 1 | ✓ זהה | 0 | הופקה ב-11/05/2026 · בתוקף עד 25/05/2026 |  |
| 14 | price-quote_weasyprint.pdf | 1 | ✓ זהה | 0 | טלפון: 0543978620 |  |
| 15 | price-quote_weasyprint.pdf | 1 | ✓ זהה | 0 | amirbiron@gmail.com |  |
| 16 | price-quote_weasyprint.pdf | 1 | ✓ זהה | 0 | https://amirbiron.github.io/Automation-made-easy/ |  |
| 17 | price-quote_weasyprint.pdf | 2 | ✗ | 5 | סה"כ לתשלום | תנאי תשלום |
| 18 | price-quote_weasyprint.pdf | 4 | ✓ זהה | 0 | תקלות שמקורן בצד שלישי (Meta, Telegram, Google, ספקי תשתית), שאינן בשליטת החברה. |  |
| 19 | social-publisher-setup_weasyprint.pdf | 1 | ✓ זהה | 0 | כל מה שצריך להכין לפני שמתחילים — Meta, Google Drive ו-Sheets |  |
| 20 | social-publisher-setup_weasyprint.pdf | 2 | ✓ זהה | 0 | IG\_USER\_ID — נמצא ב-Business Settings ← Instagram Accounts. |  |
| 21 | doc-4p_weasyprint.pdf | 1 | ✗ | 17 | עוזרים לעסק שלך לחשוב אחרת | עוזרים לעסק שלך לחשוב אחרתמסמך אפיון דרישות |
| 22 | doc-4p_weasyprint.pdf | 1 | ✓ זהה | 0 | תאריך: 11.06.2026 |  |
| 23 | doc-2p_weasyprint.pdf | 1 | ✓ זהה | 0 | פרויקט Campaign AI · שותפות טכנולוגית · המטרה: להפוך "חזון" ל"עסקה שאפשר להעריך" |  |
| 24 | doc-2p_weasyprint.pdf | 1 | ✓ זהה | 0 | מהרווח הנקי / מהמחזור / או בעלות בחברה (equity)? ההבדל עצום — אחוז מרווח נעלם אם אין רווח; equity שווה משהו גם במכירת החברה. |  |
| 25 | gps-book_indesign.pdf | 2 | ✓ זהה | 0 | בעולם שמשתנה במהירות ואינו ממתין למתלבטים, |  |
| 26 | gps-book_indesign.pdf | 2 | ✓ זהה | 0 | אנו חברה לניהול עסקים פרטיים (קטנים ובינוניים). מתמחים באבחון, |  |
| 27 | gps-book_indesign.pdf | 2 | ✓ זהה | 0 | אנו מתגאים במעל 90% הצלחה |  |
| 28 | marketing-flyer_illustrator.pdf | 1 | ✗ | 3 | מאות חברות בחרו ב GPS לעסקים | מאות חברות בחרו ב ⟨U+001D⟩⟨U+001E⟩⟨U+001F⟩ לעסקים |
| 29 | marketing-flyer_illustrator.pdf | 1 | ✗ | 3 | ומה איתך? | ומהא יתך⟨U+001C⟩ |
| 30 | marketing-flyer_illustrator.pdf | 1 | ✗ | 10 | בניית תוכנית עבודה | פיתוח תהליכי עבודה |
| 31 | marketing-flyer_illustrator.pdf | 1 | ✗ | 12 | פרסום במדיות, יחסי | פיתוח תשתיות |
| 32 | presentation_canva.pdf | 2 | ✗ | 24 | מאיה קארגי \| 058-7999120 \| OOHMYWEB.COM | מאיה קארגי \| OOHMYWEB.COM \| 058-7999120 |
| 33 | presentation_canva.pdf | 4 | ✓ זהה | 0 | המדריך הזה נולד מתוך ההבנה (וצורך אמיתי שלי להתייעלות בכתיבת תוכן) |  |
| 34 | presentation_canva.pdf | 23 | ✗ | 1 | הכלים להפוך את החזון הזה למציאות 💫 | הכלים להפוך את החזון הזה למציאות ⟨U+009A⟩ |
| 35 | optimization_chrome.pdf | 1 | ✗ | 2 | ← זה הזמן לבחון ולדייק את הפרומפט (ההנחיה) של ה-AI בפאנל. | ← זה הזמן לבחון ולדייק את הפרומפט( ההנחיה) של ה-AI בפאנל. |
| 36 | optimization_chrome.pdf | 1 | ✓ זהה | 0 | 3. דיוק ה-AI |  |
| 37 | financial-report-q2-2025_aspose.pdf | 35 | ✗ | 1 | רב בריח (08) תעשיות בע"מ | רב בריח ( 08) תעשיות בע"מ |
| 38 | financial-report-q2-2025_aspose.pdf | 35 | ✗ | 12 | הכנסות ממכירות \| \| 366,343 \| 300,306\* \| 178,881 \| 145,921\* \| 633,833\* | הכנסות ממכירות 366,343 300,306\* 178,881 145,921\* 633,833\* |
| 39 | financial-report-q2-2025_aspose.pdf | 35 | ✗ | 12 | הוצאות (הכנסות) אחרות \| \| (189) \| (5,203) \| (139) \| 18 \| (9,995)\* | הוצאות (הכנסות) אחרות (189) (5,203) (139) 18 (9,995)\* |
| 40 | financial-report-q2-2025_aspose.pdf | 35 | ✗ | 14 | רווח (הפסד) מפעילויות נמשכות \| \| (206) \| (29,396) \| (2,073) \| (20,496) \| (53,464) | רווח (הפסד) מפעילו יו ת נמשכו ת (206) (29,396) (2,073) (20,496) (53,464) |

ממתינות לאישור: אין

לא ברורות: אין

## לפי קובץ

אותיות סופיות: אחוז המילים (מבין אלה שיש בהן אות סופית) שהאות הסופית לא בתחילתן; גבוה = טוב. פיסוק בתחילת שורה: אחוז השורות העבריות שמתחילות בסימן פיסוק; נמוך = טוב. שתיהן בדיקות עקיפות מהאב-טיפוס, ו-100% בהן אינו הוכחה שהפלט נכון.

| קובץ | תוכנה | עמודים | אותיות סופיות | פיסוק בתחילת שורה | בדיקת תצוגה נכשלה | דו-משמעיות | מאושרות | זהות | מרחק |
|---|---|---|---|---|---|---|---|---|---|
| chatbot-spec-form_gdocs.pdf | gdocs | 4 | 100% | 0% | 0 | 0 | 3 | 1 | 4 |
| doc-2p_weasyprint.pdf | weasyprint | 2 | 100% | 0% | 0 | 0 | 2 | 2 | 0 |
| doc-4p_weasyprint.pdf | weasyprint | 4 | 100% | 0% | 0 | 0 | 2 | 1 | 17 |
| doc-6p_gdocs.pdf | gdocs | 6 | 100% | 0% | 1 | 12 | 3 | 2 | 2 |
| financial-report-q2-2025_aspose.pdf | aspose | 66 | 100% | 0% | 0 | 1 | 4 | 0 | 39 |
| gps-book_indesign.pdf | indesign | 16 | 100% | 0% | 0 | 2 | 3 | 3 | 0 |
| marketing-flyer_illustrator.pdf | illustrator | 1 | 100% | 0% | 0 | 0 | 4 | 0 | 28 |
| mentoros-overview_weasyprint.pdf | weasyprint | 8 | 100% | 0% | 1 | 4 | 5 | 2 | 30 |
| optimization_chrome.pdf | chrome | 1 | 100% | 0% | 0 | 0 | 2 | 1 | 2 |
| presentation_canva.pdf | canva | 24 | 100% | 0% | 0 | 23 | 3 | 1 | 25 |
| price-quote_weasyprint.pdf | weasyprint | 7 | 100% | 0% | 0 | 1 | 7 | 5 | 11 |
| social-publisher-setup_weasyprint.pdf | weasyprint | 2 | 100% | 0% | 0 | 3 | 2 | 2 | 0 |

## לפי עמוד

<details>
<summary>כל העמודים</summary>

| קובץ | עמוד | שורות עם טקסט | אותיות שדולגו | סוגריים בלי צורה | בדיקת תצוגה נכשלה | דו-משמעיות | אותיות סופיות | פיסוק בתחילת שורה |
|---|---|---|---|---|---|---|---|---|
| chatbot-spec-form_gdocs.pdf | 1 | 18 | 0 | 0 | 0 | 0 | 100% | 0% |
| chatbot-spec-form_gdocs.pdf | 2 | 15 | 0 | 0 | 0 | 0 | 100% | 0% |
| chatbot-spec-form_gdocs.pdf | 3 | 17 | 0 | 0 | 0 | 0 | 100% | 0% |
| chatbot-spec-form_gdocs.pdf | 4 | 7 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-2p_weasyprint.pdf | 1 | 28 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-2p_weasyprint.pdf | 2 | 4 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-4p_weasyprint.pdf | 1 | 31 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-4p_weasyprint.pdf | 2 | 28 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-4p_weasyprint.pdf | 3 | 33 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-4p_weasyprint.pdf | 4 | 1 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-6p_gdocs.pdf | 1 | 36 | 0 | 0 | 0 | 1 | 100% | 0% |
| doc-6p_gdocs.pdf | 2 | 34 | 0 | 0 | 0 | 1 | 100% | 0% |
| doc-6p_gdocs.pdf | 3 | 34 | 0 | 0 | 0 | 3 | 100% | 0% |
| doc-6p_gdocs.pdf | 4 | 38 | 0 | 0 | 1 | 6 | 100% | 0% |
| doc-6p_gdocs.pdf | 5 | 36 | 0 | 0 | 0 | 0 | 100% | 0% |
| doc-6p_gdocs.pdf | 6 | 32 | 0 | 0 | 0 | 1 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 1 | 2 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 2 | 8 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 3 | 2 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 4 | 24 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 5 | 37 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 6 | 40 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 7 | 35 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 8 | 32 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 9 | 43 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 10 | 38 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 11 | 38 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 12 | 25 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 13 | 61 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 14 | 39 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 15 | 23 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 16 | 44 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 17 | 49 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 18 | 44 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 19 | 49 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 20 | 35 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 21 | 33 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 22 | 41 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 23 | 28 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 24 | 17 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 25 | 38 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 26 | 49 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 27 | 32 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 28 | 2 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 29 | 3 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 30 | 15 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 31 | 26 | 0 | 0 | 0 | 1 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 32 | 17 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 33 | 25 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 34 | 41 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 35 | 48 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 36 | 30 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 37 | 31 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 38 | 18 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 39 | 46 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 40 | 45 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 41 | 32 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 42 | 36 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 43 | 22 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 44 | 40 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 45 | 27 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 46 | 39 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 47 | 31 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 48 | 19 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 49 | 33 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 50 | 31 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 51 | 13 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 52 | 2 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 53 | 5 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 54 | 12 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 55 | 22 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 56 | 25 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 57 | 35 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 58 | 42 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 59 | 50 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 60 | 45 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 61 | 17 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 62 | 21 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 63 | 42 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 64 | 1 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 65 | 39 | 0 | 0 | 0 | 0 | 100% | 0% |
| financial-report-q2-2025_aspose.pdf | 66 | 43 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 1 | 0 (אין טקסט) | 0 | 0 | 0 | 0 | — | — |
| gps-book_indesign.pdf | 2 | 24 | 0 | 0 | 0 | 1 | 100% | 0% |
| gps-book_indesign.pdf | 3 | 0 (אין טקסט) | 0 | 0 | 0 | 0 | — | — |
| gps-book_indesign.pdf | 4 | 18 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 5 | 20 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 6 | 43 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 7 | 6 | 0 | 0 | 0 | 0 | — | — |
| gps-book_indesign.pdf | 8 | 31 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 9 | 12 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 10 | 35 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 11 | 7 | 0 | 0 | 0 | 0 | — | — |
| gps-book_indesign.pdf | 12 | 21 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 13 | 24 | 0 | 0 | 0 | 0 | 100% | 0% |
| gps-book_indesign.pdf | 14 | 9 | 0 | 0 | 0 | 0 | — | — |
| gps-book_indesign.pdf | 15 | 3 | 0 | 0 | 0 | 0 | 100% | — |
| gps-book_indesign.pdf | 16 | 5 | 0 | 0 | 0 | 1 | 100% | 0% |
| marketing-flyer_illustrator.pdf | 1 | 65 | 0 | 0 | 0 | 0 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 1 | 9 | 0 | 0 | 0 | 1 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 2 | 15 | 0 | 0 | 1 | 1 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 3 | 19 | 0 | 0 | 0 | 1 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 4 | 19 | 0 | 0 | 0 | 0 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 5 | 19 | 0 | 0 | 0 | 1 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 6 | 19 | 0 | 0 | 0 | 0 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 7 | 8 | 0 | 0 | 0 | 0 | 100% | 0% |
| mentoros-overview_weasyprint.pdf | 8 | 12 | 0 | 0 | 0 | 0 | 100% | 0% |
| optimization_chrome.pdf | 1 | 14 | 0 | 0 | 0 | 0 | 100% | 0% |
| presentation_canva.pdf | 1 | 4 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 2 | 15 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 3 | 19 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 4 | 16 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 5 | 21 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 6 | 16 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 7 | 23 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 8 | 31 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 9 | 20 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 10 | 28 | 0 | 0 | 0 | 0 | 100% | 0% |
| presentation_canva.pdf | 11 | 18 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 12 | 18 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 13 | 25 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 14 | 23 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 15 | 23 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 16 | 20 | 0 | 0 | 0 | 1 | 100% | 5% |
| presentation_canva.pdf | 17 | 22 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 18 | 21 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 19 | 25 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 20 | 17 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 21 | 22 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 22 | 11 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 23 | 20 | 0 | 0 | 0 | 1 | 100% | 0% |
| presentation_canva.pdf | 24 | 13 | 0 | 0 | 0 | 1 | 100% | 0% |
| price-quote_weasyprint.pdf | 1 | 15 | 0 | 0 | 0 | 1 | 100% | 0% |
| price-quote_weasyprint.pdf | 2 | 18 | 0 | 0 | 0 | 0 | 100% | 0% |
| price-quote_weasyprint.pdf | 3 | 40 | 0 | 0 | 0 | 0 | 100% | 0% |
| price-quote_weasyprint.pdf | 4 | 39 | 0 | 0 | 0 | 0 | 100% | 0% |
| price-quote_weasyprint.pdf | 5 | 40 | 0 | 0 | 0 | 0 | 100% | 0% |
| price-quote_weasyprint.pdf | 6 | 42 | 0 | 0 | 0 | 0 | 100% | 0% |
| price-quote_weasyprint.pdf | 7 | 20 | 0 | 0 | 0 | 0 | 100% | 0% |
| social-publisher-setup_weasyprint.pdf | 1 | 24 | 0 | 0 | 0 | 3 | 100% | 0% |
| social-publisher-setup_weasyprint.pdf | 2 | 6 | 0 | 0 | 0 | 0 | 100% | 0% |

</details>
