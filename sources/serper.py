from __future__ import annotations

from typing import Any

from http_client import RetryingHttpClient
from models import RawPosting


SERPER_URL = "https://google.serper.dev/search"


# Serper's FREE plan rejects advanced-operator queries (`site:`, `OR`, and
# heavy phrase-quoting) with HTTP 400 "Query pattern not allowed for free
# accounts". These are plain-keyword queries the free tier accepts; the firm
# gate downstream keeps only target-firm results. A paid Serper plan would
# unlock `site:boards.greenhouse.io`-style ATS discovery — see review_candidates.
DEFAULT_QUERIES = [
    "2027 summer analyst internship finance",
    "2027 summer internship consulting strategy",
    "2027 investment banking summer analyst program",
    "sophomore summer analyst diversity program 2027",
    "2027 private equity summer internship",
    "2027 quantitative trading summer internship",
]


def fetch_serper(
    *,
    api_key: str,
    http: RetryingHttpClient | None = None,
    queries: list[str] | None = None,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    search_queries = queries or DEFAULT_QUERIES
    postings: list[RawPosting] = []
    for query in search_queries:
        try:
            response = client.post(
                SERPER_URL,
                json={"q": query, "num": 20},
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            )
        except Exception:  # one rejected/failed query must not kill the source
            continue
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
