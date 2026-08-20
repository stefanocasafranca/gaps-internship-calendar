"""Render the syllabus with a correct contents page.

Page numbers cannot be known before layout, and layout shifts once the numbers are
printed, so this measures and re-renders until the contents page agrees with the
document it describes. It refuses to emit a PDF whose contents page is wrong.
"""
import io, re, subprocess, sys

SP, OUT = sys.argv[1], sys.argv[2]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MAX_PASSES = 6

def build():
    subprocess.run([sys.executable, SP + "/build_syllabus.py", SP + "/syllabus.html"],
                   check=True, capture_output=True)
    return io.open(SP + "/syllabus.html", encoding="utf-8").read()

def render(html, pdf):
    io.open(SP + "/_render.html", "w", encoding="utf-8").write(html)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=20000", "--print-to-pdf=" + pdf,
                    "file://" + SP + "/_render.html"], capture_output=True)
    return subprocess.run(["pdftotext", "-layout", pdf, "-"],
                          capture_output=True, text=True).stdout.split("\f")

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip().lower()

def page_of(pages, needle):
    hits = [i + 1 for i, p in enumerate(pages) if needle in norm(p)]
    return hits[-1] if hits else None

tok = build()
entries = [("@@PG_CAD@@", "weekly cadence"), ("@@PG_ESC@@", "escalation path")]
entries += [("@@PG_W%s@@" % n, norm(t)) for t, _d, n in
            re.findall(r'<div class="t">([^<]+)</div><div class="d">(.*?)</div><div class="p">@@PG_W(\d+)@@', tok, re.S)]

pages = render(tok, SP + "/_pass.pdf")
for i in range(1, MAX_PASSES + 1):
    html = tok
    for token, needle in entries:
        pg = page_of(pages, needle)
        assert pg, "contents entry never appears in the PDF: " + needle
        html = html.replace(token, str(pg))
    assert "@@PG_" not in html, "unfilled contents token"
    pages = render(html, OUT)
    wrong = [(n, c) for (t, n), c in
             zip(entries, re.findall(r'<div class="p">(\d+)</div>', html))
             if page_of(pages, n) != int(c)]
    if not wrong:
        print("contents correct after pass %d: %d entries, %d pages" % (i, len(entries), len(pages)))
        sys.exit(0)
    print("pass %d: %d contents entries still wrong, re-measuring" % (i, len(wrong)))
print("FAILED to converge after %d passes" % MAX_PASSES)
sys.exit(1)
