from __future__ import annotations

from typing import Any, Callable

from http_client import RetryingHttpClient, TokenPruned
from models import RawPosting


def fetch_greenhouse(
    token: str,
    *,
    company: str = "",
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    response = client.get(url, params={"content": "true"}, token=token, prune_callback=prune_callback)
    payload = response.json()
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    postings: list[RawPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = job.get("location") or {}
        postings.append(
            RawPosting(
                company=company or str(job.get("company_name") or token),
                title=str(job.get("title") or ""),
                link=str(job.get("absolute_url") or ""),
                location=str(location.get("name") or ""),
                posted=str(job.get("updated_at") or ""),
                source="greenhouse",
                raw=job,
            )
        )
    return postings


def fetch_lever(
    token: str,
    *,
    company: str = "",
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    url = f"https://api.lever.co/v0/postings/{token}"
    response = client.get(url, params={"mode": "json"}, token=token, prune_callback=prune_callback)
    payload = response.json()
    if not isinstance(payload, list):
        return []
    postings: list[RawPosting] = []
    for job in payload:
        if not isinstance(job, dict):
            continue
        categories = job.get("categories") or {}
        postings.append(
            RawPosting(
                company=company or token,
                title=str(job.get("text") or ""),
                link=str(job.get("hostedUrl") or job.get("applyUrl") or ""),
                location=str(categories.get("location") or ""),
                posted=str(job.get("createdAt") or ""),
                source="lever",
                raw=job,
            )
        )
    return postings


def fetch_ashby(
    token: str,
    *,
    company: str = "",
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    response = client.get(url, token=token, prune_callback=prune_callback)
    payload = response.json()
    jobs = payload.get("jobPostings", []) if isinstance(payload, dict) else []
    postings: list[RawPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        location = job.get("locationName") or job.get("location") or ""
        postings.append(
            RawPosting(
                company=company or token,
                title=str(job.get("title") or ""),
                link=str(job.get("jobUrl") or job.get("applyUrl") or ""),
                location=str(location),
                posted=str(job.get("publishedDate") or ""),
                source="ashby",
                raw=job,
            )
        )
    return postings


def fetch_smartrecruiters(
    token: str,
    *,
    company: str = "",
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
    limit: int = 100,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    offset = 0
    postings: list[RawPosting] = []
    while True:
        url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
        response = client.get(
            url,
            params={"status": "PUBLIC", "limit": limit, "offset": offset},
            token=token,
            prune_callback=prune_callback,
        )
        payload = response.json()
        jobs = _smartrecruiters_jobs(payload)
        for job in jobs:
            postings.append(_smartrecruiters_posting(job, company=company or token))
        total = _smartrecruiters_total(payload)
        offset += limit
        if not jobs:
            break
        if total is not None and offset >= total:
            break
        if len(jobs) < limit and total is None:
            break
    return postings


def fetch_workable(
    token: str,
    *,
    company: str = "",
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
) -> list[RawPosting]:
    client = http or RetryingHttpClient()
    base_url = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
    headers = {
        "Origin": "https://apply.workable.com",
        "Referer": f"https://apply.workable.com/{token}/",
    }
    body: dict[str, Any] = {"query": "", "location": [], "workplace": [], "department": []}
    next_url: str | None = base_url
    cursor: str | None = None
    postings: list[RawPosting] = []

    while next_url:
        request_body = dict(body)
        if cursor:
            request_body["cursor"] = cursor
        response = client.post(
            next_url,
            json=request_body,
            headers=headers,
            token=token,
            prune_callback=prune_callback,
        )
        payload = response.json()
        jobs = payload.get("results") or payload.get("jobs") or []
        if not isinstance(jobs, list):
            jobs = []
        for job in jobs:
            if isinstance(job, dict):
                postings.append(_workable_posting(job, company=company or token))
        paging = payload.get("paging") or {}
        next_value = paging.get("next") or payload.get("next")
        if not next_value:
            break
        if isinstance(next_value, str) and next_value.startswith("http"):
            next_url = next_value
            cursor = None
        else:
            next_url = base_url
            cursor = str(next_value)
    return postings


def fetch_ats_tokens(
    tokens: list[dict[str, str]],
    *,
    http: RetryingHttpClient | None = None,
    prune_callback: Callable[[str], None] | None = None,
) -> list[RawPosting]:
    postings: list[RawPosting] = []
    fetchers = {
        "greenhouse": fetch_greenhouse,
        "lever": fetch_lever,
        "ashby": fetch_ashby,
        "smartrecruiters": fetch_smartrecruiters,
        "workable": fetch_workable,
    }
    for token_info in tokens:
        platform = token_info["platform"].lower()
        fetcher = fetchers.get(platform)
        if fetcher is None:
            continue
        try:
            postings.extend(
                fetcher(
                    token_info["token"],
                    company=token_info.get("company", ""),
                    http=http,
                    prune_callback=prune_callback,
                )
            )
        except TokenPruned:
            continue
    return postings


def discover_tokens(candidates: list[dict[str, str]], store) -> int:
    # Discovery is intentionally queue-only. The collector must not call these
    # tokens until review_candidates promotes them into active_tokens.
    return store.add_pending_tokens(candidates)


def _smartrecruiters_jobs(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    jobs = payload.get("content") or payload.get("postings") or payload.get("jobs") or []
    return [job for job in jobs if isinstance(job, dict)]


def _smartrecruiters_total(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("totalFound", "total", "count"):
        value = payload.get(key)
        if isinstance(value, int):
            return value
    return None


def _smartrecruiters_posting(job: dict[str, Any], *, company: str) -> RawPosting:
    company_payload = job.get("company") or {}
    location = job.get("location") or {}
    return RawPosting(
        company=str(company_payload.get("name") or company),
        title=str(job.get("name") or job.get("title") or ""),
        link=str(job.get("ref") or job.get("applyUrl") or job.get("url") or ""),
        location=str(location.get("city") or location.get("name") or ""),
        posted=str(job.get("releasedDate") or job.get("createdOn") or ""),
        source="smartrecruiters",
        raw=job,
    )


def _workable_posting(job: dict[str, Any], *, company: str) -> RawPosting:
    location = job.get("location") or {}
    return RawPosting(
        company=str(job.get("company") or company),
        title=str(job.get("title") or ""),
        link=str(job.get("url") or job.get("shortlink") or job.get("application_url") or ""),
        location=str(location.get("city") if isinstance(location, dict) else location or ""),
        posted=str(job.get("published") or job.get("created_at") or ""),
        source="workable",
        raw=job,
    )
