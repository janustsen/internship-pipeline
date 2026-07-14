from __future__ import annotations

import json

import pytest

from cloud_judge import FactCheckResult, compose_report, judge_candidates, run_cloud_judge
from config import Config, ConfigError


def test_missing_required_env_fails_fast(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    with pytest.raises(ConfigError, match="ADZUNA_APP_ID"):
        Config.from_env(env_path=tmp_path / ".env", required=("ADZUNA_APP_ID", "ADZUNA_APP_KEY"))


def test_cloud_judge_fact_checks_tier_sorts_and_pushes(tmp_path) -> None:
    artifact = {
        "generated_at": "2026-07-10T00:00:00+00:00",
        "run_date": "2026-07-10",
        "candidate_count": 5,
        "candidates": [
            _candidate("T2", "Jefferies", "2027 Summer Analyst Program", "https://x/t2"),
            _candidate("T3", "Brattle Group", "2027 Summer Analyst Program", "https://x/t3"),
            _candidate("T1", "JPMorgan", "2027 Summer Analyst Program", "https://x/t1"),
            _candidate("T1", "JPMorgan", "2027 Summer Analyst Program", "https://x/closed"),
            _candidate("T1", "Random Startup", "2027 Summer Analyst Program", "https://x/random"),
        ],
    }
    path = tmp_path / "todays_candidates.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    pushed = []

    report = run_cloud_judge(
        artifact_path=path,
        push=pushed.append,
        fact_checker=lambda row: FactCheckResult(False, "closed")
        if row["link"].endswith("closed")
        else FactCheckResult(True),
    )

    assert pushed == [report]
    assert report.startswith("🔔 NEWLY OPEN")
    assert report.index("JPMorgan") < report.index("Jefferies") < report.index("Brattle Group")
    assert "closed" not in report
    assert "Random Startup" not in report


def test_empty_cloud_report_is_short() -> None:
    report = compose_report([])
    assert len(report.splitlines()) <= 5
    assert "No new open internships today." in report


def test_judge_trusts_ats_sourced_without_fact_check() -> None:
    # An ATS/Workday posting came from a live keyless feed — it is trusted as-is,
    # so even a rejecting fact_checker must not drop it (the 403-fragility fix).
    payload = {
        "generated_at": "2026-07-10T00:00:00+00:00",
        "run_date": "2026-07-10",
        "candidate_count": 1,
        "candidates": [
            {**_candidate("T1", "JPMorgan", "2027 Summer Analyst Program", "https://x/gh"),
             "source": "greenhouse"},
        ],
    }
    accepted = judge_candidates(payload, fact_checker=lambda _row: FactCheckResult(False, "closed"))
    assert [row["company"] for row in accepted] == ["JPMorgan"]


def test_judge_candidates_drops_role_mismatches() -> None:
    payload = {
        "generated_at": "2026-07-10T00:00:00+00:00",
        "run_date": "2026-07-10",
        "candidate_count": 1,
        "candidates": [_candidate("T1", "JPMorgan", "2027 New Grad Analyst Program", "https://x/ng")],
    }
    assert judge_candidates(payload, fact_checker=lambda _row: FactCheckResult(True)) == []


def _candidate(tier: str, company: str, title: str, link: str) -> dict[str, str]:
    return {
        "tier_hint": tier,
        "category": "business",
        "company": company,
        "title": title,
        "location": "New York",
        "link": link,
        "source": "test",
        "posted": "2026-07-10",
    }
