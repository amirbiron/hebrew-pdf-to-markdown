"""Mechanical order check for labels.md.

For each label: display its "correct text" through the Unicode bidi algorithm
(as a Hebrew paragraph) and compare to the glyphs of the matching page line
sorted by x (what the page actually shows, left to right). Whitespace is
ignored and brackets are folded to one symbol, so the check is about order
and content of the visible characters only.
"""
import ctypes, re, sys
from collections import Counter
import pypdfium2 as pdfium, pypdfium2.raw as raw
from bidi.algorithm import get_display

PDFS = sys.argv[1]
LABELS = sys.argv[2]

def parse(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        if not re.match(r"^\| *\d+ *\|", line):
            continue
        cells = [c.replace("\\|", "|").replace("\\\\", "\\").strip()
                 for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        rows.append(dict(n=int(cells[0]), file=cells[1], page=int(cells[2]), out=cells[3], truth=cells[4], status=cells[5]))
    return rows

def page_rows(pdf, idx):
    tp = pdf[idx].get_textpage(); x = ctypes.c_double(); y = ctypes.c_double(); ch = []
    for i in range(tp.count_chars()):
        c = tp.get_text_range(i, 1)
        if not c or c in "\r\n":
            continue
        b = tp.get_charbox(i)
        if not raw.FPDFText_GetCharOrigin(tp, i, x, y):
            continue
        ch.append((c, (b[0] + b[2]) / 2, y.value))
    ch.sort(key=lambda c: -c[2]); rows = []
    for c in ch:
        if rows and abs(rows[-1][0][2] - c[2]) <= 2: rows[-1].append(c)
        else: rows.append([c])
    return ["".join(c[0] for c in sorted(r, key=lambda c: c[1])) for r in rows]

BR = str.maketrans({k: "#" for k in "()[]{}<>"})
def norm(s):
    return re.sub(r"\s+", "", s).translate(BR)

def bracket_problem(s):
    depth = 0
    for c in s:
        if c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0: return "סוגר לפני פותח"
    return "סוגריים לא מאוזנים" if depth else None

cache = {}
for r in parse(LABELS):
    key = (r["file"], r["page"])
    if key not in cache:
        cache[key] = page_rows(pdfium.PdfDocument(f"{PDFS}/{r['file']}"), r["page"] - 1)
    vis_rows = cache[key]
    t = r["truth"]
    # two readings of "|": cell separator (each cell is displayed on its own, cells laid right to left)
    # or a literal character that is part of the text
    as_cells = norm("".join(get_display(c, base_dir="R") for c in reversed(re.split(r"\s*\|\s*", t))))
    as_text = norm(get_display(t, base_dir="R"))
    cands = [as_cells, as_text]
    best = max(vis_rows, key=lambda v: max(sum((Counter(norm(v)) & Counter(c)).values()) for c in cands))
    v = norm(best); shown = as_cells
    if any(c == v for c in cands): verdict = "OK (שורה שלמה)"
    elif any(c in v for c in cands): verdict = "OK (חלק מהשורה)"
    else:
        missing = Counter(shown) - Counter(v); extra = Counter(v) - Counter(shown)
        verdict = "סדר שונה" if not missing else f"חסר בעמוד: {''.join(missing.elements())[:20]!r}"
    bp = bracket_problem(r["truth"])
    print(f"{r['n']:>2} | {verdict}{' | ' + bp if bp else ''}")
