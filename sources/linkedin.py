from __future__ import annotations

from typing import Any

from models import RawPosting


def fetch_linkedin(
    *,
    apify_token: str,
    actor_id: str,
    input_payload: dict[str, Any] | None = None,
) -> list[RawPosting]:
    from apify_client import ApifyClient

    client = ApifyClient(apify_token)
    run_input = input_payload or {
        "keywords": "2027 summer internship analyst strategy finance consulting",
        "location": "United States",
    }
    run = client.actor(actor_id).call(run_input=run_input)
    dataset_id = run.get("defaultDatasetId")
    postings: list[RawPosting] = []
    for item in client.dataset(dataset_id).iterate_items():
        if not isinstance(item, dict):
            continue
        postings.append(
            RawPosting(
                company=str(item.get("companyName") or item.get("company") or ""),
                title=str(item.get("title") or ""),
                link=str(item.get("url") or item.get("link") or ""),
                location=str(item.get("location") or ""),
                posted=str(item.get("postedAt") or item.get("listedAt") or ""),
                source="linkedin",
                description=str(item.get("description") or ""),
                raw=item,
            )
        )
    return postings
