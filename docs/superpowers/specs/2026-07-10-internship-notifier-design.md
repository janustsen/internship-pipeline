# Internship Notifier — Design Spec

**Date:** 2026-07-10
**Owner:** Janus Tsen (Stanford c/o 2029)
**Status:** Approved design — pending implementation plan

---

## 1. Purpose

Turn the existing internship scraper pipeline into a **high-precision, prestige-tiered
opening-detector** and add a **daily notifier** that mirrors the existing `fellowship-watch`
cloud routine, so Janus is alerted the day a top-tier internship application opens and can
apply same-day.

Two workstreams:

1. **Improve the pipeline** — replace the weak "prestige" filter with a curated, tiered
   allowlist that gates *every* source, and retarget the recruiting cycle to Summer 2027 +
   sophomore/underclassman tracks.
2. **Build the notifier** — a `internship-watch` cloud routine (twin of `fellowship-watch`)
   that reads the pipeline's daily output and delivers a push + email digest.

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
whose name doesn't contain "vet clinic / dental / daycare / …". Consequently:

- Curated ATS seeds and curated Serper queries (GS, MS, JPM, MBB, Blackstone, Jane Street, …)
  *are* genuinely high-tier. ✅
- But **LinkedIn, Adzuna, Handshake, and the daily auto-discovery** leak in arbitrary no-name
  firms that merely mention "capital" or "advisory." Auto-discovery even **permanently saves**
  those unvetted boards to the DB and re-scrapes them forever. ❌

The fix: a real, curated, **tiered allowlist** as the single source of truth, gating all
sources; auto-discovery becomes a review queue, not an auto-add.

### Two operational risks in the current file

- 🔴 **Live secrets are hardcoded in plaintext** in `orchestrator.py` (Gmail app password,
  Apify, Serper, Adzuna keys). Combined with the open key-revocation thread from the
  2026-07 public-repo incident, these must be moved to `.env` and **rotated**.
- ⚙️ **Handshake requires a logged-in local browser (Selenium)** — it cannot run in a cloud
  routine. This drives the two-halves architecture below.

---

## 3. Decisions (locked 2026-07-10)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Prestige filter | Curated **tiered allowlist**; discovery → review queue | "It's a short list" — precision over recall |
| 2 | Cycle & roles | **Summer 2027 + sophomore/underclassman** tracks | c/o 2029 = rising sophomore as of 2026-07; S2026 has passed |
| 3 | Delivery | `internship-watch` **cloud routine** — push + email, daily | Match `fellowship-watch`; apply day-of |
| 4 | Hosting / secrets | `~/dev/internship-pipeline` repo, `.env`, rotate keys | Out of iCloud (sync risk); fits agentic-git + security discipline |
| 5 | Architecture | **Two halves** (local pipeline + cloud routine, git bridge) | Handshake needs local browser; preserve full pipeline coverage |
| 6 | Roster / corp scope | Tiers as in §5; **big-tech + marquee corporates** | Matches "top strategy roles in big corps or big tech" |

---

## 4. Architecture & data flow

Same shape as Janus's reingestion layer (local gather half → cloud judge half), bridged by a
private GitHub repo.

```
LOCAL  ·  ~/dev/internship-pipeline  ·  daily ~06:00 PT (launchd)
  improved pipeline (secrets in .env, Handshake intact)
    5 sources → TIERED-ALLOWLIST gate (firm_match) → S2027/sophomore title filter
    → lifetime SQLite dedup  (this IS the "newly open" signal)
    → append Internship_Digest.xlsx        (human-browsable tracker)
    → write todays_openings.json           (machine artifact: only NEW target-firm roles)
    → git commit + push  ───────────────┐
                                         ▼
BRIDGE  ·  private GitHub repo (todays_openings.json + tracker committed)
                                         │
CLOUD  ·  internship-watch routine  ·  daily ~08:00 PT
          fresh session per fire · connectors stripped
    → clone repo → read todays_openings.json
    → compose "🔔 NEWLY OPEN" digest (tier · role · apply-now link · deadline)
    → deliver PUSH + EMAIL   ← true fellowship-watch twin
```

**Timing/ordering:** the Mac is awake at 6am for Handshake's authenticated browser anyway; it
scrapes, filters, and pushes the artifact by ~06:30. The cloud routine fires at ~08:00 (`0 15
* * *` UTC ≈ 8am PDT), clones the fresh commit, and pings — early enough to apply day-of.

**Why the git bridge:** cloud routine prompts can't be edited in place and we won't recreate
the routine daily, so the routine must read *external state*. A committed JSON in a repo the
cloud env clones is exactly the reingestion pattern already in use. A **dedicated private
repo** (not the brain vault) keeps this cleanly away from MNPI/PII/FStea/MS confidentiality
walls.

---

## 5. Component: the tiered allowlist

`target_firms.py` (or `.yaml`) — the single source of truth. Every firm entry carries:

- `canonical` — display name
- `aliases` — matching variants across sources ("JPMorgan", "J.P. Morgan", "JPMorgan Chase")
- `sources` — where its applications live: ATS `platform`+`token` and/or `careers_url`
- `tier` — `T1` | `T2` | `CORP`

Starting roster (full list + current ATS tokens/careers URLs to be completed in
implementation):

| Tier | Category | Firms |
|------|----------|-------|
| **T1** | Bulge-bracket IB | Goldman Sachs, Morgan Stanley, JPMorgan, BofA, Citi |
| **T1** | Elite boutiques | Evercore, Centerview, Lazard, Moelis, PJT, Perella Weinberg, Qatalyst, Guggenheim, Houlihan Lokey, Jefferies |
| **T1** | Quant / HF / MM | Citadel, Citadel Securities, Jane Street, Two Sigma, HRT, D.E. Shaw, Point72, Millennium, Jump Trading, DRW, Optiver, IMC, SIG |
| **T1** | Megafund PE | Blackstone, KKR, Apollo, Carlyle, Bain Capital, TPG, Warburg Pincus, Silver Lake, Vista, Advent, General Atlantic |
| **T1** | MBB | McKinsey, BCG, Bain & Company |
| **T2** | Banks / consulting | Barclays, UBS, Deutsche Bank, RBC, Wells Fargo; Oliver Wyman, L.E.K., Parthenon-EY, Strategy&, Kearney |
| **CORP** | Big-tech strategy | Google, Meta, Amazon, Apple, Microsoft, Nvidia — Corp Strategy / BizOps / Corp Dev / Chief-of-Staff |
| **CORP** | Marquee corporates | Short blue-chip list (e.g. Disney, top consumer/industrial names) — Corp Strategy / Corp Dev |

Priority: **T1 always notifies first; T2 and CORP notify below it.**

### `firm_match(company_name) -> FirmMatch | None`

Replaces `is_prestigious`. Normalizes the incoming company string (lowercase, strip
Inc/LLC/LP/Group/&, punctuation) and alias-matches against the allowlist. Returns the matched
firm (with tier) or `None`. **Every source** (LinkedIn, Adzuna, Handshake, Serper, all ATS
scrapers) gates on `firm_match(...) is not None`.

### Discovery → review queue

`run_discovery` still finds new ATS boards but writes them to a `candidate_companies` table
(status `pending`) instead of auto-scraping. A small `review_candidates` CLI lets Janus
promote a candidate into `target_firms.py` (or reject it). Nothing un-approved ever notifies.

---

## 6. Component: filter changes (Summer 2027 + sophomore)

In `ats_scraper.py`:

- **Swap** the prestige gate: `is_prestigious(company)` → `firm_match(company) is not None`
  everywhere it's used (`_passes_filters`, and the inline checks in `orchestrator.py`'s
  LinkedIn/Handshake/Adzuna loops).
- **Retarget cycle:** year signal `2027` primary (`2026` fading), applied in the Serper /
  discovery queries and as a soft title signal.
- **Add underclassman include-signals** to the title logic: *sophomore, freshman, first year,
  second year, early insight, spring week, insight, discovery, emerging, rising, women,
  diversity, scholars* — these mark sophomore-eligible early programs many T1 firms run.
- Keep `is_relevant_internship` and `is_finance_domain`, lightly extended.
- Preserve `normalize_title` and the two-pass (URL + semantic) dedup unchanged.

---

## 7. Component: the daily artifact

`todays_openings.json` — written each local run, contains **only NEW target-firm roles** (rows
inserted into the lifetime DB this run). Schema:

```json
{
  "generated_at": "2026-07-10T06:12:00-07:00",
  "run_date": "2026-07-10",
  "new_count": 3,
  "openings": [
    {
      "tier": "T1",
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

The lifetime SQLite dedup (new-URL detection) *is* the "newly open" signal — stronger and less
noisy than `fellowship-watch`'s recency heuristic. The Excel tracker is kept as the
human-browsable archive; the notifier reads the JSON.

---

## 8. Component: the `internship-watch` cloud routine

Registered next to `fellowship-watch` (`trig_01UQ3tvJ2MrmHCnoBy2gK19W`), via the RemoteTrigger
tool / claude.ai/code/routines:

- **Schedule:** daily, `0 15 * * *` UTC (≈ 08:00 PT; accepts UTC winter drift like the others).
- **Session:** `create_new_session_on_fire = true` (fresh per fire).
- **Env:** an env with the private `internship-pipeline` repo cloned.
- **Connectors:** Google-Drive connector **stripped** on create (standing security rule); needs
  only repo read + notification.
- **Delivery:** push + email. (Email is the reliable channel until Remote Control mobile push
  is paired; push activates then.)
- **Report DNA (mirrors `fellowship-watch`):**
  - Leads with **🔔 NEWLY OPEN** — tier-sorted (T1 → T2 → CORP), each line: firm · role ·
    location · **apply-now link** · deadline if known.
  - Then 🔴 **closing soon** (if deadline data available), then a one-line "No new openings
    today" on quiet days (~3–5 lines total).
  - No emojis beyond the section markers already used by the fellowship routine; concise.
- **Management caveat:** `update_trigger` cannot change a prompt — to revise the report format,
  delete + recreate the routine.

---

## 9. Component: repo & secrets

- New **private** repo at `~/dev/internship-pipeline` (out of iCloud — eliminates
  sync-corruption risk on the SQLite DB + Excel).
- `.env` (git-ignored) holds `MY_EMAIL`, `EMAIL_APP_PASSWORD`, `APIFY_API_TOKEN`,
  `SERPER_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`; code reads via `os.environ` /
  `python-dotenv`. `.env.example` committed as documentation.
- `.gitignore` excludes `.env`, `venv/`, `seen_internships.db`, `Internship_Digest.xlsx`,
  `handshake-scraper/handshake_jobs.csv`, `__pycache__/`.
- 🔴 **Key rotation:** the currently-committed plaintext keys are considered exposed. Janus
  rotates the Gmail app password + Apify/Serper/Adzuna keys; the new values go only in `.env`.
- The `.env` and `todays_openings.json` are the only bridge state; **no** confidential
  (FStea/MS/MNPI) content ever touches this repo.

---

## 10. Testing

- **Unit — `firm_match`:** aliases match ("J.P. Morgan" → JPMorgan), near-misses reject
  ("Morgan & Morgan" ≠ Morgan Stanley), junk rejects (random "X Capital LLC" → None).
- **Unit — title filter:** S2027 / sophomore / spring-week titles pass; senior / staff / PhD /
  director reject; 2026-only roles de-prioritized.
- **Integration — pipeline dry run:** run end-to-end against live ATS boards with a
  `--no-email --no-push` flag; assert `todays_openings.json` contains only allowlisted firms.
- **Integration — notifier:** fire the cloud routine once manually; confirm push + email land
  and the report reads correctly for both "new openings" and "nothing new" states.

---

## 11. Rollout sequence

1. Scaffold repo: move/copy pipeline code out of iCloud into `~/dev/internship-pipeline`;
   `.env` + `.gitignore` + `.env.example`; rotate keys.
2. Build `target_firms.py` allowlist + `firm_match`; wire it into every source gate; convert
   discovery to the candidate review queue.
3. Apply the S2027 + sophomore filter changes.
4. Add `todays_openings.json` writer; keep Excel + DB.
5. Tests (§10); pipeline dry run.
6. launchd LaunchAgent for the 6am local run; confirm push to private GitHub repo.
7. Register the `internship-watch` cloud routine (strip Drive connector); manual test fire.
8. Record the new routine in the `claude-code-automation` memory; enable daily.

---

## 12. Open items / non-goals

- **Open:** final firm roster completion + current ATS tokens/careers URLs (implementation).
- **Open:** confirm the cloud env/repo wiring for the routine (new env vs. extend an existing).
- **Open:** Remote Control mobile push pairing (Janus-side; email works meanwhile).
- **Non-goal (v1):** applying automatically / autofilling applications — this only *notifies*.
- **Non-goal (v1):** deadline-tracking beyond what sources expose (no manual calendar like the
  fellowship 70-program embed; the DB's new-URL detection is the signal).
