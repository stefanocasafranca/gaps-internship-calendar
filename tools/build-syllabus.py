# Builds a flat, syllabus-style print edition of the GAPS calendar.
# Reads ~/code/gaps-calendar/index.html (the source of truth) and emits syllabus.html.
# Nothing is retyped: every string below comes out of the calendar itself.
import io, os, re, sys
from bs4 import BeautifulSoup, NavigableString

SRC = os.path.expanduser("~/code/gaps-calendar/index.html")
OUT = sys.argv[1]

soup = BeautifulSoup(io.open(SRC, encoding="utf-8").read(), "html.parser")

# The calendar ships with <div id="calendar" class="hum-active">, so on screen the
# .hum-only variants show and the .standard-only variants are hidden. Print has no
# toggle, so drop the hidden branch here or the document prints two contradictory
# schedules for every week that has both.
for _el in soup.select(".standard-only, .standard-only-block"):
    _el.decompose()

ALLOWED = {"strong", "b", "em", "i", "a", "br", "u"}

def inline(node, drop_first_label=False):
    """Inner HTML with only inline emphasis kept. Block wrappers are flattened."""
    if node is None:
        return ""
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
            continue
        name = child.name
        if drop_first_label and name == "span" and "block-label" in (child.get("class") or []):
            drop_first_label = False
            continue
        if name in ALLOWED:
            attrs = ""
            if name == "a" and child.get("href"):
                attrs = ' href="%s"' % child["href"]
            out.append("<%s%s>%s</%s>" % (name, attrs, inline(child), name))
        else:
            out.append(inline(child))
    return re.sub(r"\s+", " ", "".join(out)).strip()

def text(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""

# ---------------------------------------------------------------- front matter
cadence_note = text(soup.select_one(".cadence div[style*='text-align:center']"))
hours = [(text(l).rsplit(" ", 1)[0].strip(), text(l.select_one(".target-hrs")))
         for l in soup.select(".target-bar-legend .target-label")]
hours = [(n.replace(h, "").strip() or n, h) for n, h in hours]
esc = [(text(s.select_one("h4")), text(s.select_one(".meta")))
       for s in soup.select(".escalation-step")]
esc_note = text(soup.select_one(".escalation-note"))

# ---------------------------------------------------------------------- weeks
PHASE_INK = {"Setup": "#4a4e58", "Discovery": "#2f5a4f", "Testing": "#3d5673",
             "Iteration": "#6b4d2e", "Refinement": "#5c4069", "Deployment": "#33513f"}
blocks, phase = [], None
for el in soup.select_one("#calendar").find_all(recursive=False):
    cls = el.get("class") or []
    if "phase-header" in cls:
        phase = {"name": text(el.select_one("h3")),
                 "weeks": text(el.select_one(".phase-weeks")),
                 "epoch": text(el.select_one(".epoch-badge"))}
        phase["ink"] = PHASE_INK.get(phase["name"], "#4a4e58")
        blocks.append(("phase", phase))
    elif "week-card" in cls:
        w = {"num": el.get("data-week"), "phase": phase,
             "badges": [text(b) for b in el.select(".format-badge")],
             "title": text(el.select_one(".week-content h5")),
             "paras": [], "timeline": [], "detail": [], "hours": [],
             "deliv_top": text(el.select_one(".week-main .deliverables")),
             "deliv": "", "source": "", "hum": None}
        for p in el.select(".week-content p, .week-content .shrink-note"):
            pcls = p.get("class") or []
            kind = "venue" if "week-venue" in pcls else ("light" if "shrink-note" in pcls else "body")
            w["paras"].append((kind, inline(p)))
        for tb in el.select(".schedule-dropdown .time-block"):
            label = tb.select_one(".block-label")
            lcls = " ".join(label.get("class") or []) if label else ""
            kind = ("break" if "label-break" in lcls else
                    "hum" if "label-hum" in lcls else "gaps")
            w["timeline"].append({"time": text(tb.select_one(".time-range")),
                                  "label": text(label), "kind": kind,
                                  "desc": inline(tb.select_one(".time-desc"), True)})
        for ds in el.select(".schedule-dropdown .detail-section"):
            sec = {"label": text(ds.select_one(".detail-label")), "paras": [], "roles": []}
            content = ds.select_one(".detail-content")
            for p in content.find_all("p", recursive=False):
                sec["paras"].append(inline(p))
            for rb in content.select(".role-block"):
                sec["roles"].append({"role": text(rb.select_one(".role-tag")),
                                     "items": [inline(li) for li in rb.select("li")]})
            for ul in content.find_all("ul", recursive=False):
                sec["roles"].append({"role": "", "items": [inline(li) for li in ul.select("li")]})
            w["detail"].append(sec)
        for it in el.select(".schedule-dropdown .hrs-item"):
            w["hours"].append((text(it.select_one(".hrs-label")),
                               text(it).replace(text(it.select_one(".hrs-label")), "").strip()))
        w["deliv"] = inline(el.select_one(".schedule-deliverables"))
        w["source"] = text(el.select_one(".schedule-source")).replace("Source:", "").strip()
        hr = el.select_one(".hum-row")
        if hr:
            w["hum"] = {"label": text(hr.select_one(".hum-label")),
                        "prompt": text(hr.select_one(".hum-prompt")),
                        "detail": inline(hr.select_one(".hum-detail"))}
        blocks.append(("week", w))

# ----------------------------------------------------------------------- emit
E = []
a = E.append
a("""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>GAPS Internship Syllabus, Fall 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  @page { size: letter; margin: 0.62in 0.66in 0.7in; }
  :root{
    --ink:#15171c; --ink-2:#3d424b; --ink-3:#5a606b;
    --rule:#dcd8d0; --rule-soft:#ebe8e2; --paper:#fff; --wash:#f7f5f1;
    --gold:#8a6d24; --gold-line:#c9a55c; --hum:#9d4a34;
  }
  *{box-sizing:border-box}
  html{-webkit-print-color-adjust:exact; print-color-adjust:exact}
  body{margin:0;background:var(--paper);color:var(--ink);orphans:3;widows:3;
       font-family:'Outfit',-apple-system,'Segoe UI',sans-serif;
       font-size:9.3pt;line-height:1.5;font-weight:400;
       text-rendering:geometricPrecision}
  a{color:var(--gold);text-decoration:none;border-bottom:.5px solid rgba(138,109,36,.45)}
  strong,b{font-weight:600;color:var(--ink)}
  em,i{font-style:italic}
  p{margin:0 0 .5em}
  p:last-child{margin-bottom:0}

  /* ---- title block ---- */
  .cover{padding:.28in 0 .42in;border-bottom:2px solid var(--ink);margin-bottom:24px}
  .cover .org{font-size:8.2pt;letter-spacing:.20em;text-transform:uppercase;
       color:var(--ink-3);font-weight:500;margin-bottom:16px}
  .cover h1{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;
       font-size:46pt;line-height:.98;letter-spacing:-.015em;margin:0 0 10px}
  .cover .sub{font-family:'Cormorant Garamond',Georgia,serif;font-size:17pt;
       font-style:italic;color:var(--ink-2);margin-bottom:22px}
  .cover .facts{display:grid;grid-template-columns:repeat(4,1fr);gap:0 20px;font-size:8.5pt;
       color:var(--ink-2);border-top:1px solid var(--rule);padding-top:14px}
  .cover .facts b{display:block;font-size:7.4pt;letter-spacing:.13em;
       text-transform:uppercase;color:var(--ink-3);font-weight:500;margin-bottom:2px}

  /* ---- generic section ---- */
  h2{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:21pt;
     letter-spacing:-.005em;margin:0 0 3px;color:var(--ink)}
  .sec{margin:0 0 30px}
  .sec-rule{height:1px;background:var(--rule);margin:0 0 13px}
  .lede{color:var(--ink-2);max-width:74ch;margin-bottom:12px}

  /* ---- definition rows: the syllabus workhorse ---- */
  .row{display:grid;grid-template-columns:100px 1fr;gap:0 16px;
       padding:4.5px 0;border-top:1px solid var(--rule-soft);break-inside:avoid}
  .row:first-of-type{border-top:1px solid var(--rule)}
  .row .k{font-size:8.2pt;font-weight:600;letter-spacing:.02em;color:var(--ink-2);
       padding-top:1px;font-variant-numeric:tabular-nums}
  .row .v{color:var(--ink);max-width:72ch}
  .row .v .lab{font-weight:600;color:var(--ink)}
  .row.is-break .k,.row.is-break .v{color:var(--ink-3)}
  .row.is-hum .k{color:var(--hum)}
  .row.is-hum .v .lab{color:var(--hum)}

  /* ---- weeks ---- */
  /* every week opens a page; the phase strip rides along so orientation never
     depends on a divider you passed eight pages ago */
  .phasebar{display:flex;align-items:baseline;gap:10px;padding-bottom:6px;margin-bottom:12px;
     border-bottom:1px solid currentColor;font-size:8pt;letter-spacing:.15em;
     text-transform:uppercase;font-weight:600}
  .phasebar .pw{margin-left:auto;letter-spacing:.11em;font-weight:500;color:var(--ink-3)}
  .phasebar .ep{letter-spacing:.11em;font-weight:600}

  .week{margin:0;break-inside:auto;break-before:page;page-break-before:always}
  .week.first{break-before:auto;page-break-before:auto}

  /* contents */
  .toc{break-after:page;page-break-after:always}
  .toc-row{display:grid;grid-template-columns:46px 1fr 152px 30px;gap:0 14px;padding:5.5px 0;
     border-top:1px solid var(--rule-soft);align-items:baseline}
  .toc-row:first-of-type{border-top:1px solid var(--rule)}
  .toc-row .n{font-family:'Cormorant Garamond',Georgia,serif;font-size:14pt;font-weight:600;
     font-variant-numeric:tabular-nums;line-height:1}
  .toc-row .t{font-weight:500}
  .toc-row .d{font-size:8.4pt;color:var(--ink-3);text-align:right;font-variant-numeric:tabular-nums}
  .toc-row .p{font-size:8.6pt;color:var(--ink-2);text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
  .toc-phase{font-size:7.6pt;letter-spacing:.16em;text-transform:uppercase;font-weight:600;
     margin:14px 0 4px;padding-top:9px;border-top:1px solid var(--ink)}
  .frontsec{break-after:page;page-break-after:always}
  .whead{display:grid;grid-template-columns:100px 1fr;gap:0 16px;
     padding-bottom:7px;margin-bottom:8px;border-bottom:1px solid var(--rule);break-after:avoid}
  .wnum{font-family:'Cormorant Garamond',Georgia,serif;font-size:30pt;line-height:.82;
     font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
  .wnum small{display:block;font-family:'Outfit',sans-serif;font-size:7.2pt;font-weight:600;
     letter-spacing:.19em;text-transform:uppercase;color:var(--ink-3);margin-bottom:5px}
  .badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:7px}
  .badge{font-size:7.6pt;font-weight:600;letter-spacing:.04em;padding:2.5px 8px;
     border:1px solid var(--rule);border-radius:2px;color:var(--ink-2);background:var(--wash)}
  .badge.inperson{border-color:var(--gold-line);color:var(--gold);background:rgba(201,165,92,.10)}
  .week h4{font-family:'Cormorant Garamond',Georgia,serif;font-size:18pt;font-weight:600;
     line-height:1.1;letter-spacing:-.01em;margin:0}
  .summary{max-width:74ch;color:var(--ink-2);margin-bottom:9px}
  .summary p{margin-bottom:.45em}
  .venue{border-left:1px solid var(--gold-line);padding:1px 0 1px 12px;color:var(--ink-2)}
  .light{color:var(--ink-3);font-size:9.3pt}

  .sub-h{font-size:7.7pt;font-weight:600;letter-spacing:.17em;text-transform:uppercase;
     color:var(--ink-3);margin:11px 0 5px;break-after:avoid}
  .roles{display:grid;grid-template-columns:100px 1fr;gap:0 16px;padding:4px 0;
     border-top:1px solid var(--rule-soft);break-inside:avoid}
  .roles .r{font-size:8.2pt;font-weight:600;color:var(--ink-2);line-height:1.35;word-spacing:.06em}
  .roles ul{margin:0;padding-left:15px;max-width:72ch}
  .roles li{margin-bottom:2px}
  .roles li::marker{color:var(--gold-line)}

  .meta-row{display:grid;grid-template-columns:100px 1fr;gap:0 16px;padding:4.5px 0;
     border-top:1px solid var(--rule-soft);break-inside:avoid}
  .meta-row .k{font-size:7.7pt;font-weight:600;letter-spacing:.15em;text-transform:uppercase;
     color:var(--ink-3);padding-top:2px}
  .meta-row .v{max-width:72ch;color:var(--ink)}
  .meta-row.src .v{color:var(--ink-3);font-size:8.6pt}
  .wmeta{break-inside:avoid}
  .meta-row.hum .k{color:var(--hum)}
  .meta-row.hum .v{color:var(--ink-2)}
  .meta-row.hum .q{font-family:'Cormorant Garamond',Georgia,serif;font-style:italic;
     font-size:12.5pt;color:var(--hum);display:block;margin-bottom:2px}
  .hrs{display:flex;flex-wrap:wrap;gap:0 20px;font-size:8.8pt;color:var(--ink-2)}
  .hrs b{color:var(--ink);font-weight:600}
</style></head><body>""")

# cover
a('<div class="cover"><div class="org">Center for Government and Civic Service &nbsp;&middot;&nbsp; The Public Service Desk</div>')
a('<h1>GAPS Internship</h1>')
a('<div class="sub">Generative AI in Public Service &mdash; 16-Week Syllabus, Fall 2026</div>')
a('<div class="facts">')
for k, v in [("Term", "Aug 22 &ndash; Dec 5, 2026"), ("Commitment", "~20 hours per week"),
             ("In person", "9 Saturdays, ACC Highland Campus, Room 2226"),
             ("Weekdays", "Async and virtual, team-scheduled")]:
    a('<div><b>%s</b>%s</div>' % (k, v))
a('</div></div>')

# contents. Page numbers are filled in by a second render pass: the tokens below are
# replaced once the first pass reveals which page each week actually opens on.
a('<div class="sec toc"><h2>Contents</h2><div class="sec-rule"></div>')
a('<div class="toc-row"><div class="n"></div><div class="t">Weekly Cadence</div><div class="d"></div><div class="p">@@PG_CAD@@</div></div>')
a('<div class="toc-row"><div class="n"></div><div class="t">Escalation Path</div><div class="d"></div><div class="p">@@PG_ESC@@</div></div>')
cur = None
for kind, b in blocks:
    if kind == "phase":
        cur = b
        a('<div class="toc-phase" style="color:%s">%s &nbsp;&middot;&nbsp; %s &nbsp;&middot;&nbsp; %s</div>'
          % (b["ink"], b["name"], b["weeks"], b["epoch"]))
        continue
    dates = b["badges"][0] if b["badges"] else ""
    dates = dates.split("\u00b7")[0].strip() if "\u00b7" in dates else dates
    a('<div class="toc-row"><div class="n">%s</div><div class="t">%s</div><div class="d">%s</div><div class="p">@@PG_W%s@@</div></div>'
      % (b["num"].zfill(2), b["title"], dates, b["num"]))
a('</div>')

# cadence
a('<div class="sec frontsec"><h2>Weekly Cadence</h2><div class="sec-rule"></div>')
a('<p class="lede">%s</p>' % cadence_note)
a('<div class="sub-h">Target hours per week</div>')
for n, h in hours:
    a('<div class="row"><div class="k">%s</div><div class="v">%s</div></div>' % (h, n))
a('<div class="row"><div class="k"><b>~20</b></div><div class="v"><b>Weekly total</b></div></div>')
a('</div>')

# escalation
a('<div class="sec frontsec"><h2>Escalation Path</h2><div class="sec-rule"></div>')
a('<p class="lede">%s</p>' % esc_note)
for i, (h, m) in enumerate(esc, 1):
    a('<div class="row"><div class="k">Step %d</div><div class="v"><span class="lab">%s</span> %s</div></div>' % (i, h, m))
a('</div>')

# weeks
cur_phase, first = None, True
for kind, b in blocks:
    if kind == "phase":
        cur_phase = b
        continue
    w = b
    a('<div class="week%s">' % (" first" if first else ""))
    first = False
    if cur_phase:
        a('<div class="phasebar" style="color:%s"><span>%s</span><span class="ep">&middot; %s</span>'
          '<span class="pw">%s</span></div>'
          % (cur_phase["ink"], cur_phase["name"], cur_phase["epoch"], cur_phase["weeks"]))
    a('<div class="whead"><div class="wnum"><small>Week</small>%s</div><div>' % w["num"].zfill(2))
    a('<div class="badges">')
    for bd in w["badges"]:
        cls = "badge inperson" if ("Sat" in bd or "Full Day" in bd or "Half Day" in bd) else "badge"
        a('<span class="%s">%s</span>' % (cls, bd))
    a('</div><h4>%s</h4></div></div>' % w["title"])

    if w["paras"]:
        a('<div class="summary">')
        for k, html in w["paras"]:
            cls = {"venue": ' class="venue"', "light": ' class="light"'}.get(k, "")
            a('<p%s>%s</p>' % (cls, html))
        a('</div>')

    if w["timeline"]:
        a('<div class="sub-h">Session schedule</div>')
        for t in w["timeline"]:
            cls = " is-break" if t["kind"] == "break" else (" is-hum" if t["kind"] == "hum" else "")
            desc = (" " + t["desc"]) if t["desc"] else ""
            a('<div class="row%s"><div class="k">%s</div><div class="v"><span class="lab">%s</span>%s</div></div>'
              % (cls, t["time"], t["label"], desc))

    for sec in w["detail"]:
        a('<div class="sub-h">%s</div>' % sec["label"])
        for p in sec["paras"]:
            a('<div class="row"><div class="k"></div><div class="v">%s</div></div>' % p)
        for r in sec["roles"]:
            a('<div class="roles"><div class="r">%s</div><ul>%s</ul></div>'
              % (r["role"], "".join("<li>%s</li>" % i for i in r["items"])))

    a('<div class="wmeta">')
    if w["hours"]:
        a('<div class="meta-row"><div class="k">Hours</div><div class="v"><div class="hrs">')
        for lab, val in w["hours"]:
            a('<span>%s <b>%s</b></span>' % (lab.rstrip(":"), val))
        a('</div></div></div>')
    deliv = w["deliv"] or w["deliv_top"]
    if deliv:
        a('<div class="meta-row"><div class="k">Deliverables</div><div class="v">%s</div></div>'
          % re.sub(r"^<strong>Deliverables:</strong>\s*", "", deliv))
    if w["hum"]:
        a('<div class="meta-row hum"><div class="k">HUM opener</div><div class="v"><span class="q">%s</span>%s %s</div></div>'
          % (w["hum"]["prompt"], w["hum"]["label"] + ".", w["hum"]["detail"]))
    if w["source"]:
        a('<div class="meta-row src"><div class="k">Source</div><div class="v">%s</div></div>' % w["source"])
    a('</div></div>')

a("</body></html>")
io.open(OUT, "w", encoding="utf-8").write("\n".join(E))
print("weeks:", sum(1 for k, _ in blocks if k == "week"), "-> ", OUT)
