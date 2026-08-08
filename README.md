# internship-pipeline

> ## ⚠️ RETIRED — archive only, as of 2026-08-08
>
> **This pipeline no longer runs, and it should not be restarted.** Janus retired it
> because he found a better tool that does the same job; nothing here is being
> maintained. The code below is kept for reference and history only.
>
> Everything that used to run it is off, deliberately:
>
> - **GitHub Actions `collect-internships`** — `disabled_manually`. Do not re-enable it.
>   The `schedule:` trigger has also been removed from `.github/workflows/collect-internships.yml`,
>   so re-enabling the workflow alone will not restart collection.
> - **Cloud routine `internship-watch`** (`trig_01SRWWpNcKmjAaHJ2jTm3KUu`) — disabled in
>   claude.ai and recorded as retired in the vault's routine register
>   (`janus-brain/99-SYSTEM/routines/register.json`).
> - **LaunchAgent `com.janustsen.internship-collector`** — unloaded, and the plist has been
>   removed from `~/Library/LaunchAgents/`. The repo's own copy at
>   `deploy/com.janustsen.internship-collector.plist` is a reference artifact.
>   **It must stay unloaded — do not `launchctl bootstrap` it.**
>
> If you ever revive this, treat the API keys in `.env.example` as long expired and rotate
> everything before the first run.

A two-halves internship **opening-detector** for elite finance / consulting / strategy / quant
/ business roles (Summer 2027 + sophomore tracks), built to surface top-tier postings the day
they open.

- **Local collector** (`collector.py`) — scrapes 4 sources (ATS APIs, LinkedIn, Adzuna,
  Serper), gates every posting through a curated cross-sector **Tier-1/2/3 firm
  allowlist** (`target_firms.py`), deduplicates against a lifetime SQLite store, and writes
  `todays_candidates.json`, committing it to this git repo (the "bridge").
- **Cloud judge** (`routines/internship-watch.md`) — a scheduled Claude routine (twin of
  `fellowship-watch`) that **trusts** the ATS-sourced artifact as-is (Path A came from an
  authoritative keyless feed, so it isn't re-verified), **web-searches the no-feed roster firms**
  it can't otherwise see (Path B — curated marquees daily, the full list on Tuesdays; see
  `no_feed.py`), **fact-checks only those discoveries**, then runs an **LLM relevance/fit pass**
  that ranks Tier 1/2/3 and trims low-fit roles before pushing a daily report. See that file for
  the routine prompt.

Design spec: `docs/superpowers/specs/2026-07-10-internship-notifier-design.md`.

## Setup

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in ROTATED keys (see below)
./venv/bin/python -m pytest   # 34 tests
```

### Secrets (`.env`) — rotate first

The keys were migrated from the original scraper, where they lived in plaintext; treat them as
**exposed and rotate them** (then replace the values in `.env`, which is git-ignored).

| Key | Used by | Needed? |
|-----|---------|---------|
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna source | optional |
| `SERPER_API_KEY` | Serper career-page source (free plan: plain-keyword queries only) | optional |
| `APIFY_TOKEN`, `LINKEDIN_APIFY_ACTOR_ID` | LinkedIn source | optional |

**The keyless feed layer (Greenhouse / Lever / Ashby / SmartRecruiters / Workable / Workday)
needs no keys** and is the highest-signal source, so the pipeline runs usefully with an empty
`.env` — sources whose keys are missing skip themselves. The aggregators cover the ~80 target
firms that have no direct keyless feed (bulge brackets, MBB, big tech, marquee corporates;
enumerated by `no_feed.py`), so set the keys to watch those.

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
manual **Run workflow** button, and needs only `contents: write`. Enabling it **replaces** the
launchd job below — disable that plist so both don't push the same artifacts.

### Mac launchd (local)

```bash
cp deploy/com.janustsen.internship-collector.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.janustsen.internship-collector.plist
launchctl kickstart -k gui/$(id -u)/com.janustsen.internship-collector   # run once now
```

Runs `bin/run.sh` daily at 06:00 local (keyless ATS/Workday via `cloud_collect.py`);
logs to `logs/`.

## Coverage discipline

The prime directive is **≥99% recall of real postings at target firms**. Every run prints a
`raw → kept → dropped(reason)` coverage line per source so a silent drop is impossible. Run
`verify_tokens.py` periodically to catch a dead ATS token before it costs a listing.
