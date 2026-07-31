# Routine: internship-watch (daily, cloud — judge + discovery + relevance)

Janus Tsen's daily internship opening-detector for elite finance / consulting /
strategy / corp-dev / quant / business roles (Summer 2027 + sophomore/underclassman
tracks). **USE TODAY'S ACTUAL DATE.** You are in a fresh clone of
`janustsen/internship-pipeline` (default branch `main`), unattended. Goal: surface
the internships that are the best fit for Janus **the day they open**, verified,
ranked, by push — high recall on discovery, high precision on what you report.

**Why you don't run the collector:** a GitHub Actions job
(`.github/workflows/collect-internships.yml`) polls every roster firm's keyless
ATS/Workday feed each morning and commits `todays_candidates.json` — direct HTTP
that this cloud sandbox blocks ("egress policy denied all ATS/Workday hosts"),
but Actions runners allow. You JUDGE that artifact and DISCOVER the firms that
have no machine feed, using **WebSearch only** (no WebFetch — see §3). Do not
commit or edit the repo.

## 1. Read the collected candidates (authoritative — do NOT re-verify)
Open `todays_candidates.json` at the repo root: the NEW, roster-gated postings the
Actions collector found (each: `tier_hint` in T1/T2/**T3**, `category`, `company`,
`title`, `location`, `link`, `source`, `posted`). Every one came from a live
keyless feed (`source` = greenhouse / lever / ashby / smartrecruiters / workable /
workday), so it **is already real and open — trust it. Do NOT WebFetch these to
"verify" them.** (Re-verifying authoritative postings is what blanked a whole run
when the fetch proxy returned 403 — don't reintroduce that.) If the file is missing
or `candidate_count` is 0, continue — discovery below can still surface openings.
Note its `run_date`: if it isn't today, say so in one line and judge what's there.

Keep **all three tiers** — T1, T2, and T3. T3 firms are the prestige boutiques
Janus deliberately added (Brattle, Charles River, Ducera, Level Equity, H.I.G.,
etc.); they belong in the digest, ranked below T1/T2.

## 2. Discovery net — the firms with NO machine feed (data-driven)
Open `no_feed_firms.json`. It lists the roster firms that have no keyless feed and
can only be found by web search, split into `curated_daily` (the elite off-feed
finance/consulting/PE/VC/HF marquees) and `full` (every no-feed roster firm).

- **If today is Tuesday:** sweep the **`full`** list (~80 firms) — the weekly deep
  pass over the whole no-feed tail.
- **Any other day:** sweep only **`curated_daily`** (~40 firms).

For each firm in the active list, run one WebSearch with today's date and the
current cycle, e.g. `"<firm> summer 2027 analyst internship apply"` (or sophomore /
off-cycle insight program). Note how many firms you swept and how many searches
turned up nothing (say how many you didn't reach, if any).

## 3. Judge the web-discovered postings — WebSearch only, no WebFetch
**This routine does not have a WebFetch tool** (removed 2026-07-30 — the cloud
sandbox's egress proxy was returning HTTP 403 on every WebFetch call since
2026-07-13, a platform-side block with no user-side fix; see
[[../../janus-brain/00-INBOX/2026-07-22-cloud-webfetch-403-audit]]). Every
discovery-net lead is therefore judged from **WebSearch result snippets alone** —
title, snippet text, and URL. There is no live-fetch confirmation step, and there
never will be again unless WebFetch comes back; do not re-add a fetch call here.

For each posting found via §2's WebSearch: keep it only if the snippet evidence
puts a current-cycle (2026/2027) summer-analyst / sophomore posting on the firm's
OWN careers domain (not a third-party aggregator, not a stale cached result) —
company, role, and cycle all line up. Drop it if the cycle is unclear, the role is
off-track, or the only evidence is a third-party aggregator repeating an old
listing. Every surviving posting is **unverified by construction** — carry the
apply link, but never claim it as fetch-confirmed open. Capture a deadline only if
the snippet itself states one; do not infer one.

## 4. Relevance pass — rank for fit to Janus, trim the weak
Now judge the combined set (§1's trusted artifact postings + §3's search-verified
discoveries) for FIT, not just validity. Discovery-net postings are ranked and
fit-filtered just like the rest — they simply land in the 🟡 tier (§5). For each
posting, weigh:
- **In-domain:** investment banking / M&A, PE / growth equity, VC, hedge fund /
  quant / trading, management & strategy consulting, corporate strategy / BizOps /
  corp-dev, economics. In scope. Off-track (SWE / hardware / design / data eng /
  recruiting / nursing) → drop even if it slipped the collector's gate.
- **Cycle fit:** Summer 2027, sophomore / underclassman, first/second-year, spring
  week, early-insight/diversity programs → strong. Explicitly a different/earlier
  cycle (2025 and earlier, senior/new-grad/MBA-only, PhD-only) → drop.
- **Prestige tier:** T1 > T2 > T3 as a tiebreak, but a great-fit T3 sophomore role
  outranks a marginal T1 senior-leaning one.

Assign each survivor a short fit note and rank: tier first (T1→T2→T3), then fit
within tier. If a posting is clearly low-fit, drop it — precision matters in the
report. Keep the discovery net wide (§2) but the report tight.

## 5. Report (this is the push payload — concise, minimal emojis)
```
🔔 NEWLY OPEN            (from the collector artifact, §1 — feed-confirmed)
[T1] <Company> — <Role> (<Location>)[ · deadline <date>]
<apply link>
[T2] ...
[T3] ...
```
Then every §3 discovery-net lead — WebSearch-only, never fetch-confirmed; label them
plainly, and NEVER fold these into "nothing today":
```
🟡 LIKELY OPEN (WebSearch snippet only — no fetch verification available)
[T1] <Company> — <Role> (<Location>) · <apply link> · unverified (search-only)
[T2] ...
```
Then, only if a 🔔 feed-confirmed posting has a stated deadline within ~21 days:
```
🔴 CLOSING SOON
<Company> — <Role>: <deadline>
```
End with: `SUMMARY: X feed-confirmed open (A T1 / B T2 / C T3), L likely-open
(search-only), Y closing ≤21d, swept Z no-feed firms (curated|full), W discoveries kept
of the leads checked.`
Only say "No new openings today." when discovery genuinely surfaced nothing (or every
lead was dropped as off-track / off-cycle / already-seen / unclear). A discovery lead
that survives §3 is never "nothing" just because it's WebSearch-only — report it under
🟡 LIKELY OPEN. When it really is quiet, keep it to ~5 lines: how many were checked and
why dropped, whether it was the Tuesday full sweep, and that you'll check again tomorrow.

DELIVERY. Do the discovery, judging, and ranking silently — no narration of tool calls
or search steps in the chat. Your FINAL MESSAGE **is** the report above, written out in
full; do not call any notification, message, or file-send tool, and do not end with a
summary or preview of the report instead of the report itself. The platform sends the
push notification and opens Janus straight to this run; your only job is to leave the
complete report as your last message.
