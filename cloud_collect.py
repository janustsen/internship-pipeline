"""cloud_collect.py — keyless, laptop-free collection for the cloud routine.

Runs inside the `internship-watch` cloud routine (a fresh clone of the repo, no
API keys, no login). Fetches every roster firm's KEYLESS feed (ATS + Workday),
gates through the same relevance + tier filters as the local collector, merges in
Handshake postings dropped by the tiny local hybrid job, dedups against a
git-committed `seen_postings.json` (persistent state lives in the repo, not a
local SQLite), and writes `todays_candidates.json` for the judge half.

No network keys, no git here — the routine commits the artifacts. Idempotent per
day: a posting is reported once (its fingerprint is remembered in seen_postings).

Usage:  ./venv/bin/python cloud_collect.py            # writes todays_candidates.json + seen_postings.json
        ./venv/bin/python cloud_collect.py --dry-run  # no writes; prints summary
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from filters import (
    candidate_category,
    firm_match,
    is_relevant_posting,
    normalize_company_name,
    normalize_title,
)
from handoff import write_handoff
from http_client import RetryingHttpClient
from models import Candidate, RawPosting
from sources import ats, workday
from target_firms import all_source_tokens

SEEN_PATH = Path("seen_postings.json")
HANDSHAKE_DROP = Path("handshake_candidates.json")
TARGET_YEAR = 2027

# platform -> (fetcher, kind). ATS fetchers take an org slug; workday takes the
# full /wday/cxs/.../jobs URL. Unknown platforms are skipped, never crash.
_DISPATCH = {
    "greenhouse": ats.fetch_greenhouse,
    "lever": ats.fetch_lever,
    "ashby": ats.fetch_ashby,
    "smartrecruiters": getattr(ats, "fetch_smartrecruiters", None),
    "workable": getattr(ats, "fetch_workable", None),
    "workday": workday.fetch_workday,
}


def _fingerprint(company: str, title: str, link: str) -> str:
    """Stable identity for a posting: normalized company+title, plus link tail.
    Company+title alone would collapse two distinct reqs with the same title; the
    link disambiguates without being defeated by tracking-param churn."""
    tail = link.split("?")[0].rstrip("/").rsplit("/", 1)[-1][:40]
    return f"{normalize_company_name(company)}::{normalize_title(title)}::{tail}"


def load_seen(path: Path = SEEN_PATH) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    except (OSError, json.JSONDecodeError):
        return set()


def fetch_all_keyless(http: RetryingHttpClient | None = None) -> list[RawPosting]:
    """Fetch every roster firm's keyless feed. One bad feed never aborts the run."""
    client = http or RetryingHttpClient()
    postings: list[RawPosting] = []
    for entry in all_source_tokens():
        platform = str(entry.get("platform") or "")
        token = str(entry.get("token") or "")
        company = str(entry.get("company") or "")
        fetcher = _DISPATCH.get(platform)
        if not fetcher or not token:
            continue
        try:
            postings.extend(fetcher(token, company=company, http=client))
        except Exception as exc:  # network / parse / blocked host — log, continue
            print(f"  ! {platform}:{company} failed: {exc}", file=sys.stderr)
    return postings


def load_handshake_drop(path: Path = HANDSHAKE_DROP) -> list[RawPosting]:
    """Merge in Handshake postings dropped by the local hybrid job (if present)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    # Accept the collector's handoff shape ({"candidates":[...]}) or a raw list.
    items = data.get("candidates") or data.get("postings") or (data if isinstance(data, list) else [])
    out = []
    for j in items:
        if isinstance(j, dict):
            out.append(RawPosting(
                company=str(j.get("company") or ""), title=str(j.get("title") or ""),
                link=str(j.get("link") or ""), location=str(j.get("location") or ""),
                posted=str(j.get("posted") or ""), source="handshake", raw=j,
            ))
    return out


def gate(postings: list[RawPosting]) -> list[Candidate]:
    """Keep only real internships at roster firms; assign tier + category."""
    kept: list[Candidate] = []
    for p in postings:
        if not is_relevant_posting(p, target_year=TARGET_YEAR):
            continue
        match = firm_match(p.company)
        if not match:  # not on the Tier-1/2 allowlist
            continue
        kept.append(Candidate(
            tier_hint=str(match.get("tier") or match.get("tier_hint") or ""),
            category=candidate_category(p),
            company=str(match.get("canonical") or match.get("company") or p.company),
            title=p.title, location=p.location, link=p.link,
            source=p.source, posted=p.posted,
        ))
    return kept


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Keyless cloud collection for internship-watch.")
    ap.add_argument("--dry-run", action="store_true", help="no writes; print a summary")
    ap.add_argument("--artifact", default="todays_candidates.json")
    args = ap.parse_args(argv)

    raw = fetch_all_keyless() + load_handshake_drop()
    candidates = gate(raw)

    # Dedup within-run (same fingerprint from two feeds) and against history.
    seen = load_seen()
    fresh: list[Candidate] = []
    seen_this_run: set[str] = set()
    for c in candidates:
        fp = _fingerprint(c.company, c.title, c.link)
        if fp in seen or fp in seen_this_run:
            continue
        seen_this_run.add(fp)
        fresh.append(c)

    print(f"fetched {len(raw)} raw · {len(candidates)} at roster firms · "
          f"{len(fresh)} NEW (not in seen_postings)", file=sys.stderr)

    if args.dry_run:
        for c in fresh[:25]:
            print(f"  [{c.tier_hint}] {c.company} — {c.title[:55]} ({c.source})")
        return 0

    write_handoff(fresh, path=args.artifact, run_date=datetime.now(timezone.utc).date().isoformat())
    # Remember everything we surfaced today so tomorrow it isn't re-reported.
    all_fps = sorted(seen | {_fingerprint(c.company, c.title, c.link) for c in candidates})
    SEEN_PATH.write_text(
        json.dumps({"seen": all_fps, "updated": datetime.now(timezone.utc).isoformat()},
                   indent=0) + "\n", encoding="utf-8")
    print(f"wrote {args.artifact} ({len(fresh)} new) + seen_postings.json ({len(all_fps)} known)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
