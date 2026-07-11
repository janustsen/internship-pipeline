from __future__ import annotations

import argparse
import json

from collector import collect_from_sources, run_collector
from coverage_report import CoverageReport
from handoff import commit_and_push
from models import RawPosting
from store import InternshipStore
from tests.conftest import RecordingRunner


def test_handoff_schema_and_git_commit_push(tmp_path) -> None:
    runner = RecordingRunner(diff_returncode=1)
    artifact = tmp_path / "todays_candidates.json"
    args = _args(tmp_path, artifact=artifact, dry_run=False, no_push=False, source=["ats"])
    store = InternshipStore(tmp_path / "seen.db")
    runner = RecordingRunner(diff_returncode=1)
    try:
        result = run_collector(
            args,
            fetchers={
                "ats": lambda: [
                    RawPosting("JPMorgan", "2027 Summer Analyst Program", "https://x/1", "ats"),
                    RawPosting("Morgan Stanley", "2027 Sophomore Summer Analyst", "https://x/2", "ats"),
                    RawPosting("Goldman Sachs", "2027 Summer Associate Internship", "https://x/3", "ats"),
                ]
            },
            store=store,
            git_runner=runner,
        )
        assert result.artifact["candidate_count"] == 3
        payload = json.loads(artifact.read_text())
        assert payload["candidate_count"] == len(payload["candidates"])
    finally:
        store.close()

    commands = commit_and_push(artifact, runner=runner)
    assert ["git", "commit", "-m", "Update internship candidates"] in [cmd for cmd, _ in runner.commands]
    assert ["git", "push"] in [cmd for cmd, _ in runner.commands]
    assert commands


def test_coverage_report_has_no_silent_drops(tmp_path) -> None:
    store = InternshipStore(tmp_path / "seen.db")
    duplicate = RawPosting("JPMorgan", "2027 Summer Analyst Program", "https://x/dup", "adzuna")
    store.dedupe(
        [
            # Seed semantic duplicate.
            __import__("models").Candidate(
                "T1",
                "business",
                "JPMorgan",
                "2027 Summer Analyst Program",
                "NY",
                "https://old",
                "seed",
            )
        ],
        dry_run=False,
    )
    args = _args(tmp_path, source=["adzuna"], dry_run=True, no_push=True)
    raw = [
        RawPosting("Morgan Stanley", "2027 Summer Analyst Program 1", "https://x/1", "adzuna"),
        RawPosting("Morgan Stanley", "2027 Summer Analyst Program 2", "https://x/2", "adzuna"),
        RawPosting("Goldman Sachs", "2027 Summer Analyst Program 3", "https://x/3", "adzuna"),
        RawPosting("Evercore", "2027 Summer Analyst Program 4", "https://x/4", "adzuna"),
        RawPosting("Random Startup", "2027 Summer Analyst Program 5", "https://x/5", "adzuna"),
        RawPosting("Morgan & Morgan", "2027 Summer Analyst Program 6", "https://x/6", "adzuna"),
        RawPosting("Unknown Co", "2027 Summer Analyst Program 7", "https://x/7", "adzuna"),
        RawPosting("JPMorgan", "2027 Software Engineering Internship", "https://x/8", "adzuna"),
        RawPosting("JPMorgan", "2027 New Grad Analyst Program", "https://x/9", "adzuna"),
        duplicate,
    ]
    try:
        result = run_collector(args, fetchers={"adzuna": lambda: raw}, store=store)
        line = result.coverage.lines()[0]
        assert "raw=10" in line
        assert "kept=4" in line
        assert "non_allowlisted=3" in line
        assert "irrelevant=2" in line
        assert "duplicate=1" in line
    finally:
        store.close()


def test_dead_source_does_not_abort_daily_run() -> None:
    coverage = CoverageReport()
    candidates = collect_from_sources(
        {
            "linkedin": _dead_source,
            "adzuna": lambda: [
                RawPosting("JPMorgan", "2027 Summer Analyst Program", "https://x/1", "adzuna")
            ],
        },
        coverage=coverage,
    )

    assert len(candidates) == 1
    assert coverage.source("linkedin").errors


def test_cli_flags_select_source_and_dry_run_skips_mutation_and_push(tmp_path) -> None:
    store = InternshipStore(tmp_path / "seen.db")
    artifact = tmp_path / "todays_candidates.json"
    args = _args(
        tmp_path,
        artifact=artifact,
        source=["adzuna"],
        since="2026-07-08",
        dry_run=True,
        no_push=True,
    )
    calls = []
    try:
        result = run_collector(
            args,
            fetchers={
                "adzuna": lambda: calls.append("adzuna")
                or [RawPosting("JPMorgan", "2027 Summer Analyst Program", "https://x/1", "adzuna")],
                "ats": lambda: calls.append("ats") or [],
            },
            store=store,
            git_runner=RecordingRunner(),
        )

        assert calls == ["adzuna"]
        assert result.artifact["candidate_count"] == 1
        assert store.has_seen_url("https://x/1") is False
    finally:
        store.close()


def _dead_source():
    raise RuntimeError("apify down")


def _args(
    tmp_path,
    *,
    artifact=None,
    source=None,
    since=None,
    dry_run=True,
    no_push=True,
):
    return argparse.Namespace(
        dry_run=dry_run,
        no_push=no_push,
        source=source,
        since=since,
        db=str(tmp_path / "seen.db"),
        artifact=str(artifact or tmp_path / "todays_candidates.json"),
        env_file=str(tmp_path / ".env"),
        strict_env=False,
    )
