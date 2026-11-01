"""
בונה PDF מקובץ Markdown, ומפיק ממנו "דף תשובות": המבנה של העמוד, בלוק אחרי בלוק.

שימוש (מתיקיית הריפו):
    python -m tools.build_table_pdf SOURCE.md OUT.pdf OUT.truth.json [--landscape] [--table-font PT]
                                    [--engine weasyprint|chrome]

ה-HTML: המקור עובר ב-cmark-gfm, המפרסר ש-GitHub מציג בו Markdown (ב-CodeKeeper המסמכים נכתבים באותו
תחביר). python-markdown, שבנה את הקובץ עד סבב 5, דורש הזחה של ארבעה רווחים לרשימה פנימית, ולכן רשימה
שמוזחת בשלושה (כמו במסמך האפיון) יצאה אצלו שטוחה. בלוק ":::" (סוג) הופך ל-div של תיבה, וכדי שה-div יישאר
ב-HTML המפרסר רץ עם CMARK_OPT_UNSAFE (בלעדיו HTML גולמי מוחלף בהערה; cmarkgfm/cmark.py).

העמוד: A4 לאורך, או לרוחב עם --landscape, מימין לשמאל, גופן DejaVu Sans. מילה לא נשברת באמצע: שבירת
שורה רק במקום שבו Unicode מתיר אותה (רווח, אחרי מקף ואחרי לוכסן; UAX #14), כמו במסמכים אמיתיים. עד
סבב 5ב התאים נבנו עם overflow-wrap: anywhere, ושמות משתנים ארוכים נשברו באמצע רק בגלל זה. הטבלה
ברוחב הדף ובפריסה אוטומטית: כל עמודה רחבה לפחות כמו המילה הארוכה בה. כשסכום המילים הארוכות של כל
העמודות רחב מהדף, הטבלה חורגת ממנו, והפתרון הוא גודל האות בטבלה (--table-font, בנקודות; ברירת
המחדל 8.5). הפקודה שבנתה כל קובץ, עם הגודל שלו, ב-testset/ground_truth/README.md.

המנוע: WeasyPrint (ברירת המחדל), או Chrome (--engine chrome), שמדפיס את אותו HTML בדיוק במצב headless:
--print-to-pdf, ו---no-pdf-header-footer כדי שלא יתווספו לעמוד תאריך וכתובת. שני הדגלים מוגדרים
ב-Chromium ב-components/headless/command_handler/headless_command_switches.cc, והדפסה מהשורה משתמשת
בגודל העמוד מה-CSS (preferCSSPageSize ב-headless_command.js). הנתיב ל-Chrome: --chrome, או google-chrome
או chromium מה-PATH. כך לאותו מקור יש שני קבצים משתי תוכנות, עם אותו דף תשובות, ורואים אם כשל תלוי
בתוכנה.

דף התשובות נגזר מה-HTML שנבנה (harness/html_structure.py), ולכן הוא בדיוק מה שהעמוד מציג: כותרות עם
הרמה שלהן, פסקאות, פריטי רשימה עם עומק הקינון, ציטוטים, קוד וטבלאות, לפי הסדר. המבנה שלו מתואר
ב-testset/ground_truth/README.md.

דורש: pip install -r requirements-dev.txt (הגרסאות שבנו את הקבצים שבריפו)
"""
import argparse
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cmarkgfm

from harness.html_structure import block_to_json, parse

CSS = """
@page { size: A4 %(orientation)s; margin: 18mm 14mm; @bottom-center { content: counter(page); font-size: 9pt; } }
html { direction: rtl; }
body { font-family: 'DejaVu Sans'; font-size: 10pt; line-height: 1.45; }
h1 { font-size: 20pt; } h2 { font-size: 15pt; margin-top: 18pt; } h3 { font-size: 12pt; }
table { width: 100%%; border-collapse: collapse; margin: 8pt 0; font-size: %(table_font)spt; }
th, td { border: 0.6pt solid #999; padding: 3pt 4pt; text-align: right; vertical-align: top; }
th { background: #eee; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
code { font-family: 'DejaVu Sans Mono'; font-size: 0.92em; }
pre { direction: ltr; text-align: left; background: #f5f5f5; padding: 6pt; font-size: 8pt; white-space: pre-wrap; }
blockquote { border-right: 3pt solid #bbb; margin: 6pt 0; padding: 0 8pt; color: #333; }
.callout { border-right: 3pt solid #888; background: #f7f7f7; padding: 4pt 8pt; margin: 6pt 0; }
"""


def build_html(source: str, landscape: bool, table_font: float, title: str) -> str:
    # ::: type ... ::: -> div של תיבה. בלוק HTML נמשך עד שורה ריקה (GFM, "HTML blocks", סוג 6), ולכן שורה
    # ריקה אחרי כל תגית: אחרי <div> כדי שהתוכן יישאר Markdown, ואחרי </div> כדי שהשורה הבאה (למשל כותרת)
    # לא תיבלע בבלוק ותוצג כטקסט גולמי
    source = re.sub(r"^::: *(\w+)[ \t]*\n(.*?)\n:::[ \t]*$",
                    lambda m: f'<div class="callout {m.group(1)}">\n\n{m.group(2)}\n\n</div>\n',
                    source, flags=re.S | re.M)
    body = cmarkgfm.github_flavored_markdown_to_html(source, options=cmarkgfm.Options.CMARK_OPT_UNSAFE)
    css = CSS % {"orientation": "landscape" if landscape else "portrait", "table_font": f"{table_font:g}"}
    head = f'<meta charset="utf-8"><title>{html.escape(title)}</title><style>{css}</style>'
    return f'<!doctype html><html lang="he" dir="rtl"><head>{head}</head><body>{body}</body></html>'


def write_pdf(page_html: str, out: Path, engine: str, chrome: str | None) -> None:
    """כותבת את ה-PDF, או זורקת RuntimeError עם הסיבה. אין מצב שבו הקובץ חסר והפונקציה מצליחה."""
    if engine == "weasyprint":
        import weasyprint
        weasyprint.HTML(string=page_html).write_pdf(str(out))
    else:
        binary = chrome or shutil.which("google-chrome") or shutil.which("chromium")
        if not binary:
            raise RuntimeError("לא נמצא Chrome: אין google-chrome או chromium ב-PATH, ולא ניתן --chrome")
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "page.html"
            page.write_text(page_html, encoding="utf-8")
            out.unlink(missing_ok=True)
            done = subprocess.run([binary, "--headless", "--no-pdf-header-footer", f"--print-to-pdf={out.resolve()}",
                                   page.as_uri()], capture_output=True, text=True, timeout=300)
            if done.returncode != 0:
                raise RuntimeError(f"Chrome נכשל (קוד {done.returncode}): {done.stderr.strip()[-500:]}")
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"לא נוצר קובץ PDF ב-{out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.build_table_pdf", description=__doc__.split("\n\n")[1])
    parser.add_argument("source", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("truth", type=Path)
    parser.add_argument("--landscape", action="store_true", help="A4 לרוחב (ברירת המחדל: לאורך)")
    parser.add_argument("--table-font", type=float, default=8.5, help="גודל האות בטבלאות, בנקודות (ברירת המחדל: 8.5)")
    parser.add_argument("--engine", choices=("weasyprint", "chrome"), default="weasyprint")
    parser.add_argument("--chrome", help="הנתיב ל-Chrome (ברירת המחדל: google-chrome או chromium מה-PATH)")
    args = parser.parse_args(argv)

    if not (math.isfinite(args.table_font) and args.table_font > 0):
        parser.error("--table-font: מספר חיובי של נקודות")
    page_html = build_html(args.source.read_text(encoding="utf-8"), args.landscape, args.table_font, args.source.stem)
    write_pdf(page_html, args.pdf, args.engine, args.chrome)
    blocks = parse(page_html).structure
    truth = {
        "source": args.source.name,
        "note": "the page's structure in order, derived from the HTML the PDF was built from (harness/html_structure.py)",
        "blocks": [block_to_json(block) for block in blocks],
    }
    args.truth.write_text(json.dumps(truth, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    kinds = [block.kind for block in blocks]
    tables = [block for block in blocks if block.kind == "table"]
    print({kind: kinds.count(kind) for kind in sorted(set(kinds))},
          "table rows", sum(len(t.rows) - 1 for t in tables), [(len(t.rows) - 1, len(t.rows[0])) for t in tables])
    return 0


if __name__ == "__main__":
    sys.exit(main())
