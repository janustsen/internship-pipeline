from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import requests

from filters import firm_match, is_relevant_posting
from handoff import validate_payload
from target_firms import TIER_ORDER


@dataclass(frozen=True)
class FactCheckResult:
    ok: bool
    reason: str = ""
    deadline: str = ""


def load_artifact(path: str | Path = "todays_candidates.json") -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_payload(payload)
    return payload


def default_fact_checker(candidate: dict[str, str]) -> FactCheckResult:
    try:
        response = requests.get(candidate["link"], timeout=10, allow_redirects=True)
    except requests.RequestException as exc:
        return FactCheckResult(False, f"fetch_failed: {exc}")
    if response.status_code != 200:
        return FactCheckResult(False, f"status_{response.status_code}")
    text = response.text.lower()
    if any(marker in text for marker in ("job is no longer available", "position has closed", "no longer accepting")):
        return FactCheckResult(False, "closed")
    title = candidate.get("title", "").lower()
    company = candidate.get("company", "").lower()
    if title and title.split()[0] not in text:
        return FactCheckResult(False, "role_mismatch")
    if company and company.split()[0] not in text:
        return FactCheckResult(False, "firm_mismatch")
    deadline = _extract_deadline(response.text)
    return FactCheckResult(True, deadline=deadline)


def judge_candidates(
    payload: dict[str, object],
    *,
    fact_checker: Callable[[dict[str, str]], FactCheckResult] = default_fact_checker,
) -> list[dict[str, str]]:
    validate_payload(payload)
    accepted: list[dict[str, str]] = []
    for candidate in payload["candidates"]:  # type: ignore[index]
        if not isinstance(candidate, dict):
            continue
        match = firm_match(str(candidate.get("company") or ""))
        if match is None or match["tier"] not in {"T1", "T2"}:
            continue
        if not is_relevant_posting(candidate):
            continue
        check = fact_checker({key: str(value) for key, value in candidate.items()})
        if not check.ok:
            continue
        row = {key: str(value) for key, value in candidate.items()}
        row["tier_hint"] = match["tier"]
        if check.deadline:
            row["deadline"] = check.deadline
        accepted.append(row)
    accepted.sort(key=lambda row: (TIER_ORDER.get(row["tier_hint"], 99), row["company"], row["title"]))
    return accepted


def compose_report(candidates: Iterable[dict[str, str]]) -> str:
    rows = list(candidates)
    if not rows:
        return "\n".join(
            [
                "No new open internships today.",
                "Checked the bridge artifact and filtered closed or non-T1/T2 postings.",
                "Next run: tomorrow morning.",
            ]
        )
    lines = ["🔔 NEWLY OPEN"]
    for row in rows:
        deadline = f" | deadline: {row['deadline']}" if row.get("deadline") else ""
        lines.append(
            f"{row['tier_hint']} - {row['company']} - {row['title']} "
            f"({row.get('location', '')}){deadline}\n{row['link']}"
        )
    closing = [row for row in rows if row.get("deadline")]
    if closing:
        lines.append("🔴 CLOSING SOON / DEADLINES KNOWN")
        for row in closing:
            lines.append(f"{row['company']} - {row['title']}: {row['deadline']}")
    return "\n".join(lines)


def run_cloud_judge(
    *,
    artifact_path: str | Path = "todays_candidates.json",
    push: Callable[[str], None],
    fact_checker: Callable[[dict[str, str]], FactCheckResult] = default_fact_checker,
) -> str:
    payload = load_artifact(artifact_path)
    accepted = judge_candidates(payload, fact_checker=fact_checker)
    report = compose_report(accepted)
    push(report)
    return report


def _extract_deadline(text: str) -> str:
    match = re.search(r"(deadline|apply by)[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})", text)
    return match.group(2) if match else ""
