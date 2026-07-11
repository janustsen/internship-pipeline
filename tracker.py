from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from models import Candidate, REQUIRED_CANDIDATE_FIELDS


TRACKER_HEADERS = ["recorded_at", *REQUIRED_CANDIDATE_FIELDS]


def append_tracker(
    candidates: Iterable[Candidate],
    *,
    path: str | Path = "Internship_Digest.xlsx",
) -> int:
    rows = list(candidates)
    if not rows:
        return 0

    try:
        from openpyxl import Workbook, load_workbook
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise RuntimeError("openpyxl is required to append Internship_Digest.xlsx") from exc

    target = Path(path)
    if target.exists():
        workbook = load_workbook(target)
        sheet = workbook.active
        _ensure_headers(sheet)
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Internships"
        sheet.append(TRACKER_HEADERS)

    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for candidate in rows:
        data = candidate.to_json()
        sheet.append([recorded_at, *[data[field] for field in REQUIRED_CANDIDATE_FIELDS]])
    workbook.save(target)
    return len(rows)


def _ensure_headers(sheet) -> None:
    values = [cell.value for cell in sheet[1]]
    if values[: len(TRACKER_HEADERS)] == TRACKER_HEADERS:
        return
    if all(value is None for value in values):
        for column, header in enumerate(TRACKER_HEADERS, start=1):
            sheet.cell(row=1, column=column, value=header)
        return
    raise ValueError("existing tracker has unexpected headers")
