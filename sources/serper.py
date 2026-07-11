from __future__ import annotations

from typing import Any

from http_client import RetryingHttpClient
from models import RawPosting


SERPER_URL = "https://google.serper.dev/search"


def fetch_serper(
    *,
    api_key: str,
    http: RetryingHttpClient | None = None,
    queries: list[str] | None = None,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    search_queries = queries or [
        'site:jobs.lever.co OR site:boards.greenhouse.io "2027 Summer Analyst"',
        '"2027 summer internship" "strategy" "apply"',
    ]
    postings: list[RawPosting] = []
    for query in search_queries:
        response = client.post(
            SERPER_URL,
            json={"q": query, "num": 20},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        )
        payload = response.json()
        organic = payload.get("organic", []) if isinstance(payload, dict) else []
        if not isinstance(organic, list):
            continue
        for item in organic:
            if isinstance(item, dict):
                postings.append(_posting_from_serper(item))
    return postings


def _posting_from_serper(item: dict[str, Any]) -> RawPosting:
    title = str(item.get("title") or "")
    return RawPosting(
        company=_guess_company(title),
        title=title,
        link=str(item.get("link") or ""),
        location="",
        posted=str(item.get("date") or ""),
        source="serper",
        description=str(item.get("snippet") or ""),
        raw=item,
    )


def _guess_company(title: str) -> str:
    for separator in (" - ", " | ", " at "):
        if separator in title:
            return title.split(separator)[-1].strip()
    return ""
