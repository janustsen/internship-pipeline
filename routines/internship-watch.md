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
have no machine feed. Your WebFetch/WebSearch tools reach the open web through the
proxy, not the blocked sandbox egress. Do not commit or edit the repo.

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
off-cycle insight program). Add a posting only if you can open it and confirm it is
real, currently open, and maps to that roster firm. Note how many firms you swept
and cap total WebFetches at ~30 on normal days / ~60 on Tuesday (say how many you
didn't reach).

## 3. Verify ONLY the web-discovered postings
The artifact postings are already trusted (§1). For each posting **you** found via
discovery (§2), WebFetch its link (WebSearch to relocate if it 404s): it must still
EXIST and be OPEN (not closed / "no longer accepting" / 404) and plausibly match the
company + an internship / summer-analyst / sophomore role in the current cycle.
**Drop any discovery posting you cannot verify.** Capture any stated application
deadline / "apply by" date.

## 4. Relevance pass — rank for fit to Janus, trim the weak
Now judge the combined set (trusted artifact + verified discoveries) for FIT, not
just validity. For each posting, weigh:
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
🔔 NEWLY OPEN
[T1] <Company> — <Role> (<Location>)[ · deadline <date>]
<apply link>
[T2] ...
[T3] ...
```
Then, only if a verified posting has a deadline within ~21 days:
```
🔴 CLOSING SOON
<Company> — <Role>: <deadline>
```
End with: `SUMMARY: X open (A T1 / B T2 / C T3), Y closing ≤21d, swept Z no-feed
firms (curated|full), checked W discoveries.`
If nothing survives, keep it to ~5 lines: "No new openings today.", how many were
checked and why dropped (closed / off-track / off-cycle / already-seen), whether it
was the Tuesday full sweep, and that you'll check again tomorrow. Your final message
IS the report — delivered by push.
