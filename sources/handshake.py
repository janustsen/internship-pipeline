from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from models import RawPosting


# The vendored handshake_scraper.py CLI is: -u <search_url> -p <pages> -t <throttle>.
# It reads a persistent Chrome profile at ~/.handshake_chrome_profile (set inside
# the scraper, not via a flag) and always writes handshake_jobs.csv in the cwd.
# It needs a one-time interactive SSO login in that profile before it can run
# unattended. The search URL is school-specific (e.g. a Stanford Handshake
# internship search containing page=1) and comes from HANDSHAKE_SEARCH_URL.


def fetch_handshake(
    *,
    search_url: str = "",
    script_path: str = "handshake_scraper.py",
    output_csv: str = "handshake_jobs.csv",
    pages: int = 1000,
    throttle: float = 10.0,
    runner=subprocess.run,
) -> list[RawPosting]:
    if not search_url:
        # Not configured — skip cleanly rather than launching a browser with no target.
        return []
    script = Path(script_path)
    if not script.exists():
        raise FileNotFoundError(f"Handshake scraper not found: {script}")
    command = [
        sys.executable,
        str(script),
        "-u",
        search_url,
        "-p",
        str(pages),
        "-t",
        str(throttle),
    ]
    runner(command, check=True, timeout=600)
    return read_handshake_csv(output_csv)


# Column names written by the vendored scraper's df_out.
_COL_COMPANY = ("Company Name", "company_name", "company", "Employer")
_COL_TITLE = ("Job Title", "title")
_COL_LINK = ("Job Link", "url", "link", "URL")
_COL_LOCATION = ("Job Location", "location", "Location")
_COL_POSTED = ("Job PostedAt", "posted_at", "posted", "Posted")


def _first(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    return ""


def read_handshake_csv(path: str = "handshake_jobs.csv") -> list[RawPosting]:
    target = Path(path)
    if not target.exists():
        return []
    postings: list[RawPosting] = []
    with target.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            postings.append(
                RawPosting(
                    company=_first(row, _COL_COMPANY),
                    title=_first(row, _COL_TITLE),
                    link=_first(row, _COL_LINK),
                    location=_first(row, _COL_LOCATION),
                    posted=_first(row, _COL_POSTED),
                    source="handshake",
                    description=_first(row, ("Job Description", "description")),
                    raw=dict(row),
                )
            )
    return postings
