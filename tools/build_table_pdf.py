"""
בונה PDF מקובץ Markdown עם טבלאות, ומפיק ממנו "דף תשובות" לכל תא.

שימוש: python tools/build_table_pdf.py SOURCE.md OUT.pdf OUT.truth.json
העמוד: A4 לרוחב, מימין לשמאל, גופן DejaVu Sans. תאים ארוכים נשברים לכמה שורות בכוונה.
דף התשובות נגזר מה-HTML שנבנה, כך שהוא בדיוק הטקסט שכל תא מציג. תווי עיצוב בלתי נראים
(הקטגוריה Cf ב-Unicode, כמו RLM) יורדים מהטקסט של כל תא: הם לא מוצגים, ולכן הם לא חלק ממה
שהתא מציג. במקור יש שניים כאלה, בתיאורים של PUSH_LOCAL_TIMEOUT_SECONDS ו-MCP_RATE_LIMIT_PER_MINUTE.
דורש: pip install -r requirements-dev.txt (הגרסאות שבנו את הקובץ שבריפו)
"""
import json, re, sys, unicodedata
from html.parser import HTMLParser
import markdown, weasyprint


def cell_text(text):
    """הטקסט שהתא מציג: בלי תווי Cf, ועם רווח אחד במקום כל רצף של רווחים."""
    return re.sub(r"\s+", " ", "".join(ch for ch in text if unicodedata.category(ch) != "Cf")).strip()

src = open(sys.argv[1], encoding="utf-8").read()
# ::: type ... ::: -> div blocks (markdown inside kept via md_in_html)
src = re.sub(r"^::: *(\w+)\s*\n(.*?)\n:::\s*$",
             lambda m: f'<div class="callout {m.group(1)}" markdown="1">\n\n{m.group(2)}\n\n</div>',
             src, flags=re.S | re.M)
body = markdown.markdown(src, extensions=["tables", "fenced_code", "md_in_html"])

css = """
@page { size: A4 landscape; margin: 18mm 14mm; @bottom-center { content: counter(page); font-size: 9pt; } }
html { direction: rtl; }
body { font-family: 'DejaVu Sans'; font-size: 10pt; line-height: 1.45; }
h1 { font-size: 20pt; } h2 { font-size: 15pt; margin-top: 18pt; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin: 8pt 0; font-size: 8.5pt; }
th, td { border: 0.6pt solid #999; padding: 3pt 4pt; text-align: right; vertical-align: top; overflow-wrap: anywhere; }
th { background: #eee; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
code { font-family: 'DejaVu Sans Mono'; font-size: 0.92em; }
pre { direction: ltr; text-align: left; background: #f5f5f5; padding: 6pt; font-size: 8pt; white-space: pre-wrap; }
.callout { border-right: 3pt solid #888; background: #f7f7f7; padding: 4pt 8pt; margin: 6pt 0; }
"""
html = f'<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>'
weasyprint.HTML(string=html).write_pdf(sys.argv[2])

# ground truth: exactly the text each rendered table cell shows
class T(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self.row = None; self.cell = None; self.section = None
    def handle_starttag(self, tag, a):
        if tag == "table": self.tables.append({"section": self.section, "rows": []})
        elif tag == "tr": self.row = []
        elif tag in ("td", "th"): self.cell = []
        elif tag == "h2": self.section = ""
    def handle_endtag(self, tag):
        if tag in ("td", "th"): self.row.append(cell_text("".join(self.cell))); self.cell = None
        elif tag == "tr": self.tables[-1]["rows"].append(self.row); self.row = None
    def handle_data(self, d):
        if self.cell is not None: self.cell.append(d)
        elif self.section == "" or (self.section is not None and self.lasttag == "h2"):
            if self.lasttag == "h2": self.section = (self.section or "") + d.strip()
p = T(); p.feed(html)
json.dump({"source": "environment.md (CodeBot docs/environment-variables)", "producer": "WeasyPrint",
           "note": "header row is rows[0] of each table; cell text = what the rendered cell shows",
           "tables": p.tables}, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("tables", len(p.tables), "rows", sum(len(t["rows"]) - 1 for t in p.tables),
      [(t["section"], len(t["rows"]) - 1, len(t["rows"][0])) for t in p.tables])
