"""Live coverage check for the ATS tokens declared in target_firms.py.

Hits each firm's ATS board through the real pipeline code and reports how many
jobs and how many *relevant internships* it yields, so you can see at a glance
which target firms the pipeline can actually watch — and catch a silently-dead
token before it costs you a listing.

Usage:
    python3 verify_tokens.py                 # check every token in target_firms
    python3 verify_tokens.py --min-interns 1 # only show boards with >=1 internship
    python3 verify_tokens.py --platform greenhouse
"""
from __future__ import annotations

import argparse

from filters import is_relevant_posting
from http_client import RetryableHttpError, RetryingHttpClient, TokenPruned
from sources import ats
from target_firms import all_source_tokens

FETCHERS = {
    "greenhouse": ats.fetch_greenhouse,
    "lever": ats.fetch_lever,
    "ashby": ats.fetch_ashby,
    "smartrecruiters": ats.fetch_smartrecruiters,
    "workable": ats.fetch_workable,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ATS tokens in target_firms.py")
    parser.add_argument("--platform", choices=sorted(FETCHERS), help="limit to one platform")
    parser.add_argument("--min-interns", type=int, default=0, help="only show boards with >= N")
    args = parser.parse_args(argv)

    http = RetryingHttpClient()
    tokens = all_source_tokens()
    if args.platform:
        tokens = [t for t in tokens if t["platform"] == args.platform]

    print(f"{'FIRM':<28}{'TIER':<5}{'PLATFORM':<16}{'TOKEN':<28}{'STATUS':<9}{'JOBS':>6}{'INT':>5}")
    print("-" * 97)
    dead: list[str] = []
    total_jobs = total_int = ok = 0
    for t in tokens:
        fetcher = FETCHERS.get(t["platform"])
        if fetcher is None:
            continue
        try:
            postings = fetcher(t["token"], company=t["company"], http=http)
            interns = [p for p in postings if is_relevant_posting(p)]
            if len(interns) < args.min_interns:
                continue
            status = "OK" if postings else "EMPTY"
            ok += 1
            total_jobs += len(postings)
            total_int += len(interns)
            print(f"{t['company'][:27]:<28}{t['tier']:<5}{t['platform']:<16}"
                  f"{t['token'][:27]:<28}{status:<9}{len(postings):>6}{len(interns):>5}")
        except (TokenPruned, RetryableHttpError) as exc:
            dead.append(f"{t['company']} ({t['platform']}:{t['token']}) — {type(exc).__name__}")
            print(f"{t['company'][:27]:<28}{t['tier']:<5}{t['platform']:<16}"
                  f"{t['token'][:27]:<28}{'DEAD':<9}{'-':>6}{'-':>5}")
    print("-" * 97)
    print(f"Reachable: {ok}  Dead: {len(dead)}  Total jobs: {total_jobs}  Internships: {total_int}")
    if dead:
        print("\nDead/unreachable tokens (fix or remove from target_firms.py):")
        for line in dead:
            print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
