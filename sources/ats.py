from __future__ import annotations

from typing import Any, Callable

from filters import firm_match
from http_client import RetryingHttpClient, RetryableHttpError, TokenPruned
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
        location_name = location.get("name") if isinstance(location, dict) else location
        postings.append(
            RawPosting(
                company=company or str(job.get("company_name") or token),
                title=str(job.get("title") or ""),
                link=str(job.get("absolute_url") or ""),
                location=str(location_name or ""),
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
        location = categories.get("location") if isinstance(categories, dict) else ""
        postings.append(
            RawPosting(
                company=company or token,
                title=str(job.get("text") or ""),
                link=str(job.get("hostedUrl") or job.get("applyUrl") or ""),
                location=str(location or ""),
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
    # The live Ashby posting API returns jobs under "jobs" (not "jobPostings"),
    # with fields location/publishedAt/isListed. Keep "jobPostings" as a fallback
    # in case the shape varies by org.
    response = client.get(
        url, params={"includeCompensation": "false"}, token=token, prune_callback=prune_callback
    )
    payload = response.json()
    if isinstance(payload, dict):
        jobs = payload.get("jobs") or payload.get("jobPostings") or []
    else:
        jobs = []
    postings: list[RawPosting] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("isListed") is False:
            continue
        location = job.get("location") or job.get("locationName") or ""
        postings.append(
            RawPosting(
                company=company or token,
                title=str(job.get("title") or ""),
                link=str(job.get("jobUrl") or job.get("applyUrl") or ""),
                location=str(location),
                posted=str(job.get("publishedAt") or job.get("publishedDate") or ""),
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
        if not isinstance(payload, dict):
            break
        jobs = payload.get("results") or payload.get("jobs") or []
        if not isinstance(jobs, list):
            jobs = []
        for job in jobs:
            if isinstance(job, dict):
                postings.append(_workable_posting(job, company=company or token))
        next_url, cursor = _workable_next(payload, base_url=base_url)
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
        token_pruner = _platform_pruner(prune_callback, platform)
        try:
            postings.extend(
                fetcher(
                    token_info["token"],
                    company=token_info.get("company", ""),
                    http=http,
                    prune_callback=token_pruner,
                )
            )
        except (TokenPruned, RetryableHttpError):
            continue
    return postings


def discover_tokens(candidates: list[dict[str, str]], store) -> int:
    # Discovery is intentionally queue-only. The collector must not call these
    # tokens until review_candidates promotes them into active_tokens.
    pending: list[dict[str, str]] = []
    for candidate in candidates:
        match = firm_match(candidate.get("company", ""))
        if match is None:
            continue
        queued = dict(candidate)
        queued["company"] = match["canonical"]
        pending.append(queued)
    return store.add_pending_tokens(pending)


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
    company_name = (
        company_payload.get("name") if isinstance(company_payload, dict) else company_payload
    )
    location_name = ""
    if isinstance(location, dict):
        location_name = str(location.get("city") or location.get("name") or "")
    else:
        location_name = str(location or "")
    return RawPosting(
        company=str(company_name or company),
        title=str(job.get("name") or job.get("title") or ""),
        link=str(job.get("ref") or job.get("applyUrl") or job.get("url") or ""),
        location=location_name,
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


def _workable_next(payload: dict[str, Any], *, base_url: str) -> tuple[str | None, str | None]:
    paging = payload.get("paging") if isinstance(payload.get("paging"), dict) else {}
    for next_value in (paging.get("next"), payload.get("next")):
        if not next_value:
            continue
        if isinstance(next_value, str):
            if next_value.startswith("http"):
                return next_value, None
            return base_url, next_value
        if isinstance(next_value, dict):
            url = next_value.get("url") or next_value.get("href")
            if isinstance(url, str) and url.startswith("http"):
                return url, None
            cursor = (
                next_value.get("cursor")
                or next_value.get("token")
                or next_value.get("offset")
                or next_value.get("next")
            )
            if cursor:
                return base_url, str(cursor)
    return None, None


def _platform_pruner(
    prune_callback: Callable[[str], None] | None,
    platform: str,
) -> Callable[[str], None] | None:
    if prune_callback is None:
        return None

    def prune(token: str) -> None:
        try:
            prune_callback(token, platform=platform)  # type: ignore[call-arg]
        except TypeError:
            prune_callback(token)

    return prune
