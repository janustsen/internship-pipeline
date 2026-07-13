"""Workday source — keyless fetch of a firm's Workday jobs feed.

Most bulge-bracket banks and large corporates run Workday, which exposes an
unauthenticated JSON search endpoint:

    POST https://{host}/wday/cxs/{tenant}/{site}/jobs
    body: {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "..."}
    -> {"total": N, "jobPostings": [{"title", "externalPath", "locationsText",
                                     "postedOn", "bulletFields"}, ...]}

This is the recall unlock for the ~145 roster firms with no ATS token: it runs in
the cloud routine with no keys and no login. The roster stores the full jobs
endpoint URL as the token, e.g.:

    ("workday", "https://citi.wd5.myworkdayjobs.com/wday/cxs/citi/2/jobs")

Postings are pre-narrowed with intern/analyst search terms; final relevance +
firm gating is done downstream by filters.py (same as every other source).
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from http_client import RetryingHttpClient
from models import RawPosting

# Search terms that pre-narrow the feed to internship-shaped roles. Kept broad;
# filters.is_relevant_posting() applies the authoritative intern/cycle gate.
_SEARCH_TERMS = ("intern", "summer analyst", "sophomore")
_PAGE_LIMIT = 20
_MAX_PAGES = 2  # per term; caps a runaway feed while covering fresh postings


def _build_link(endpoint: str, external_path: str) -> str:
    """Turn a Workday `externalPath` into a public apply URL.

    endpoint: .../wday/cxs/{tenant}/{site}/jobs
    public:   https://{host}/en-US/{site}{externalPath}
    """
    if not external_path:
        return endpoint
    parts = urlsplit(endpoint)
    seg = [s for s in parts.path.split("/") if s]  # [wday, cxs, tenant, site, jobs]
    site = seg[3] if len(seg) >= 5 and seg[0] == "wday" and seg[1] == "cxs" else ""
    path = f"/en-US/{site}{external_path}" if site else external_path
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def fetch_workday(
    endpoint: str,
    *,
    company: str = "",
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
) -> list[RawPosting]:
    """Fetch internship-shaped postings from one Workday jobs endpoint.

    endpoint: the full `/wday/cxs/{tenant}/{site}/jobs` URL (stored as the token).
    Returns RawPostings; never raises on a bad feed — returns [] and moves on.
    """
    client = http or RetryingHttpClient()
    seen_paths: set[str] = set()
    postings: list[RawPosting] = []

    for term in _SEARCH_TERMS:
        for page in range(_MAX_PAGES):
            body = {
                "appliedFacets": {},
                "limit": _PAGE_LIMIT,
                "offset": page * _PAGE_LIMIT,
                "searchText": term,
            }
            try:
                response = client.post(
                    endpoint,
                    json=body,
                    headers={"Content-Type": "application/json",
                             "Accept": "application/json"},
                )
                payload = response.json()
            except Exception:  # network / JSON / non-Workday host — skip this feed
                return postings
            if not isinstance(payload, dict):
                break
            batch = payload.get("jobPostings") or []
            if not batch:
                break
            for job in batch:
                if not isinstance(job, dict):
                    continue
                ext = str(job.get("externalPath") or "")
                if ext in seen_paths:
                    continue
                seen_paths.add(ext)
                postings.append(
                    RawPosting(
                        company=company or endpoint,
                        title=str(job.get("title") or ""),
                        link=_build_link(endpoint, ext),
                        location=str(job.get("locationsText") or ""),
                        posted=str(job.get("postedOn") or ""),
                        source="workday",
                        raw=job,
                    )
                )
            if len(batch) < _PAGE_LIMIT:
                break  # last page for this term
    return postings
