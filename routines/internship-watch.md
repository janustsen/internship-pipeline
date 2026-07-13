# Routine: internship-watch (daily, cloud — judge + discovery)

Janus Tsen's daily internship opening-detector for elite finance / consulting /
strategy / corp-dev / quant / business roles (Summer 2027 + sophomore tracks).
Use TODAY'S ACTUAL DATE. You are in a fresh clone of `janustsen/internship-pipeline`
(default branch `main`), unattended. Goal: surface top-tier internships **the day
they open**, verified, by push — high recall, near-zero false positives.

**Why you don't run the collector:** the local job (`bin/run.sh`, keyless ATS +
Workday + Handshake) collects and pushes `todays_candidates.json` — because this
cloud sandbox blocks outbound egress to the job-feed hosts. You JUDGE that
artifact and DISCOVER what has no machine feed. Your two tools reach the open web
(WebFetch/WebSearch go through the proxy, not the blocked sandbox egress).

## 1. Read the collected candidates
Open `todays_candidates.json` at the repo root — the NEW, roster-gated postings the
local job found (each: `tier_hint`, `category`, `company`, `title`, `location`,
`link`, `source`, `posted`). If it's missing or `candidate_count` is 0, don't stop —
the discovery pass below can still surface openings. Note its `run_date`: if it's
not today, say so in one line (the Mac may not have collected yet) and judge what's
there anyway.

## 2. Discovery net (the firms with no machine feed)
Several marquee firms have NO keyless feed and won't be in the artifact — chiefly
**MBB (McKinsey, Bain, BCG)**, **Goldman Sachs** (HireVue), **KKR/Evercore/BofA**
(locked portals). Run a short WebSearch sweep (TODAY's date, current cycle),
`"<firm> summer 2027 analyst internship apply"`, for: McKinsey, Bain, BCG, Goldman
Sachs, Evercore, Centerview, Lazard, PJT, plus any marquee roster firm you know
posts off-feed. Add only postings you can open and confirm are real, currently
open, and match a roster firm in `target_firms.py`. Cap at ~15 fetches.

## 3. Fact-check everything (drop anything unverifiable)
For each candidate (artifact + discovery), WebFetch its link (WebSearch to relocate
if it 404s): must still EXIST and be OPEN (not closed / "no longer accepting" / 404)
and plausibly match the company + an internship / summer-analyst / sophomore role in
the current cycle. **Drop anything you cannot verify.** Verify T1 first; cap at ~25
(say how many you didn't reach). Confirm tier vs `target_firms.py`; drop off-track
roles (SWE / hardware / design / recruiting) that slipped the gate.

## 4. Note deadlines
Capture any stated application deadline / "apply by" date on a verified posting.

## 5. Report (this is the push payload — concise, minimal emojis)
```
🔔 NEWLY OPEN
[T1] <Company> — <Role> (<Location>)[ · deadline <date>]
<apply link>
...
```
Then, only if a verified posting has a deadline within ~21 days:
```
🔴 CLOSING SOON
<Company> — <Role>: <deadline>
```
End: `SUMMARY: X open, Y closing ≤21d, checked Z (artifact + discovery).`
If nothing survives, keep it to ~5 lines: "No new openings today.", how many were
checked and why dropped (closed / below-tier / off-track / already-seen), and that
you'll check again tomorrow. Your final message IS the report — delivered by push.
Do not commit or edit the repo.
