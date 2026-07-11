from __future__ import annotations

from http_client import RetryingHttpClient
from sources.adzuna import fetch_adzuna
from sources.ats import fetch_ashby, fetch_smartrecruiters, fetch_workable
from sources.handshake import fetch_handshake, read_handshake_csv
from sources.linkedin import fetch_linkedin
from sources.serper import fetch_serper
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


def test_adzuna_pages_until_exhausted_uses_what_or() -> None:
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
    # `what_or` (OR semantics) — a `what` AND-query matched zero postings, the
    # bug that made this whole source silently return nothing.
    for call in http.session.requests:
        params = call[2]["params"]
        assert "what" not in params
        assert params["what_or"]
        assert params["max_days_old"] == 7


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


def test_serper_drops_listing_pages_keeps_postings() -> None:
    payload = {
        "organic": [
            {"title": "2027 Summer Analyst Program - Goldman Sachs", "link": "https://gs/1"},
            {"title": "1,000+ Finance Summer Internship jobs in United States", "link": "https://li/x"},
            {"title": "151 Private Equity Intern jobs in United States", "link": "https://li/y"},
        ]
    }
    http = client_for([FakeResponse(payload)])

    postings = fetch_serper(api_key="k", http=http, queries=["x"])

    titles = [p.title for p in postings]
    assert titles == ["2027 Summer Analyst Program - Goldman Sachs"]


def test_handshake_skips_when_no_search_url() -> None:
    calls = []

    def runner(*args, **kwargs):  # must never be invoked
        calls.append(args)

    assert fetch_handshake(search_url="", runner=runner) == []
    assert calls == []


def test_handshake_reads_real_csv_columns(tmp_path) -> None:
    # The vendored scraper writes "Company Name"/"Job Title"/"Job Link"/... —
    # the wrapper previously read company/link/location and got blanks.
    csv_path = tmp_path / "handshake_jobs.csv"
    csv_path.write_text(
        "Company Name,Job Title,Job Link,Job Location,Job PostedAt\n"
        "Jane Street,2027 Summer Analyst,https://x/1,New York,2026-07-10\n",
        encoding="utf-8",
    )

    postings = read_handshake_csv(str(csv_path))

    assert len(postings) == 1
    assert postings[0].company == "Jane Street"
    assert postings[0].title == "2027 Summer Analyst"
    assert postings[0].link == "https://x/1"
    assert postings[0].location == "New York"
    assert postings[0].posted == "2026-07-10"


def test_linkedin_maps_actor_output_fields() -> None:
    # Actor input uses `keyword` (a list); output uses jobTitle/companyName/jobUrl.
    class FakeClient:
        def __init__(self, _token):
            self.inputs = []

        def actor(self, _id):
            outer = self

            class _Actor:
                def call(self, run_input):
                    outer.inputs.append(run_input)
                    return {"defaultDatasetId": "ds1"}

            return _Actor()

        def dataset(self, _id):
            class _DS:
                def iterate_items(self):
                    return iter(
                        [
                            {
                                "companyName": "Goldman Sachs",
                                "jobTitle": "2027 Summer Analyst",
                                "jobUrl": "https://li/1",
                                "location": "New York",
                            }
                        ]
                    )

            return _DS()

    client = FakeClient("t")
    postings = fetch_linkedin(
        apify_token="t",
        actor_id="a",
        keywords=["summer analyst"],
        client_factory=lambda _t: client,
    )

    assert client.inputs[0]["keyword"] == ["summer analyst"]
    assert len(postings) == 1
    assert postings[0].company == "Goldman Sachs"
    assert postings[0].title == "2027 Summer Analyst"
    assert postings[0].link == "https://li/1"


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
