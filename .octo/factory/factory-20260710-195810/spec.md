# Internship Notifier — Design Spec

**Date:** 2026-07-10
**Owner:** Janus Tsen (Stanford c/o 2029)
**Status:** Approved design (rev. 2) — pending implementation plan

---

## 1. Purpose

Turn the existing internship scraper pipeline into a high-precision **collector**, and add a
**cloud Claude routine** that fact-checks and prestige-judges what the collector hands off,
then returns a daily `fellowship-watch`-style report — so Janus is alerted the day a top-tier
internship application opens and can apply same-day.

Two workstreams:

1. **Improve the pipeline (local collector)** — replace the weak "prestige" filter with a
   curated, cross-sector tiered allowlist as a *coarse pre-filter*, retarget the recruiting
   cycle to Summer 2027 + sophomore/underclassman tracks, and hand off a candidate list
   instead of emailing.
2. **Build the notifier (cloud judge)** — a `internship-watch` cloud routine (twin of
   `fellowship-watch`) that, each fire, **fact-checks every candidate** (real, currently open,
   link resolves) and **confirms it's a genuine Tier 1 / Tier 2 firm**, then delivers a
   push report. No email.

---

## 2. Background — the existing system

Source of truth (read-only reference), currently at
`~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/Internships/Internship Scraper/`:

- **`orchestrator.py`** — runs 5 sources (LinkedIn via Apify, Handshake via local Selenium,
  Adzuna API, Serper career-page search, ATS-direct via Greenhouse/Lever/Ashby/
  SmartRecruiters/Workable with daily auto-discovery), dedups, writes `Internship_Digest.xlsx`,
  emails an HTML digest via Gmail SMTP. Runs daily at 8am via cron.
- **`ats_scraper.py`** — filtering brains: `is_relevant_internship` (title keywords),
  `is_finance_domain` (domain keywords), `is_prestigious` (company name), `normalize_title`
  (semantic dedup). Holds curated ATS seed lists + a Serper-powered discovery engine.
- **`seen_internships.db`** — SQLite: lifetime `jobs` dedup table + `discovered_companies`
  ATS token cache.

### The core defect this spec fixes

`is_prestigious()` is a **blocklist**, not an allowlist — it returns `True` for *any* company
whose name doesn't contain "vet clinic / dental / daycare / …". Consequently curated ATS seeds
are high-tier ✅ but **LinkedIn, Adzuna, Handshake, and auto-discovery leak in arbitrary
no-name firms** ❌ (and auto-discovery permanently saves those unvetted boards). The fix:
a curated **tiered allowlist** pre-filter locally + an **authoritative Claude prestige+fact
check** in the cloud.

### Two operational risks in the current file

- 🔴 **Live secrets are hardcoded in plaintext** (Gmail app password, Apify, Serper, Adzuna
  keys). Combined with the open key-revocation thread from the 2026-07 public-repo incident,
  these must move to `.env` and be **rotated**.
- ⚙️ **Handshake requires a logged-in local browser (Selenium)** — cannot run in a cloud
  routine. This drives the two-halves architecture.

---

## 3. Decisions (locked; rev. 2 = 2026-07-10)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Prestige filter | Curated **tiered allowlist** pre-filter (local) + **Claude tier judgment** (cloud); discovery → review queue | "Short list" precision; Claude is the authoritative judge |
| 2 | Cycle & roles | **Summer 2027 + sophomore/underclassman** tracks; role scope = Janus's track (finance/quant/consulting/strategy/corp-dev/BizOps/business) | c/o 2029 rising sophomore; brands broaden, roles don't |
| 3 | Delivery | **Push only** via `internship-watch` cloud routine (report = final message) | Email dropped; Remote Control paired |
| 4 | Hosting / secrets | `~/dev/internship-pipeline` repo, `.env`, rotate keys | Out of iCloud; agentic-git + security discipline |
| 5 | Architecture | **Two halves** — local *collector* + cloud *judge*, git bridge | Handshake needs local browser; Claude does verify+judge |
| 6 | Prestige scope | **Cross-sector T1/T2** — big companies, hot startups, marquee institutions (incl. gov e.g. NASA), big tech, top consulting, reputable boutiques | Defined by `/deep-research` in implementation |
| 7 | Cloud processing | Claude **fact-checks each posting** + **confirms T1/T2** before reporting | User asks #1 (fact-check) + #2 (tier-confirm) |
| 8 | Cloud env | **New dedicated environment** bound to the repo | Clean separation from vault/confidential repos |

---

## 4. Architecture & data flow

Same shape as Janus's reingestion layer (local gather → cloud judge), bridged by a private
GitHub repo.

```
LOCAL  ·  ~/dev/internship-pipeline  ·  daily ~06:00 PT (launchd)  ·  COLLECTOR
  improved pipeline (secrets in .env, Handshake intact)
    5 sources → role/cycle relevance filter → TIERED-ALLOWLIST coarse pre-filter (firm_match)
    → lifetime SQLite dedup  (the "newly seen" signal)
    → write todays_candidates.json   (NEW candidate roles for a target firm)
    → git commit + push  ───────────────┐
                                         ▼
BRIDGE  ·  private GitHub repo (todays_candidates.json committed)
                                         │
CLOUD  ·  internship-watch routine  ·  daily ~08:00 PT  ·  JUDGE
          new dedicated env · fresh session per fire · connectors stripped
    → clone repo → read todays_candidates.json
    → for each candidate:  ① FACT-CHECK (real? open? link live? right firm?) via web
                           ② CONFIRM Tier 1 / Tier 2 (embedded criteria + reference list)
    → drop anything unverified or below the bar
    → compose "🔔 NEWLY OPEN" report (tier · role · apply-now link · deadline if known)
    → deliver PUSH   ← fellowship-watch twin (no email)
```

**Timing:** Mac is awake at 6am for Handshake's authenticated browser anyway; it collects and
pushes the candidate artifact by ~06:30. The cloud routine fires ~08:00 (`0 15 * * *` UTC ≈
8am PDT), clones the fresh commit, verifies + judges, and pushes the report — early enough to
apply day-of.

**Why the git bridge:** cloud routine prompts can't be edited in place and we won't recreate
the routine daily, so it must read *external state*. A committed JSON in a repo the cloud env
clones is exactly the reingestion pattern already in use. A **dedicated private repo** (not
the brain vault) keeps this away from MNPI/PII/FStea/MS confidentiality walls.

---

## 5. Component: the tiered allowlist (cross-sector)

`target_firms.py` (or `.yaml`) — the local pre-filter's source of truth, **populated by
`/deep-research`** (see §6a). Two tiers, cross-sector. Every firm entry carries:

- `canonical` — display name
- `aliases` — matching variants across sources
- `sources` — ATS `platform`+`token` and/or `careers_url` (watch the authoritative portal)
- `tier` — `T1` | `T2`

Illustrative categories (final roster from `/deep-research`):

| Tier | Spans | Illustrative firms |
|------|-------|--------------------|
| **T1** | Bulge-bracket + elite boutiques; MBB; megafund PE; top quant/HF; FAANG-tier tech; hottest startups; marquee institutions | Goldman Sachs, Evercore, Centerview, Citadel, Jane Street, Blackstone, KKR, McKinsey, BCG, Bain, Google, Apple, Nvidia, OpenAI, Ramp, NASA JPL |
| **T2** | Strong banks/consulting; blue-chip corporates; well-regarded startups; **reputable boutiques nominally "tier 3"** | Barclays, UBS, RBC; Oliver Wyman, L.E.K., Accenture, Strategy&; Disney, top consumer/industrial names; solid growth-stage startups; respected M&A/strategy boutiques |

Priority: **T1 always reports first; T2 below it.** Role scope stays Janus's track (finance,
quant, consulting, strategy, corp dev, BizOps, business/product-strategy) even at cross-sector
firms — not aerospace-engineering or SWE roles.

### Discovery → review queue

`run_discovery` still finds new ATS boards but writes them to a `candidate_companies` table
(status `pending`) instead of auto-scraping. A `review_candidates` CLI lets Janus promote a
candidate into `target_firms.py` or reject it. Nothing un-approved is handed off.

### `firm_match(company_name) -> FirmMatch | None`

Replaces `is_prestigious`. Normalizes the company string (lowercase, strip Inc/LLC/LP/Group/&)
and alias-matches the allowlist; returns the matched firm (with tier) or `None`. **Every
source** gates on `firm_match(...) is not None` to bound the handoff. The allowlist is coarse
by design — Claude makes the final call in the cloud.

---

## 6. Component: filter changes (Summer 2027 + sophomore)

In `ats_scraper.py`:

- **Swap** the prestige gate: `is_prestigious(company)` → `firm_match(company) is not None`
  everywhere (`_passes_filters` + inline checks in `orchestrator.py`).
- **Retarget cycle:** `2027` primary (`2026` fading) in Serper/discovery queries + as a soft
  title signal.
- **Add underclassman include-signals:** *sophomore, freshman, first/second year, early
  insight, spring week, insight, discovery, emerging, rising, women, diversity, scholars*.
- Keep `is_relevant_internship` + `is_finance_domain` (lightly extended) and `normalize_title`
  + two-pass dedup unchanged.

### 6a. `/deep-research`: defining "prestigious enough"

Run early in implementation. Research question (approx.):

> "For a Stanford undergraduate targeting elite internships in finance, consulting, strategy,
> corp dev / BizOps, and quant, define a two-tier (T1 / T2) prestige ranking of firms **across
> sectors** — bulge-bracket & boutique banking, MBB & strategy consulting, megafund/growth PE,
> top quant/HF, FAANG-tier & marquee tech, the hottest startups, marquee institutions
> (incl. gov like NASA), and reputable finance/strategy boutiques nominally seen as 'tier 3'.
> Output: inclusion criteria per tier + a concrete firm roster with aliases."

Output feeds **both** `target_firms.py` (local allowlist) **and** the tier criteria + reference
list embedded in the cloud routine prompt.

---

## 7. Component: the handoff artifact

`todays_candidates.json` — written each local run, contains **only NEW candidate roles** at
allowlisted firms (rows newly inserted into the lifetime DB this run). It is *pre-verification*
— the cloud routine does the authoritative fact-check + tier-confirm. Schema:

```json
{
  "generated_at": "2026-07-10T06:12:00-07:00",
  "run_date": "2026-07-10",
  "candidate_count": 3,
  "candidates": [
    {
      "tier_hint": "T1",
      "category": "Quant / HF / MM",
      "company": "Jane Street",
      "title": "Summer 2027 Quantitative Trading Intern",
      "location": "New York, NY",
      "link": "https://…",
      "source": "ATS / Greenhouse",
      "posted": "2026-07-09"
    }
  ]
}
```

`tier_hint` is the local allowlist's guess; the cloud routine confirms or overrides it. The
Excel tracker is kept as the human-browsable archive.

---

## 8. Component: the `internship-watch` cloud routine (the judge)

Registered next to `fellowship-watch` (`trig_01UQ3tvJ2MrmHCnoBy2gK19W`), via RemoteTrigger /
claude.ai/code/routines:

- **Schedule:** daily, `0 15 * * *` UTC (≈ 08:00 PT; accepts UTC winter drift like the others).
- **Session:** `create_new_session_on_fire = true` (fresh per fire).
- **Env:** a **new dedicated environment** with the private `internship-pipeline` repo cloned.
- **Connectors:** Google-Drive connector **stripped** on create (standing security rule); needs
  only repo read + web (WebSearch/WebFetch) + notification.
- **Delivery:** **push only** (Remote Control mobile is paired). The report is the final message
  of each run.
- **Per-run processing:**
  1. Read `todays_candidates.json`.
  2. **Fact-check** each candidate via web — real posting? currently open? link resolves? the
     firm/role match the listing? Drop dead/closed/mismatched ones.
  3. **Confirm Tier 1 / Tier 2** using the embedded deep-research criteria + reference list;
     drop or downgrade firms that don't meet the bar; note good-boutique inclusions.
  4. Cap live-verification effort (like fellowship-watch's 15–20) if a run is unusually large.
- **Report DNA (mirrors `fellowship-watch`):** leads with **🔔 NEWLY OPEN** (tier-sorted T1→T2,
  each line: firm · role · location · **apply-now link** · deadline if known), then 🔴 closing
  soon if known, then a ~3–5 line "No new openings today" on quiet days. Concise, minimal
  emojis beyond section markers.
- **Management caveat:** `update_trigger` cannot change a prompt — to revise format/criteria,
  delete + recreate the routine.

---

## 9. Component: repo, secrets & cloud env

- New **private** repo at `~/dev/internship-pipeline` (out of iCloud — eliminates
  sync-corruption risk on the SQLite DB + Excel).
- `.env` (git-ignored) holds `MY_EMAIL`, `EMAIL_APP_PASSWORD` (SMTP no longer used for the
  digest but kept if any local alerting is wanted), `APIFY_API_TOKEN`, `SERPER_API_KEY`,
  `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`; code reads via `os.environ` / `python-dotenv`.
  `.env.example` committed as documentation.
- `.gitignore` excludes `.env`, `venv/`, `seen_internships.db`, `Internship_Digest.xlsx`,
  `handshake-scraper/handshake_jobs.csv`, `__pycache__/`. **`todays_candidates.json` IS
  committed** (it's the bridge state the cloud routine reads).
- 🔴 **Key rotation:** the currently-committed plaintext keys are considered exposed. Janus
  rotates Gmail app password + Apify/Serper/Adzuna keys; new values go only in `.env`.
- **New dedicated cloud environment** bound to this repo hosts the routine; no confidential
  (FStea/MS/MNPI) content ever touches it.

---

## 10. Testing

- **Unit — `firm_match`:** aliases match ("J.P. Morgan" → JPMorgan), near-misses reject
  ("Morgan & Morgan" ≠ Morgan Stanley), junk rejects ("X Capital LLC" → None).
- **Unit — title filter:** S2027 / sophomore / spring-week pass; senior / staff / PhD /
  director reject; 2026-only de-prioritized.
- **Integration — collector dry run:** run end-to-end against live ATS boards with
  `--no-push`; assert `todays_candidates.json` contains only allowlisted firms + track roles.
- **Cloud routine:** manual test fire — confirm (a) **push** lands on phone (no email),
  (b) fact-check drops a known-closed/dead posting, (c) tier-confirm drops a non-T1/T2 firm,
  (d) report reads correctly for both "new openings" and "nothing new" states.

---

## 11. Rollout sequence

1. Scaffold repo: move/copy pipeline code out of iCloud into `~/dev/internship-pipeline`;
   `.env` + `.gitignore` + `.env.example`; rotate keys.
2. **`/deep-research`** the T1/T2 cross-sector prestige criteria + roster (§6a).
3. Build `target_firms.py` from the research + `firm_match`; wire into every source gate;
   convert discovery to the candidate review queue.
4. Apply the S2027 + sophomore filter changes.
5. Add the `todays_candidates.json` writer; remove the SMTP email digest from the local run;
   keep Excel + DB.
6. Tests (§10); collector dry run.
7. launchd LaunchAgent for the 6am local run; confirm commit + push to the private GitHub repo.
8. Create the **new dedicated cloud environment** bound to the repo; register the
   `internship-watch` routine (embed deep-research criteria + roster; strip Drive connector);
   manual test fire (verify push + fact-check + tier-confirm).
9. Record the new routine + env in the `claude-code-automation` memory; enable daily.

---

## 12. Open items / non-goals

- **Open:** final firm roster + current ATS tokens/careers URLs — produced by `/deep-research`
  in implementation.
- **Resolved:** cloud env = **new dedicated environment**; Remote Control mobile push = paired.
- **Assumption (flag):** role scope stays Janus's business/finance/strategy track even as firms
  broaden cross-sector (no SWE/aerospace/etc.). Confirm if any-role-at-prestigious-firms is
  wanted instead.
- **Non-goal (v1):** auto-applying / autofilling applications — this only *notifies*.
- **Non-goal (v1):** manual deadline-calendar embed like the fellowship 70-program list; the
  DB's new-URL detection + cloud fact-check are the signal.

---

## Appendix A — Audit of the original scraper (secret-free) + improvements to execute

Audited 2026-07-10 against the read-only original. **Secrets live only in the top-of-file
CONFIG constants → move to `.env`; nothing here contains key values.** Preserve the exact
endpoints/quirks below; execute every fix.

### A.1 Source endpoints & quirks to PRESERVE

| Source | Endpoint | Notes to keep |
|--------|----------|---------------|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs` | returns all jobs, no pagination; `?content=true` optional for descriptions |
| Lever | `GET api.lever.co/v0/postings/{token}?mode=json` | returns a list; guard non-list responses |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{token}` | `jobPostings[]`; no pagination |
| SmartRecruiters | `GET api.smartrecruiters.com/v1/companies/{token}/postings?status=PUBLIC&limit=100` | **see A.2 pagination** |
| Workable | `POST apply.workable.com/api/v3/accounts/{token}/jobs` | **v3 quirk:** body `{"query":"","location":[],"workplace":[],"department":[]}` (no limit/offset); **Origin+Referer headers required** for CORS; **see A.2 pagination** |
| Handshake | Selenium via vendored `handshake_scraper.py` subprocess | persistent Chrome profile `~/.handshake_chrome_profile` (SSO reused); args `-u -p -t`; outputs `handshake_jobs.csv`; `--lang=fr-FR` is a vendor quirk (switch to en-US) |

### A.2 Coverage bugs to FIX (directly serves "return every/virtually every listing")

1. **`is_finance_domain` is a recall bug.** It requires a finance keyword *in the title*, which
   drops generic-titled roles at target firms ("2027 Summer Analyst Program", "Summer Intern"
   at Blackstone/Jane Street). Since **every source now gates on `firm_match` (curated
   prestigious firms), the extra title-domain gate is redundant and harmful.** → **Remove it as
   a hard gate.** Keep only: `is_relevant_internship` (intern + cycle) AND `firm_match`. Role
   on-track-ness is enforced by the allowlist's per-firm role scope + the cloud judge, not a
   brittle title keyword.
2. **SmartRecruiters pagination missing** — `limit=100` returns only the first 100; firms with
   >100 postings lose roles. → **Loop `offset += 100` until `content` empty / `totalFound`.**
3. **Workable pagination missing** — v3 returns a cursor (`paging.next` / `nextPage`). →
   **Follow the cursor until exhausted.**
4. **Adzuna** — only `page 1`, `results_per_page=50`, `max_days_old=1`. → **Page until
   exhausted; use `max_days_old=2` with dedup to survive a missed run (gap day).**
5. **Handshake `-p 3` caps ~75 jobs.** → **Raise to unlimited (`-p -1`) or a high page cap**
   with throttle, so target-firm postings aren't truncated.
6. **No retry/backoff anywhere** — a transient 429/timeout silently drops a firm for the day.
   → **Add exponential backoff + jitter; distinguish 404 (prune token) from transient (retry,
   keep token).**

### A.3 Correctness & robustness

- **Dedup:** `jobs.id = Link` + semantic (company + `normalize_title`) cross-source dedup is
  sound; a firm re-post under a new URL re-alerts, which is correct for an opening-detector.
- **Auto-discovery** permanently saved tokens & re-scraped forever (unbounded + unvetted) →
  fixed by the review-queue design (§5).
- **Per-host politeness** `POLITE_DELAY≈0.35s` — keep.
- `TITLE_INCLUDE` has `new grad` / `analyst program` — ambiguous vs internships; tighten so
  new-grad full-time roles don't slip in.

### A.4 Structural improvements to execute

- Secrets → `.env` (`python-dotenv`); `.env.example` committed.
- Modularize: `target_firms.py`, `filters.py` (`firm_match` + title/cycle), `store.py`
  (SQLite), `sources/` (one module per source), `handoff.py` (`todays_candidates.json`),
  `collector.py` (entry point).
- CLI flags for testing: `--dry-run`, `--no-push`, `--source <name>`, `--since <date>`.
- **Per-run coverage report** — log `raw → kept → dropped (with reason)` per source, so a
  silent drop is visible. This is the operational guardrail for the "every listing" mandate.
- Tests: `firm_match` (aliases/near-miss/junk), title+cycle filter, pagination loops (mocked),
  dedup, artifact schema.

---

## Purpose

Build a two-halves internship pipeline: a **local collector** (Python, all 5 sources incl.
Selenium Handshake) that scrapes, gates through a curated cross-sector Tier-1/Tier-2 firm
allowlist, dedups, and writes `todays_candidates.json`, committing it to a private git bridge;
and a **cloud judge routine** (`internship-watch`, twin of `fellowship-watch`) that fact-checks
each candidate and confirms Tier 1/2 membership before pushing a daily report. Prime directive:
return **every or virtually every real listing at target firms** — precision on firms, high
recall on their postings.

## Actors

- **Janus** — recipient of the daily push report; approves firms into the allowlist.
- **Local collector** (`collector.py`) — runs daily ~06:00 PT via launchd.
- **Cloud judge** (`internship-watch` routine) — runs daily ~08:00 PT, fresh session, push-only.
- **Sources** — LinkedIn (Apify), Handshake (Selenium, logged-in Chrome profile), Adzuna API,
  Serper career-page search, ATS APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workable).
- **Git bridge** — private repo holding `todays_candidates.json`.

## Behaviors

1. **B1 — Allowlist gate:** every source filters each posting through
   `firm_match(company) is not None`; non-matches are dropped. `firm_match` normalizes the
   company string and alias-matches `target_firms.py`, returning the firm + tier.
2. **B2 — Relevance filter:** keep postings that are internships for the target cycle
   (Summer 2027 primary) including underclassman/sophomore/spring-week/early-insight signals;
   exclude senior/staff/PhD/director/new-grad-full-time.
3. **B3 — Recall fix:** the old `is_finance_domain` title keyword gate is **removed** — a
   target firm + intern + cycle is sufficient (a generic "Summer Analyst Program" at a T1 firm
   must NOT be dropped).
4. **B4 — Full pagination:** SmartRecruiters pages via `offset += 100` until exhausted;
   Workable follows its v3 response cursor; Adzuna pages until exhausted with `max_days_old=2`.
5. **B5 — Resilience:** every HTTP call retries with exponential backoff + jitter; 404 → prune
   token, transient 4xx/5xx → retry and keep token; per-host politeness delay preserved.
6. **B6 — Discovery review queue:** ATS auto-discovery writes new tokens to a `pending`
   candidate table instead of auto-scraping; a `review_candidates` CLI promotes/rejects.
7. **B7 — Deduplication:** two-pass — exact URL, then semantic (company + `normalize_title`);
   lifetime SQLite `jobs` table yields the NEW-since-last-run set.
8. **B8 — Handoff artifact:** write `todays_candidates.json` (schema in §7) containing only the
   NEW target-firm candidates, then git commit + push.
9. **B9 — Coverage report:** per source, log `raw → kept → dropped (reason)` so no silent drop
   is possible.
10. **B10 — CLI:** `--dry-run`, `--no-push`, `--source <name>`, `--since <date>`.
11. **B11 — Secrets:** all keys read from `.env` via `python-dotenv`; none hardcoded.
12. **B12 — Cloud judge:** read `todays_candidates.json`; for each candidate fact-check via web
    (real / open / link resolves / firm matches) and confirm Tier 1/2 against embedded
    deep-research criteria; drop failures; compose the `fellowship-watch`-style "🔔 NEWLY OPEN"
    report; deliver via push only.

## Constraints

- No secret value is ever committed to git or sent to an external LLM provider.
- Handshake requires a logged-in local Chrome profile (`~/.handshake_chrome_profile`); it can
  only run locally, never in the cloud routine.
- Per-host politeness delay (~0.35s) and backoff must be respected (no aggressive hammering).
- Delivery is **push only** (no email); Remote Control mobile is paired.
- Role scope stays Janus's track (finance / quant / consulting / strategy / corp-dev / BizOps /
  business); no SWE/aerospace/etc. even at allowlisted firms.
- Prestige tiers are **cross-sector** T1/T2 (finance, consulting, big tech, hot startups,
  marquee institutions incl. gov, reputable boutiques).

## Dependencies

- Python: `requests`, `pandas`, `openpyxl`, `python-dotenv`, `selenium`, `webdriver-manager`,
  `apify-client`.
- External services: ATS APIs (Greenhouse/Lever/Ashby/SmartRecruiters/Workable), Serper.dev,
  Adzuna, Apify; a private git remote for the bridge; a dedicated cloud environment for the
  routine.
- `/deep-research` output defines the T1/T2 criteria + firm roster that populate
  `target_firms.py` and the routine's embedded reference list.

## Acceptance Criteria

- `firm_match` unit tests: aliases match, near-misses reject, junk rejects.
- Filter unit tests: S2027/sophomore titles pass; senior/PhD/new-grad reject; a generic
  "Summer Analyst Program" at a T1 firm PASSES (B3 recall check).
- Pagination test: a firm with >100 SmartRecruiters postings returns all of them (mocked).
- Integration dry run: `todays_candidates.json` contains only allowlisted, on-track roles.
- Coverage report prints `raw → kept → dropped` per source on every run.
- No plaintext secret anywhere in the repo (`git grep` clean); `.env` git-ignored.
- Cloud judge test fire: push lands; a known-closed posting is dropped by fact-check; a
  non-T1/2 firm is dropped by tier-confirm; "nothing new" yields a ~3–5 line report.

### Edge cases & error handling

- Source returns 404 → prune the token from the DB; 429/5xx or timeout → retry with backoff,
  keep the token (never silently drop a firm on a transient error).
- Empty NEW set → still run; cloud judge emits a short "No new openings today" report.
- Missing/invalid `.env` → fail fast with a clear message (never run with hardcoded fallback).
- Handshake profile not logged in / Selenium error → log, skip the Handshake source, continue
  the rest of the run (one dead source must not abort the pipeline).
- Malformed source payload → skip the item, count it in the coverage report's `dropped`.

### Preconditions

- `.env` present with all keys; Chrome profile logged into Handshake; git remote configured;
  `target_firms.py` populated from `/deep-research`.

### Postconditions

- `todays_candidates.json` written, committed, and pushed; lifetime DB updated with the new
  jobs; coverage report logged; Excel tracker appended.
