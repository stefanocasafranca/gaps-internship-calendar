# Builds the GAPS deliverables schedule PDF from the calendar.
# Deliverable TEXT is extracted from ~/code/gaps-calendar/index.html (source of truth).
# Due DATES are derived here, from the calendar's own week ranges and stated rules.
import io, os, re, sys
from datetime import date, timedelta
from bs4 import BeautifulSoup

SRC = os.path.expanduser("~/code/gaps-calendar/index.html")
OUT = sys.argv[1]
soup = BeautifulSoup(io.open(SRC, encoding="utf-8").read(), "html.parser")
# The calendar ships with <div id="calendar" class="hum-active">, so on screen the
# .hum-only variants show and the .standard-only variants are hidden. Print has no
# toggle, so drop the hidden branch here or the document prints two contradictory
# schedules for every week that has both.
for _el in soup.select(".standard-only, .standard-only-block"):
    _el.decompose()

T = lambda x: re.sub(r"\s+", " ", x.get_text(" ", strip=True)) if x else ""

# --- Due-date model -----------------------------------------------------------
# Rule 1 (STATED in the calendar): the weekly activity report / journal is due Sunday night.
# Rule 2 (DERIVED): work produced at a Saturday session is due when that session closes.
#         The close time is read from the last time-block in that week's schedule.
# Rule 3 (DERIVED): everything else in a week is due 11:59pm on that week's closing Sunday.
SUNDAY = {0: date(2026, 8, 21), 1: date(2026, 8, 23), 2: date(2026, 8, 30), 3: date(2026, 9, 6),
          4: date(2026, 9, 13), 5: date(2026, 9, 20), 6: date(2026, 9, 27), 7: date(2026, 10, 4),
          8: date(2026, 10, 11), 9: date(2026, 10, 18), 10: date(2026, 10, 25), 11: date(2026, 11, 1),
          12: date(2026, 11, 8), 13: date(2026, 11, 15), 14: date(2026, 11, 22), 15: date(2026, 11, 29),
          16: date(2026, 12, 5)}
SATURDAY = {1: date(2026, 8, 22), 2: date(2026, 8, 29), 4: date(2026, 9, 12), 6: date(2026, 9, 26),
            8: date(2026, 10, 10), 10: date(2026, 10, 24), 12: date(2026, 11, 7),
            14: date(2026, 11, 21), 16: date(2026, 12, 5)}
# Wk 0 closes Fri Aug 21 (the calendar's own checkpoint); Wk 16 closes Sat Dec 5
# (the closing ceremony is the last day, nothing carries into a Sunday). Rest close Sunday.
CLOSE_DOW = {0: 4, 16: 5}
for w, d in SUNDAY.items():
    assert d.weekday() == CLOSE_DOW.get(w, 6), ("bad closing day", w, d)
for w, d in SATURDAY.items():
    assert d.weekday() == 5, ("not a Saturday", w, d)

def fmt(d, t):
    return "%s %s %d, %s" % (d.strftime("%a"), d.strftime("%b"), d.day, t)

# --- Tier model ---------------------------------------------------------------
# Three tiers, in the order they are tested. First match wins; default is "flex".
#   client : someone outside GAPS is in the room or receives it. The date cannot move
#            without telling the client or a real end user.
#   hard   : an internal gate. The next phase does not start until it is done.
#   flex   : learning, setup, upkeep, reflection. Slipping costs nobody anything.
# This is the ONLY place tiers are decided. Move a line between lists to re-tier it.
TIERS = [
    ("client", r"journey map|Named problem per team|usability (testing )?sessions?|"
               r"3 usability|guerrilla testing|tested against a real user|hi-fi task-based testing|"
               r"[Cc]lient handoff|Final demo|App deployed and online"),
    ("hard",   r"Feature freeze|Go/No-Go|readiness determination|[Rr]eadiness gate|"
               r"deployed to VertexAI|smoke test|Release candidate|Section 508|"
               r"pivot/persevere|IA v1 finalized|Tech stack decision|MVP requirements|"
               r"Integration decision|Repo initialized|Weekly activity report|"
               r"Diamond 1 (report|findings)|Working core flow|Internal demo|"
               r"Final documentation submission|Final quantitative usability report|"
               r"Issue backlog|Stability checklist|Functional prototype"),
]
TIER_LABEL = {"client": "Client-facing", "hard": "Hard deadline", "flex": "Internal, flexible"}

def tier(text):
    for name, pat in TIERS:
        if re.search(pat, text):
            return name
    return "flex"

ROLES = ["Researchers", "Designers", "Developers", "Project Managers"]
def owner(text):
    for r in ROLES:
        if re.search(r"\b%s\b" % r, text):
            return r
    if re.search(r"\beach intern\b|\bevery intern\b", text, re.I):
        return "Each intern"
    return "Team"

def items(blob):
    """Split a deliverables blob into discrete line items without breaking quotes."""
    blob = re.sub(r"^Deliverables:\s*", "", blob).strip()
    parts, buf, depth = [], "", 0
    for i, ch in enumerate(blob):
        buf += ch
        if ch == '"':
            depth ^= 1
        if ch == "." and not depth:
            nxt = blob[i + 1:i + 3]
            if nxt[:1] in (" ", "") and (len(nxt) < 2 or nxt[1].isupper() or nxt[1].isdigit() or nxt[1] == '"'):
                parts.append(buf.strip()); buf = ""
    if buf.strip():
        parts.append(buf.strip())
    out = []
    for p in parts:
        p = p.strip()
        if len(p) > 2:
            out.append(p[0].upper() + p[1:] if p[0].islower() else p)
    return out

def deferred(text):
    """Items the calendar itself dates forward ("first stand-up by Week 3") are not
    due at the session that names them. Return the week they actually land in."""
    m = re.search(r"by (?:Week|Wk)\s*(\d+)", text, re.I)
    return int(m.group(1)) if m else None

# --- Extract ------------------------------------------------------------------
weeks = []
for c in soup.select_one("#calendar").select(".week-card"):
    n = int(c.get("data-week"))
    full = T(c.select_one(".schedule-deliverables"))
    session_txt, async_txt = full, ""
    m = re.search(r"Async \(Mon-Fri\):\s*", full)
    if m:
        session_txt, async_txt = full[:m.start()], full[m.end():]
    times = [T(t) for t in c.select(".time-range")]
    close = ""
    if times:
        last = times[-1]
        close = last.split("-")[-1].strip()
        if close and not re.search(r"[ap]m", close, re.I):
            hh = close.split(":")[0]
            close += "am" if (hh.isdigit() and 9 <= int(hh) <= 11) else "pm"
    weeks.append({"n": n, "title": T(c.select_one(".week-content h5")),
                  "badges": [T(b) for b in c.select(".format-badge")],
                  "session": items(session_txt), "async": items(async_txt),
                  "close": close})

rows = []  # flat chronological list: (date, time, week, owner, text, kind, tier)
for w in weeks:
    n = w["n"]
    sat, sun = SATURDAY.get(n), SUNDAY[n]
    if n == 0:
        for it in w["session"]:
            rows.append((sun, "5:00pm", n, owner(it), it, "setup", tier(it)))
        continue
    for it in w["session"]:
        fwd = deferred(it)
        if fwd is not None and fwd in SUNDAY:
            rows.append((SUNDAY[fwd], "11:59pm", n, owner(it), it, "deferred", tier(it)))
        elif sat:
            rows.append((sat, w["close"] or "5:00pm", n, owner(it), it, "session", tier(it)))
        else:
            rows.append((sun, "11:59pm", n, owner(it), it, "week", tier(it)))
    for it in w["async"]:
        rows.append((sun, "11:59pm", n, owner(it), it, "async", tier(it)))
    if n >= 1:
        rows.append((sun, "11:59pm", n, "Each intern", "Weekly activity report / journal.", "standing", "hard"))
rows.sort(key=lambda r: (r[0], r[1]))

# --- Emit ---------------------------------------------------------------------
E = []; a = E.append
a("""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>GAPS Deliverables Schedule, Fall 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  @page{size:letter;margin:.62in .66in .7in}
  :root{--ink:#15171c;--ink-2:#3d424b;--ink-3:#5a606b;--rule:#dcd8d0;--rule-soft:#ebe8e2;
        --gold:#8a6d24;--gold-line:#c9a55c;--wash:#f7f5f1;--flag:#9d4a34}
  *{box-sizing:border-box}
  html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body{margin:0;background:#fff;color:var(--ink);font-family:'Outfit',-apple-system,sans-serif;
       font-size:9.9pt;line-height:1.58;orphans:3;widows:3;text-rendering:geometricPrecision}
  strong,b{font-weight:600}
  p{margin:0 0 .5em}
  .cover{padding:.28in 0 .42in;border-bottom:2px solid var(--ink);margin-bottom:24px}
  .cover .org{font-size:8.2pt;letter-spacing:.20em;text-transform:uppercase;color:var(--ink-3);font-weight:500;margin-bottom:16px}
  .cover h1{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:44pt;line-height:.98;letter-spacing:-.015em;margin:0 0 10px}
  .cover .sub{font-family:'Cormorant Garamond',Georgia,serif;font-size:16.5pt;font-style:italic;color:var(--ink-2)}
  h2{font-family:'Cormorant Garamond',Georgia,serif;font-weight:600;font-size:21pt;margin:0 0 3px}
  .sec{margin:0 0 28px}
  .sec-rule{height:1px;background:var(--rule);margin:0 0 13px}
  .lede{color:var(--ink-2);max-width:74ch;margin-bottom:12px}
  .rule-row{display:grid;grid-template-columns:86px 1fr;gap:0 16px;padding:6px 0;border-top:1px solid var(--rule-soft)}
  .rule-row:first-of-type{border-top:1px solid var(--rule)}
  .rule-row .k{font-size:7.7pt;font-weight:600;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);padding-top:2px}
  .rule-row .v{max-width:72ch}
  table{width:100%;border-collapse:collapse;font-size:8.9pt}
  thead th{font-size:7.4pt;letter-spacing:.15em;text-transform:uppercase;color:var(--ink-3);font-weight:600;
     text-align:left;padding:0 10px 6px 0;border-bottom:1px solid var(--ink)}
  tbody td{padding:6px 10px 6px 0;border-bottom:1px solid var(--rule-soft);vertical-align:top}
  tbody tr{break-inside:avoid}
  td.due{white-space:nowrap;font-weight:600;font-variant-numeric:tabular-nums;width:118px}
  td.tm{white-space:nowrap;color:var(--ink-2);font-variant-numeric:tabular-nums;width:56px}
  td.wk{white-space:nowrap;color:var(--ink-3);width:46px;font-variant-numeric:tabular-nums}
  td.own{white-space:nowrap;color:var(--ink-2);width:104px}
  tr.gate td{background:var(--wash)}
  tr.gate td.due{color:var(--gold)}
  .wblock{margin:0 0 22px;break-inside:avoid}
  .whead{display:grid;grid-template-columns:104px 1fr;gap:0 18px;padding-bottom:8px;margin-bottom:9px;
     border-bottom:1px solid var(--rule);break-after:avoid}
  .wnum{font-family:'Cormorant Garamond',Georgia,serif;font-size:32pt;line-height:.82;font-weight:600;font-variant-numeric:tabular-nums}
  .wnum small{display:block;font-family:'Outfit',sans-serif;font-size:7.2pt;font-weight:600;letter-spacing:.19em;
     text-transform:uppercase;color:var(--ink-3);margin-bottom:5px}
  .wtitle{font-family:'Cormorant Garamond',Georgia,serif;font-size:19pt;font-weight:600;line-height:1.1;margin:0}
  .badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px}
  .badge{font-size:7.6pt;font-weight:600;letter-spacing:.04em;padding:2.5px 8px;border:1px solid var(--rule);
     border-radius:2px;color:var(--ink-2);background:var(--wash)}
  .badge.inperson{border-color:var(--gold-line);color:var(--gold);background:rgba(201,165,92,.10)}
  .drow{display:grid;grid-template-columns:104px 1fr;gap:0 18px;padding:6px 0;border-top:1px solid var(--rule-soft);break-inside:avoid}
  .drow .k{font-size:8.2pt;font-weight:600;color:var(--ink-2);font-variant-numeric:tabular-nums;line-height:1.35}
  .drow .k em{display:block;font-style:normal;font-weight:400;font-size:7.6pt;color:var(--ink-3)}
  .drow .v{max-width:72ch}
  .drow .v .own{font-weight:600;color:var(--gold)}
  .flag{border-left:1px solid var(--flag);padding:2px 0 2px 12px;margin:0 0 10px;color:var(--ink-2);max-width:74ch}
  .flag b{color:var(--flag)}
  .tier{display:inline-block;font-size:7pt;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
     padding:1.5px 6px;border-radius:2px;white-space:nowrap;line-height:1.5}
  .t-client{background:#9d4a34;color:#fff}
  .t-hard{background:transparent;color:var(--ink);border:1px solid var(--ink)}
  .t-flex{background:var(--wash);color:var(--ink-3);border:1px solid var(--rule)}
  td.tier-c{width:96px}
  .legend{display:grid;grid-template-columns:96px 1fr;gap:0 16px;padding:7px 0;border-top:1px solid var(--rule-soft)}
  .legend:first-of-type{border-top:1px solid var(--rule)}
  .legend .v{max-width:72ch}
  .count{font-size:8.4pt;color:var(--ink-3);margin:8px 0 0}
</style></head><body>""")

a('<div class="cover"><div class="org">Center for Government and Civic Service &nbsp;&middot;&nbsp; The Public Service Desk</div>')
a('<h1>Deliverables Schedule</h1><div class="sub">GAPS Internship &mdash; Every deliverable, owner and due date, Fall 2026</div></div>')

a('<div class="sec"><h2>How Due Dates Work</h2><div class="sec-rule"></div>')
a('<p class="lede">Deliverable wording is taken from the GAPS calendar, the program\'s source of truth. Due dates and times are applied on top of it using three rules, because the calendar states what is due but not always when.</p>')
for k, v in [("Rule 1", "<b>Stated in the calendar.</b> The weekly activity report and journal are due Sunday night. Read as 11:59pm."),
             ("Rule 2", "<b>Derived.</b> Anything produced at a Saturday session is due when that session closes. The close time is read from the last block in that Saturday's schedule, not assumed."),
             ("Rule 3", "<b>Derived.</b> Everything else in a week is due 11:59pm on that week's closing Sunday."),
             ("Exception", "Where the calendar dates something forward itself, that wins. \"First stand-up by Week 3\" is named at the kickoff but lands at the close of Week 3, and is filed there."),
             ("Owners", "Assigned only where the calendar names a role. Everything else is a team deliverable.")]:
    a('<div class="rule-row"><div class="k">%s</div><div class="v">%s</div></div>' % (k, v))
a('</div>')

a('<div class="sec"><h2>Three Tiers</h2><div class="sec-rule"></div>')
a('<p class="lede">Not every deliverable carries the same weight. Each line is tiered, and the tier is what tells you whether a date can move.</p>')
for t, d in [("client", "Someone outside GAPS is in the room or receives it: the client, her founders, or a real end user. <b>These dates cannot move without telling someone outside the program.</b>"),
             ("hard", "An internal gate. The next phase does not start until it is done, so the date is fixed even though nobody outside GAPS sees it."),
             ("flex", "Learning, setup, upkeep, reflection. Real work, and still expected, but slipping a few days costs nobody anything. <b>Say this out loud to the cohort.</b> An intern who thinks every line is a hard deadline will burn out on the ones that never mattered.")]:
    a('<div class="legend"><div><span class="tier t-%s">%s</span></div><div class="v">%s</div></div>' % (t, TIER_LABEL[t], d))
counts = {}
for r in rows:
    counts[r[6]] = counts.get(r[6], 0) + 1
a('<p class="count">%d deliverables total: %d client-facing, %d hard internal deadlines, %d internal and flexible.</p>'
  % (len(rows), counts.get("client", 0), counts.get("hard", 0), counts.get("flex", 0)))
a('<p class="lede" style="margin-top:10px;font-size:8.6pt">Tiering is a judgement call, not something the calendar states. This is a first pass. It lives in one table in the generator, so re-tiering a line is a one-line edit, not a rebuild.</p>')
a('</div>')

a('<div class="sec"><h2>Flags</h2><div class="sec-rule"></div>')
a('<p class="flag"><b>Week 15 falls on Thanksgiving week.</b> Nov 23 to 27, 2026, with Thanksgiving on Thursday Nov 26. Week 15 carries the release candidate build, final documentation submission and the Section 508 check, all currently due Sunday Nov 29. That is the heaviest documentation week of the program landing on the week ACC is closed. Needs a decision before kickoff: move the work, move the date, or accept it.</p>')
a('<p class="flag"><b>Week 0 is deliberately soft, and the calendar used to overstate it.</b> Corrected Aug 19: the only thing genuinely expected before Aug 22 is a working PSD Google Workspace account. The laptop, the toolchain, and the Jira and Confluence accounts are best effort, and anyone who arrives with an unfinished install finishes it in the room. Everything in Week 0 is tiered flexible for that reason. The Aug 21 date is the calendar\'s own checkpoint, kept as a target rather than a gate.</p>')
a('<p class="flag"><b>Week 16 closes on the Saturday, not a Sunday.</b> Sat Dec 5 is the closing ceremony and the last day of the program, so nothing carries into a Sunday afterwards.</p>')
a('</div>')

def short_table(title, lede, keep):
    sel = [r for r in rows if r[6] in keep]
    a('<div class="sec"><h2>%s</h2><div class="sec-rule"></div>' % title)
    a('<p class="lede">%s</p>' % lede)
    a('<table><thead><tr><th>Due</th><th>Time</th><th>Wk</th><th>Owner</th><th>Deliverable</th></tr></thead><tbody>')
    for d, t, n, ow, txt, kind, tr in sel:
        a('<tr><td class="due">%s</td><td class="tm">%s</td><td class="wk">%02d</td><td class="own">%s</td><td>%s</td></tr>'
          % ("%s %s %d" % (d.strftime("%a"), d.strftime("%b"), d.day), t, n, ow, txt))
    a('</tbody></table></div>')

short_table("Client-Facing Deliverables",
            "The short list. Someone outside GAPS is in the room or receives these, so slipping one is a conversation with the client, not an internal adjustment. Everything here is a Saturday or a scheduled session with real users.",
            {"client"})
short_table("Hard Internal Deadlines",
            "Gates. The next phase does not start until these are done. Nobody outside the program sees them, and the dates still do not move.",
            {"hard"})

a('<div class="sec"><h2>All Deliverables, In Order</h2><div class="sec-rule"></div>')
a('<table><thead><tr><th>Due</th><th>Time</th><th>Wk</th><th>Tier</th><th>Owner</th><th>Deliverable</th></tr></thead><tbody>')
for d, t, n, ow, txt, kind, tr in rows:
    cls = ' class="gate"' if kind == "session" else ""
    a('<tr%s><td class="due">%s</td><td class="tm">%s</td><td class="wk">%02d</td>'
      '<td class="tier-c"><span class="tier t-%s">%s</span></td><td class="own">%s</td><td>%s</td></tr>'
      % (cls, "%s %s %d" % (d.strftime("%a"), d.strftime("%b"), d.day), t, n, tr, TIER_LABEL[tr], ow, txt))
a('</tbody></table>')
a('<p class="lede" style="margin-top:10px;font-size:8.6pt">Shaded rows are due in the room at a Saturday session. Everything else is due by 11:59pm on the date shown.</p></div>')

a('<div class="sec"><h2>By Week</h2><div class="sec-rule"></div></div>')
for w in weeks:
    n = w["n"]
    a('<div class="wblock"><div class="whead"><div class="wnum"><small>Week</small>%02d</div><div>' % n)
    a('<div class="badges">')
    for b in w["badges"]:
        cls = "badge inperson" if ("Sat" in b or "Full Day" in b or "Half Day" in b) else "badge"
        a('<span class="%s">%s</span>' % (cls, b))
    a('</div><div class="wtitle">%s</div></div></div>' % w["title"])
    mine = [r for r in rows if r[2] == n]
    if not mine:
        a('<div class="drow"><div class="k">&mdash;</div><div class="v">No deliverable recorded for this week.</div></div>')
    for d, t, _, ow, txt, kind, tr in mine:
        due = "%s %s %d<em>%s</em>" % (d.strftime("%a"), d.strftime("%b"), d.day, t)
        a('<div class="drow"><div class="k">%s</div><div class="v"><span class="tier t-%s">%s</span> '
          '<span class="own">%s</span> &nbsp;%s</div></div>' % (due, tr, TIER_LABEL[tr], ow, txt))
    a('</div>')

a("</body></html>")
io.open(OUT, "w", encoding="utf-8").write("\n".join(E))
print("weeks:", len(weeks), "deliverable rows:", len(rows))
