from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from models import RawPosting


def fetch_handshake(
    *,
    script_path: str = "handshake_scraper.py",
    output_csv: str = "handshake_jobs.csv",
    profile_path: str = "~/.handshake_chrome_profile",
    runner=subprocess.run,
) -> list[RawPosting]:
    script = Path(script_path)
    if not script.exists():
        raise FileNotFoundError(f"Handshake scraper not found: {script}")
    command = [
        sys.executable,
        str(script),
        "-u",
        "-t",
        "--profile",
        str(Path(profile_path).expanduser()),
        "--lang",
        "en-US",
        "--pages",
        "1000",
        "--output",
        output_csv,
    ]
    runner(command, check=True, timeout=540)
    return read_handshake_csv(output_csv)


def read_handshake_csv(path: str = "handshake_jobs.csv") -> list[RawPosting]:
    target = Path(path)
    if not target.exists():
        return []
    postings: list[RawPosting] = []
    with target.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            postings.append(
                RawPosting(
                    company=str(row.get("company") or row.get("Employer") or ""),
                    title=str(row.get("title") or row.get("Job Title") or ""),
                    link=str(row.get("link") or row.get("URL") or ""),
                    location=str(row.get("location") or row.get("Location") or ""),
                    posted=str(row.get("posted") or row.get("Posted") or ""),
                    source="handshake",
                    raw=dict(row),
                )
            )
    return postings
