# Internship Notifier — Design Spec

**Date:** 2026-07-10 · **Owner:** Janus Tsen (Stanford c/o 2029)
**Status:** Approved design (rev. 3) · **Complexity:** complex · **Satisfaction target:** 0.85

---

## Amendment 2026-07-14 (current architecture)

The architecture evolved after this spec was written. The historical body below is preserved
as-is for provenance, but the following supersedes it where they conflict:

- **(a) Handshake retired.** No more Selenium, no logged-in SSO Chrome profile, no
  `handshake_scraper.py`. The keyless 140-feed ATS/Workday spine replaces it.
- **(b) Path A moved off the Mac.** Keyless collection runs in **GitHub Actions**
  (`.github/workflows/collect-internships.yml`), which has the open egress the Claude cloud
  sandbox lacks for direct ATS/Workday hosts. The launchd cron / `bin/run.sh` is now a
  manual/backup runner, not the primary path.
- **(c) Path B is data-driven.** Web-search discovery reads the no-feed roster from
  `no_feed_firms.json` (derived by `no_feed.py`): the curated marquee subset sweeps **daily**,
  the full no-feed list sweeps **Tuesdays** — not a hardcoded firm list.
- **(d) T3 boutiques are kept** in the digest (they were being silently dropped by a T1/T2-only
  filter).
- **(e) ATS-sourced postings are trusted** and intentionally not re-verified — they come from an
  authoritative live keyless feed. Only Path-B web-discovered postings are fact-checked.
- **(f) LLM relevance/fit pass** ranks by tier then fit and trims low-fit roles.

Current source of truth: `cloud_collect.py`, `no_feed.py`, `routines/internship-watch.md`, and
`.github/workflows/collect-internships.yml`.

---

## Purpose

A two-halves internship pipeline. A **local collector** (Python; 5 sources incl. a Selenium
Handshake scraper) fetches postings, keeps only those from a curated **cross-sector Tier-1 /
Tier-2 firm allowlist**, deduplicates against a lifetime SQLite store, and writes
`todays_candidates.json`, committing it to a private git "bridge" repo. A **cloud judge routine**
(`internship-watch`, a twin of the existing `fellowship-watch`) reads that artifact, **fact-checks
each candidate** against the live web and **confirms Tier 1/2 membership**, then pushes a daily
report to Janus's phone. Prime directive: **≥99% recall of real postings at target firms** —
high precision on *which firms*, near-total recall on *their listings*. Delivery is push-only
(no email). It notifies; it does not auto-apply.

## Actors

- **Janus** — receives the daily push report; approves firms into the allowlist.
- **Local collector** (`collector.py`) — runs daily 06:00 PT via a launchd LaunchAgent.
- **Cloud judge** (`internship-watch` routine) — runs daily 08:00 PT, fresh session, push-only.
- **Sources** — LinkedIn (Apify actor), Handshake (Selenium + logged-in Chrome profile),
  Adzuna (REST), Serper.dev (career-page Google search), ATS APIs (Greenhouse, Lever, Ashby,
  SmartRecruiters, Workable).
- **Git bridge** — a private GitHub repo holding `todays_candidates.json`.

## Behaviors

- **B1 Allowlist gate.** Every source keeps a posting only when `firm_match(company)` returns a
  firm. `firm_match` lowercases and strips corporate suffixes (Inc/LLC/LP/Group/&), then
  alias-matches `target_firms.py`, returning `{canonical, tier}` or `None`.
- **B2 Relevance.** Keep internships for the target cycle (Summer 2027 primary), including
  underclassman signals (sophomore, first/second year, spring week, early insight, diversity,
  scholars). Reject senior / staff / principal / director / PhD / full-time new-grad.
- **B3 Recall fix.** Remove the legacy `is_finance_domain` title-keyword gate: at an allowlisted
  firm, `intern + target cycle` is sufficient. A generic "2027 Summer Analyst Program" at a
  Tier-1 firm MUST pass (it previously failed for lacking a finance keyword).
- **B4 Full pagination.** SmartRecruiters pages by `offset += 100` until exhausted; Workable
  follows its v3 response cursor; Adzuna pages until exhausted with `max_days_old=2` (survives a
  missed run). No source silently returns only its first page.
- **B5 Resilience.** Each HTTP call retries ≤3× with exponential backoff (0.5→1→2 s) + jitter
  and a 10 s timeout. HTTP 404 → prune the token; 429/5xx/timeout → retry and keep the token.
  Per-host politeness delay ≥0.35 s.
- **B6 Discovery review queue.** ATS auto-discovery writes new tokens to a `pending` table
  (never auto-scrapes them); a `review_candidates` CLI promotes or rejects each.
- **B7 Deduplication.** Two passes — exact URL, then semantic (`company + normalize_title`). The
  lifetime `jobs` table yields the NEW-since-last-run set.
- **B8 Handoff artifact.** Write `todays_candidates.json` =
  `{generated_at, run_date, candidate_count, candidates:[{tier_hint, category, company, title,
  location, link, source, posted}]}`, then `git commit` + `git push`.
- **B9 Coverage report.** Per source, log `raw → kept → dropped(reason)`; a silent drop is a
  test failure.
- **B10 CLI.** `--dry-run`, `--no-push`, `--source <name>`, `--since <date>`.
- **B11 Secrets.** All keys load from `.env` via `python-dotenv`; zero hardcoded credentials.
- **B12 Cloud judge.** Read the artifact; per candidate, fact-check via web (posting exists, is
  open, link returns 200, firm/role match) and confirm Tier 1/2 against embedded deep-research
  criteria; drop failures; compose the `fellowship-watch`-style "🔔 NEWLY OPEN" report
  (tier-sorted, apply links, deadline if known); deliver via push.

## Constraints

- No secret value is ever committed to git or sent to an external-LLM provider.
- Handshake runs **only locally** (needs logged-in Chrome profile `~/.handshake_chrome_profile`);
  it can never run in the cloud routine.
- Per-host politeness ≥0.35 s; ≤3 retries; 10 s HTTP timeout; local run ≤10 min wall-clock.
- One dead source must not abort the run (log, skip, continue).
- Delivery is push-only (Remote Control mobile is paired).
- Role scope = finance / quant / consulting / strategy / corp-dev / BizOps / business only — no
  SWE / aerospace / design roles, even at allowlisted firms.
- Prestige tiers are cross-sector T1/T2: banking & boutiques, MBB & strategy consulting,
  megafund/growth PE, top quant/HF, FAANG-tier tech, hottest startups, marquee institutions
  (incl. gov, e.g. NASA), and reputable finance/strategy boutiques.

## Dependencies

- **Python libs:** `requests`, `pandas`, `openpyxl`, `python-dotenv`, `selenium`,
  `webdriver-manager`, `apify-client`.
- **Services:** ATS APIs (Greenhouse/Lever/Ashby/SmartRecruiters/Workable), Serper.dev, Adzuna,
  Apify; a private git remote (bridge); a dedicated cloud environment for the routine.
- **`/deep-research`** output defines the T1/T2 criteria + firm roster that populate
  `target_firms.py` and the routine's embedded reference list.

## Acceptance Criteria

Satisfaction target **0.85**. Verified by:

- `firm_match` unit tests: aliases match ("J.P. Morgan"→JPMorgan); near-miss rejects
  ("Morgan & Morgan"≠Morgan Stanley); junk → `None`.
- Filter unit tests: S2027 / sophomore titles pass; senior / PhD / new-grad reject; a generic
  "Summer Analyst Program" at a Tier-1 firm PASSES (B3).
- Pagination test: a mocked firm with 250 SmartRecruiters postings returns all 250.
- Integration dry run (`--dry-run --no-push`): `todays_candidates.json` contains only
  allowlisted, on-track roles and validates against the B8 schema.
- Coverage report prints `raw → kept → dropped` per source on every run.
- `git grep` finds zero plaintext secrets; `.env` is git-ignored.
- Cloud test fire: push lands on the phone; a known-closed posting is dropped by fact-check; a
  non-T1/2 firm is dropped by tier-confirm; an empty NEW set yields a ≤5-line report.

### Edge cases & error handling

404 → prune token; 429/5xx/timeout → backoff + retry, keep token; empty NEW set → short "No new
openings today" report; missing/invalid `.env` → fail fast with a clear message (no hardcoded
fallback); Handshake not logged in / Selenium error → log, skip Handshake, continue the rest;
malformed source payload → skip the item and count it under `dropped`.

### Preconditions

`.env` complete; Chrome profile logged into Handshake; git remote configured; `target_firms.py`
populated from `/deep-research`.

### Postconditions

`todays_candidates.json` written, committed, and pushed; lifetime DB updated with the new jobs;
coverage report logged; Excel tracker appended.

---

## Design detail

### D1 — Architecture & data flow

Same shape as Janus's reingestion layer (local gather → cloud judge), bridged by a private repo.

```
LOCAL  ·  ~/dev/internship-pipeline  ·  daily ~06:00 PT (launchd)  ·  COLLECTOR
  5 sources → role/cycle relevance → firm_match allowlist gate → lifetime SQLite dedup
    → write todays_candidates.json → git commit + push  ──┐
                                                          ▼
BRIDGE  ·  private GitHub repo (todays_candidates.json)   │
                                                          ▼
CLOUD  ·  internship-watch routine  ·  daily ~08:00 PT  ·  JUDGE
  new dedicated env · fresh session · connectors stripped
    → read artifact → per candidate: ① fact-check (web) ② confirm Tier 1/2
    → "🔔 NEWLY OPEN" report → PUSH (no email)
```

The Mac is awake at 06:00 for Handshake's authenticated browser; it collects and pushes by
~06:30. The routine fires ~08:00 (`0 15 * * *` UTC), clones the fresh commit, verifies + judges,
and pushes — early enough to apply day-of. The git bridge is required because a routine's prompt
can't be edited in place; it reads external state instead. A dedicated private repo keeps this
away from the brain vault's MNPI/PII/FStea/MS confidentiality walls.

### D2 — Tiered allowlist (`target_firms.py`)

The local pre-filter's source of truth, **populated by `/deep-research`** (research question:
define cross-sector T1/T2 prestige criteria + a firm roster with aliases, spanning banking &
boutiques, MBB & consulting, PE, quant/HF, FAANG-tier tech, hot startups, marquee institutions
incl. gov, and reputable "tier-3" boutiques). Each firm entry: `canonical`, `aliases`,
`sources` (ATS platform+token and/or careers URL), `tier` (T1|T2). T1 reports first. The same
roster + criteria are embedded in the routine prompt (like `fellowship-watch`'s calendar) so the
cloud judge re-confirms tier authoritatively.

### D3 — Cloud routine (`internship-watch`)

Registered beside `fellowship-watch` (`trig_01UQ3tvJ2MrmHCnoBy2gK19W`) via RemoteTrigger. Daily
`0 15 * * *` UTC; `create_new_session_on_fire=true`; **new dedicated env** with the repo cloned;
Google-Drive connector stripped (standing security rule); needs only repo read + WebSearch/
WebFetch + notification. Report DNA mirrors `fellowship-watch`: leads with **🔔 NEWLY OPEN**
(tier-sorted, apply links), then 🔴 closing-soon if known, then a ~3–5 line "nothing new" on
quiet days. `update_trigger` cannot change a prompt — recreate to revise.

### D4 — Repo, secrets & cloud env

Private repo at `~/dev/internship-pipeline` (out of iCloud — kills sync-corruption risk on the
SQLite DB + Excel). `.env` (git-ignored) holds all keys; `.env.example` committed. `.gitignore`
excludes `.env`, `venv/`, `seen_internships.db`, `Internship_Digest.xlsx`,
`handshake_jobs.csv`, `__pycache__/`. `todays_candidates.json` **is** committed (bridge state).
🔴 The originally-committed plaintext keys are considered exposed — Janus rotates Gmail app
password + Apify/Serper/Adzuna keys; new values live only in `.env`. A **new dedicated cloud
environment** bound to this repo hosts the routine; no FStea/MS/MNPI content touches it.

### D5 — Modules

`target_firms.py` · `filters.py` (`firm_match` + title/cycle) · `store.py` (SQLite) ·
`sources/` (one module per source) · `handoff.py` (`todays_candidates.json`) ·
`collector.py` (entry point) · `tests/`.

### D6 — Rollout sequence

1. Scaffold repo, `.env`/`.gitignore`/`.env.example`, rotate keys.
2. `/deep-research` the T1/T2 cross-sector criteria + roster.
3. Build `target_firms.py` + `firm_match`; wire every source gate; discovery → review queue.
4. S2027 + sophomore filter changes; remove `is_finance_domain` hard gate (B3).
5. Add pagination (B4), retries/backoff (B5); `todays_candidates.json` writer; drop SMTP email.
6. Tests (Acceptance Criteria); collector dry run.
7. launchd LaunchAgent (06:00); confirm commit + push to the private remote.
8. Create the dedicated cloud env; register `internship-watch` (embed criteria + roster; strip
   Drive connector); manual test fire (push + fact-check + tier-confirm).
9. Record routine + env in the `claude-code-automation` memory; enable daily.

### D7 — Non-goals

Auto-applying / autofilling applications (v1 only notifies); a manual deadline-calendar embed
like the fellowship 70-program list (the DB's new-URL detection + cloud fact-check are the
signal).

---

## Appendix A — Audit of the original scraper (secret-free) + fixes to execute

Audited 2026-07-10 against the read-only original at
`~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/Internships/Internship Scraper/`.
**Secrets live only in the top-of-file CONFIG constants → move to `.env`; nothing here contains
key values.** Preserve the endpoints/quirks; execute every fix.

### A.1 Endpoints & quirks to PRESERVE

| Source | Endpoint | Keep |
|--------|----------|------|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs` | all jobs, no pagination; `?content=true` optional |
| Lever | `GET api.lever.co/v0/postings/{token}?mode=json` | returns a list; guard non-list responses |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{token}` | `jobPostings[]`; no pagination |
| SmartRecruiters | `GET api.smartrecruiters.com/v1/companies/{token}/postings?status=PUBLIC&limit=100` | **A.2 pagination** |
| Workable | `POST apply.workable.com/api/v3/accounts/{token}/jobs` | body `{"query":"","location":[],"workplace":[],"department":[]}`; **Origin+Referer headers required**; **A.2 pagination** |
| Handshake | Selenium subprocess `handshake_scraper.py -u -p -t` | profile `~/.handshake_chrome_profile` (SSO); outputs `handshake_jobs.csv`; `--lang=fr-FR` vendor quirk → switch to en-US |

### A.2 Coverage bugs to FIX (serves the ≥99% recall directive)

1. **`is_finance_domain` recall bug** — required a finance keyword *in the title*, dropping
   generic-titled roles at target firms. Since every source now gates on `firm_match`, it is
   redundant and harmful → **remove as a hard gate** (see B3).
2. **SmartRecruiters pagination** — `limit=100` returns only 100 → loop `offset += 100`.
3. **Workable pagination** — follow the v3 cursor (`paging.next`).
4. **Adzuna** — only page 1 / `max_days_old=1` → page until exhausted, `max_days_old=2`.
5. **Handshake `-p 3`** caps ~75 jobs → raise to unlimited / high cap with throttle.
6. **No retry/backoff** anywhere → add (see B5); 404 prunes, transient retries.

### A.3 Correctness & robustness

`jobs.id=Link` + semantic dedup is sound (a re-post under a new URL correctly re-alerts).
Auto-discovery previously saved tokens & re-scraped forever (unbounded + unvetted) → fixed by
the review queue (B6). Keep the per-host politeness delay. Tighten `TITLE_INCLUDE`
(`new grad`/`analyst program`) so full-time new-grad roles don't slip in.
