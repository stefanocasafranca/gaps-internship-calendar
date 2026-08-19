# GAPS Internship Calendar

The 16-week calendar for the Generative AI in Public Service (GAPS) internship,
Fall 2026. ACC Center for Government and Civic Service + The Public Service Desk.

## This calendar is the source of truth

As of July 31, 2026, this file is the single source of truth for the program
schedule. The syllabus, the curriculum, the 16-week blueprint and the Master
Board cards in the GAPS-PSSF vault are all downstream of it. When a vault
document and this calendar disagree, ask before changing either one: the vault
doc may be recording a decision the calendar has not caught up to yet.

## What is here

| File | What it is |
|---|---|
| `index.html` | The entire calendar. Self-contained, no build step, no dependencies. |
| `middleware.js` | HTTP Basic Auth at the Vercel edge. Runs before any file is served. |

## Hosting

Live at https://gaps-calendar.vercel.app behind HTTP Basic Auth.
Note: `gaps-dash.vercel.app` is a different site and is not ours.

Deploy:

```
vercel --prod --yes
```

This GitHub repository is the code home and version history. It does not serve
the site. `middleware.js` is Vercel edge middleware and does nothing on GitHub
Pages, so publishing this repo to Pages would put the calendar online with no
password. The repository is private for the same reason: the credentials are
in `middleware.js` in plaintext.
