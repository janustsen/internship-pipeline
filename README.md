# internship-pipeline

A two-halves internship **opening-detector** for elite finance / consulting / strategy / quant
/ business roles (Summer 2027 + sophomore tracks), built to surface top-tier postings the day
they open.

- **Local collector** (`collector.py`) — scrapes 5 sources (ATS APIs, LinkedIn, Handshake,
  Adzuna, Serper), gates every posting through a curated cross-sector **Tier-1/2/3 firm
  allowlist** (`target_firms.py`), deduplicates against a lifetime SQLite store, and writes
  `todays_candidates.json`, committing it to this git repo (the "bridge").
- **Cloud judge** (`routines/internship-watch.md`) — a scheduled Claude routine (twin of
  `fellowship-watch`) that reads the artifact, **fact-checks** each candidate against the live
  web, **confirms Tier 1/2/3**, and pushes a daily report. See that file for the routine prompt.

Design spec: `docs/superpowers/specs/2026-07-10-internship-notifier-design.md`.

## Setup

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in ROTATED keys (see below)
./venv/bin/python -m pytest   # 25 tests
```

### Secrets (`.env`) — rotate first

The keys were migrated from the original scraper, where they lived in plaintext; treat them as
**exposed and rotate them** (then replace the values in `.env`, which is git-ignored).

| Key | Used by | Needed? |
|-----|---------|---------|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna source | optional |
| `SERPER_API_KEY` | Serper career-page source (free plan: plain-keyword queries only) | optional |
| `APIFY_TOKEN`, `LINKEDIN_APIFY_ACTOR_ID` | LinkedIn source | optional |
| `HANDSHAKE_SCRAPER_PATH`, `HANDSHAKE_SEARCH_URL` | Handshake Selenium scraper | optional |

**The keyless feed layer (Greenhouse / Lever / Ashby / SmartRecruiters / Workable / Workday)
needs no keys** and is the highest-signal source, so the pipeline runs usefully with an empty
`.env` — sources whose keys are missing skip themselves. The aggregators cover the ~120 target
firms that have no direct keyless feed (bulge brackets, MBB, big tech, marquee corporates), so
set the keys to watch those.

**Handshake** is off unless `HANDSHAKE_SEARCH_URL` is set. To enable it: (1) do a one-time SSO
login in a Chrome window so the session persists in `~/.handshake_chrome_profile`; (2) build a
Handshake internship search on your school's Handshake, copy the URL (it must include `page=1`),
and set it as `HANDSHAKE_SEARCH_URL`. It uniquely catches campus-exclusive sophomore/diversity
programs that never reach public boards. The vendored `handshake_scraper.py` needs Chrome +
`selenium` + `webdriver-manager` (already in `requirements.txt`).

## Run

```bash
./venv/bin/python collector.py                       # all sources, commit+push artifact
./venv/bin/python collector.py --source ats --dry-run --no-push   # ATS only, no DB/push
./venv/bin/python verify_tokens.py                   # live coverage check of ATS tokens
./venv/bin/python review_candidates.py               # promote/reject discovered ATS boards
```

Flags: `--dry-run` (don't touch DB), `--no-push` (write artifact, skip git push),
`--source <name>` (repeatable), `--since YYYY-MM-DD`, `--strict-env` (fail on missing keys).

## Schedule (collection half)

Path A (the keyless-feed collector that writes + pushes the bridge artifact) runs either on the
Mac or on GitHub Actions — pick one to avoid double-collection.

### GitHub Actions (laptop-free)

`.github/workflows/collect-internships.yml` polls every roster firm's keyless ATS/Workday feed
via `cloud_collect.py` and commits `todays_candidates.json` + `seen_postings.json` to `main` —
no laptop, no keys, zero LLM tokens (Actions runners have the open egress the Claude cloud
sandbox lacks). It runs once daily on `cron: "0 10 * * *"` (~06:00 ET, before the judge) plus a
manual **Run workflow** button, and needs only `contents: write`. It does **not** run Handshake
(that needs the logged-in Mac Chrome profile). Enabling it **replaces** the launchd job below —
disable that plist so both don't push the same artifacts.

### Mac launchd (local, includes Handshake)

```bash
cp deploy/com.janustsen.internship-collector.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.janustsen.internship-collector.plist
launchctl kickstart -k gui/$(id -u)/com.janustsen.internship-collector   # run once now
```

Runs `bin/run.sh` daily at 06:00 local (Handshake + keyless ATS/Workday via `cloud_collect.py`);
logs to `logs/`.

## Coverage discipline

The prime directive is **≥99% recall of real postings at target firms**. Every run prints a
`raw → kept → dropped(reason)` coverage line per source so a silent drop is impossible. Run
`verify_tokens.py` periodically to catch a dead ATS token before it costs a listing.
