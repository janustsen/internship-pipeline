from __future__ import annotations

from datetime import date
from typing import Any

from http_client import RetryingHttpClient
from models import RawPosting


ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"


def fetch_adzuna(
    *,
    app_id: str,
    app_key: str,
    http: RetryingHttpClient | None = None,
    since: str | date | None = None,
    per_page: int = 50,
    max_pages: int = 100,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    postings: list[RawPosting] = []
    for page in range(1, max_pages + 1):
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": per_page,
            "max_days_old": 2,
            "what": "2027 summer internship analyst associate strategy finance consulting",
            "content-type": "application/json",
        }
        if since:
            params["sort_by"] = "date"
        response = client.get(ADZUNA_URL.format(page=page), params=params)
        payload = response.json()
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list) or not results:
            break
        for item in results:
            if isinstance(item, dict):
                postings.append(_posting_from_adzuna(item))
        if len(results) < per_page:
            break
    return postings


def _posting_from_adzuna(item: dict[str, Any]) -> RawPosting:
    company = item.get("company") or {}
    location = item.get("location") or {}
    area = location.get("area") if isinstance(location, dict) else []
    location_text = ", ".join(area) if isinstance(area, list) else str(location or "")
    return RawPosting(
        company=str(company.get("display_name") if isinstance(company, dict) else company or ""),
        title=str(item.get("title") or ""),
        link=str(item.get("redirect_url") or item.get("url") or ""),
        location=location_text,
        posted=str(item.get("created") or ""),
        source="adzuna",
        description=str(item.get("description") or ""),
        raw=item,
    )
