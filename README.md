# internship-pipeline

A two-halves internship **opening-detector** for elite finance / consulting / strategy / quant
/ business roles (Summer 2027 + sophomore tracks), built to surface top-tier postings the day
they open.

- **Local collector** (`collector.py`) — scrapes 5 sources (ATS APIs, LinkedIn, Handshake,
  Adzuna, Serper), gates every posting through a curated cross-sector **Tier-1/Tier-2 firm
  allowlist** (`target_firms.py`), deduplicates against a lifetime SQLite store, and writes
  `todays_candidates.json`, committing it to this git repo (the "bridge").
- **Cloud judge** (`routines/internship-watch.md`) — a scheduled Claude routine (twin of
  `fellowship-watch`) that reads the artifact, **fact-checks** each candidate against the live
  web, **confirms Tier 1/2**, and pushes a daily report. See that file for the routine prompt.

Design spec: `docs/superpowers/specs/2026-07-10-internship-notifier-design.md`.

## Setup

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in ROTATED keys (see below)
./venv/bin/python -m pytest   # 25 tests
```

### Secrets (`.env`) — rotate first

The original scraper had these keys hardcoded in plaintext; treat them as exposed and **rotate
them** before use. `.env` is git-ignored.

| Key | Used by | Needed? |
|-----|---------|---------|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna source | optional |
| `SERPER_API_KEY` | Serper career-page source | optional |
| `APIFY_TOKEN`, `LINKEDIN_APIFY_ACTOR_ID` | LinkedIn source | optional |
| `HANDSHAKE_SCRAPER_PATH` | Handshake Selenium scraper path | optional |

**The ATS layer (Greenhouse / Lever / Ashby / SmartRecruiters / Workable) needs no keys** and
is the highest-signal source, so the pipeline runs usefully with an empty `.env` — sources
whose keys are missing skip themselves. Handshake additionally needs the vendored
`handshake_scraper.py` and a logged-in Chrome profile (`~/.handshake_chrome_profile`).

## Run

```bash
./venv/bin/python collector.py                       # all sources, commit+push artifact
./venv/bin/python collector.py --source ats --dry-run --no-push   # ATS only, no DB/push
./venv/bin/python verify_tokens.py                   # live coverage check of ATS tokens
./venv/bin/python review_candidates.py               # promote/reject discovered ATS boards
```

Flags: `--dry-run` (don't touch DB), `--no-push` (write artifact, skip git push),
`--source <name>` (repeatable), `--since YYYY-MM-DD`, `--strict-env` (fail on missing keys).

## Schedule (local half)

```bash
cp deploy/com.janustsen.internship-collector.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.janustsen.internship-collector.plist
launchctl kickstart -k gui/$(id -u)/com.janustsen.internship-collector   # run once now
```

Runs daily at 06:00 local; logs to `logs/`.

## Coverage discipline

The prime directive is **≥99% recall of real postings at target firms**. Every run prints a
`raw → kept → dropped(reason)` coverage line per source so a silent drop is impossible. Run
`verify_tokens.py` periodically to catch a dead ATS token before it costs a listing.
