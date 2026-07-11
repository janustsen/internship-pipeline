from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from models import Candidate, REQUIRED_CANDIDATE_FIELDS


def artifact_payload(
    candidates: Iterable[Candidate | dict[str, str]],
    *,
    generated_at: str | None = None,
    run_date: str | None = None,
) -> dict[str, object]:
    rows = [_candidate_dict(candidate) for candidate in candidates]
    return {
        "generated_at": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_date": run_date or date.today().isoformat(),
        "candidate_count": len(rows),
        "candidates": rows,
    }


def write_handoff(
    candidates: Iterable[Candidate | dict[str, str]],
    *,
    path: str | Path = "todays_candidates.json",
    generated_at: str | None = None,
    run_date: str | None = None,
) -> dict[str, object]:
    payload = artifact_payload(candidates, generated_at=generated_at, run_date=run_date)
    validate_payload(payload)
    target = Path(path)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def validate_payload(payload: dict[str, object]) -> None:
    for key in ("generated_at", "run_date", "candidate_count", "candidates"):
        if key not in payload:
            raise ValueError(f"handoff artifact missing {key}")
    candidates = payload["candidates"]
    if not isinstance(candidates, list):
        raise ValueError("handoff artifact candidates must be a list")
    if payload["candidate_count"] != len(candidates):
        raise ValueError("candidate_count does not match candidates length")
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate {index} is not an object")
        missing = [field for field in REQUIRED_CANDIDATE_FIELDS if field not in candidate]
        if missing:
            raise ValueError(f"candidate {index} missing fields: {', '.join(missing)}")


def commit_and_push(
    path: str | Path = "todays_candidates.json",
    *,
    no_push: bool = False,
    dry_run: bool = False,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[Sequence[str]]:
    if dry_run:
        return []
    target = str(path)
    commands: list[Sequence[str]] = []
    add_cmd = ["git", "add", target]
    runner(add_cmd, check=True)
    commands.append(add_cmd)

    diff_cmd = ["git", "diff", "--cached", "--quiet", "--", target]
    diff_result = runner(diff_cmd, check=False)
    commands.append(diff_cmd)
    if getattr(diff_result, "returncode", 1) == 0:
        return commands

    commit_cmd = ["git", "commit", "-m", "Update internship candidates"]
    runner(commit_cmd, check=True)
    commands.append(commit_cmd)
    if not no_push:
        push_cmd = ["git", "push"]
        runner(push_cmd, check=True)
        commands.append(push_cmd)
    return commands


def _candidate_dict(candidate: Candidate | dict[str, str]) -> dict[str, str]:
    if isinstance(candidate, Candidate):
        return candidate.to_json()
    return {field: str(candidate.get(field, "")) for field in REQUIRED_CANDIDATE_FIELDS}
