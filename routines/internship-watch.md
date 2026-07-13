# Routine: internship-watch (daily, cloud — collect + judge)

Janus Tsen's daily internship opening-detector for elite finance / consulting /
strategy / corp-dev / quant / business roles (Summer 2027 + sophomore tracks).
**Fully cloud** — this routine both COLLECTS (keyless feeds) and JUDGES, so it
needs no laptop. Use TODAY'S ACTUAL DATE. You are in a fresh clone of
`janustsen/internship-pipeline` (default branch `main`), unattended.

Goal: surface top-tier internships **the day they open**, verified, by push —
with high recall on the target roster and near-zero false positives.

## 1. Collect (keyless, deterministic)
Set up and run the cloud collector — it fetches every roster firm's keyless feed
(ATS + Workday), gates through the relevance + Tier-1/2 allowlist, merges any
Handshake postings the local hybrid job dropped, and dedups against the
git-committed `seen_postings.json`:
```
pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt
python3 cloud_collect.py            # writes todays_candidates.json (NEW postings) + updates seen_postings.json
```
If `cloud_collect.py` errors, read the traceback, fix only if trivial, else note
it in the report and continue with whatever `todays_candidates.json` contains.
Read `todays_candidates.json` — these are the **new, roster-gated** candidates.

## 2. Discovery net (catch what the feeds miss)
The feeds miss firms with no keyless API — chiefly **MBB (McKinsey, Bain, BCG)**
and a few custom bank/boutique portals. For these, run a short WebSearch sweep
(TODAY's date, current cycle), e.g. `"<firm> summer 2027 analyst internship apply"`
and careers-page searches, for this priority shortlist plus any marquee firm you
know posts off-feed: McKinsey, Bain, BCG, Goldman Sachs, Morgan Stanley, Evercore,
Centerview, Lazard, Moelis, PJT. Add only postings you can open and confirm are
real, currently-open, and match a roster firm. Cap this pass at ~15 fetches.

## 3. Fact-check every candidate (drop anything unverifiable)
For each candidate (collector + discovery), WebFetch its link (WebSearch to
relocate if the link 404s): the posting must still EXIST and be OPEN (not closed /
"no longer accepting" / 404), and plausibly match the company + an internship /
summer-analyst / sophomore role in the current cycle. **Drop anything you cannot
verify as real and open.** If there are many, verify T1 first and cap at ~25 (say
how many you did not reach). Confirm tier against `target_firms.py` (T1 vs T2);
drop clearly off-track roles (SWE / hardware / design / recruiting) that slipped the gate.

## 4. Note deadlines
If a verified posting states an application deadline / "apply by" date, capture it.

## 5. Report (this is the push payload — concise, minimal emojis)
Lead with new openings, tier-sorted (all T1 then T2), one per line:
```
🔔 NEWLY OPEN
[T1] <Company> — <Role> (<Location>)[ · deadline <date>]
<apply link>
...
```
Then, only if any verified posting has a deadline within ~21 days:
```
🔴 CLOSING SOON
<Company> — <Role>: <deadline>
```
End with one line: `SUMMARY: X open, Y closing ≤21d, checked Z candidates (feeds + discovery).`
If nothing survived verification, keep the whole report to ~5 lines: "No new
openings today.", how many were checked and why dropped (closed / below-tier /
off-track / already-seen), and that you'll check again tomorrow.

## 6. Persist state (so tomorrow doesn't re-report today)
Commit the two artifacts to `main` so the seen-set survives to the next run:
```
git add todays_candidates.json seen_postings.json
git commit -m "internship-watch: <N> new candidates $(date -u +%FT%TZ)" || echo "nothing to commit"
git pull --rebase origin main && git push origin main || echo "push skipped/failed — note in report"
```
Never commit `.env`, `venv/`, `*.db`, or `handshake_candidates.json` (the local
job owns that drop). Your final message IS the report — it is delivered by push.
