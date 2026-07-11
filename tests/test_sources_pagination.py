from __future__ import annotations

from http_client import RetryingHttpClient
from sources.adzuna import fetch_adzuna
from sources.ats import fetch_ashby, fetch_smartrecruiters, fetch_workable
from tests.conftest import FakeResponse, FakeSession


def no_sleep(_seconds: float) -> None:
    return None


def client_for(responses):
    return RetryingHttpClient(
        session=FakeSession(responses),
        sleeper=no_sleep,
        jitter=lambda: 0.0,
    )


def test_smartrecruiters_fetches_all_pages() -> None:
    pages = [
        FakeResponse({"content": [_sr_job(i) for i in range(100)], "totalFound": 250}),
        FakeResponse({"content": [_sr_job(i) for i in range(100, 200)], "totalFound": 250}),
        FakeResponse({"content": [_sr_job(i) for i in range(200, 250)], "totalFound": 250}),
    ]
    http = client_for(pages)

    postings = fetch_smartrecruiters("acme", company="JPMorgan", http=http)

    assert len(postings) == 250
    offsets = [call[2]["params"]["offset"] for call in http.session.requests]
    assert offsets == [0, 100, 200]


def test_workable_follows_v3_cursor() -> None:
    pages = [
        FakeResponse({"results": [_workable_job(1)], "paging": {"next": "cursor-2"}}),
        FakeResponse({"results": [_workable_job(2)], "paging": {"next": "cursor-3"}}),
        FakeResponse({"results": [_workable_job(3)], "paging": {}}),
    ]
    http = client_for(pages)

    postings = fetch_workable("acme", company="JPMorgan", http=http)

    assert len(postings) == 3
    bodies = [call[2]["json"] for call in http.session.requests]
    assert "cursor" not in bodies[0]
    assert bodies[1]["cursor"] == "cursor-2"
    assert bodies[2]["cursor"] == "cursor-3"


def test_adzuna_pages_until_exhausted_with_max_days_old_two() -> None:
    pages = [
        FakeResponse({"results": [_adzuna_job(i) for i in range(50)]}),
        FakeResponse({"results": [_adzuna_job(i) for i in range(50, 75)]}),
    ]
    http = client_for(pages)

    postings = fetch_adzuna(app_id="id", app_key="key", http=http)

    assert len(postings) == 75
    urls = [call[1] for call in http.session.requests]
    assert urls == [
        "https://api.adzuna.com/v1/api/jobs/us/search/1",
        "https://api.adzuna.com/v1/api/jobs/us/search/2",
    ]
    assert all(call[2]["params"]["max_days_old"] == 2 for call in http.session.requests)


def test_ashby_reads_jobs_key_and_maps_live_fields() -> None:
    # Live Ashby posting API returns "jobs" (not "jobPostings") with
    # location/publishedAt/isListed fields. Regression guard for a real
    # coverage bug that silently dropped every Ashby posting.
    payload = {
        "apiVersion": "1",
        "jobs": [
            {
                "title": "2027 Summer Analyst Intern",
                "jobUrl": "https://jobs.ashbyhq.com/ramp/abc",
                "location": "New York",
                "publishedAt": "2026-07-09",
                "isListed": True,
            },
            {
                "title": "Hidden Role",
                "jobUrl": "https://jobs.ashbyhq.com/ramp/xyz",
                "location": "Remote",
                "isListed": False,
            },
        ],
    }
    http = client_for([FakeResponse(payload)])

    postings = fetch_ashby("ramp", company="Ramp", http=http)

    assert len(postings) == 1  # isListed=False is skipped
    assert postings[0].title == "2027 Summer Analyst Intern"
    assert postings[0].link == "https://jobs.ashbyhq.com/ramp/abc"
    assert postings[0].location == "New York"
    assert postings[0].posted == "2026-07-09"


def _sr_job(index: int) -> dict:
    return {
        "name": f"2027 Summer Analyst Program {index}",
        "ref": f"https://example.com/sr/{index}",
        "company": {"name": "JPMorgan"},
        "location": {"city": "New York"},
    }


def _workable_job(index: int) -> dict:
    return {
        "title": f"2027 Summer Analyst Program {index}",
        "url": f"https://example.com/workable/{index}",
        "company": "JPMorgan",
        "location": {"city": "New York"},
    }


def _adzuna_job(index: int) -> dict:
    return {
        "title": f"2027 Summer Analyst Program {index}",
        "redirect_url": f"https://example.com/adzuna/{index}",
        "company": {"display_name": "JPMorgan"},
        "location": {"area": ["US", "New York"]},
    }
