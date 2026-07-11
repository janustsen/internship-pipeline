from __future__ import annotations

from typing import Any, Callable

from models import RawPosting


# Proven keyword sweep (mirrors the original orchestrator, widened for the
# 2027 cycle). LinkedIn keyword search is fuzzy, so several targeted queries
# recall far more target-firm postings than one broad string. The firm gate +
# relevance filter downstream keep precision, so we cast wide here.
DEFAULT_KEYWORDS = [
    "investment banking intern",
    "summer analyst",
    "strategy intern",
    "consulting intern",
    "private equity intern",
    "venture capital intern",
    "quantitative research intern",
    "business operations intern",
    "corporate development intern",
]


def fetch_linkedin(
    *,
    apify_token: str,
    actor_id: str,
    keywords: list[str] | None = None,
    max_items: int = 150,
    client_factory: Callable[[str], Any] | None = None,
) -> list[RawPosting]:
    """Run the Apify LinkedIn actor once per keyword and normalize the items.

    Uses the actor's proven input schema (``keyword`` is a LIST, plus the
    ``internship`` jobType/experienceLevel filters and ``publishedAt`` = last
    24h) and its real output field names (``jobTitle`` / ``companyName`` /
    ``jobUrl``). The previous version used ``keywords`` (wrong key) and read
    ``title``/``url`` (wrong fields), so it silently returned nothing.
    """
    if client_factory is None:  # imported lazily so tests need no apify-client
        from apify_client import ApifyClient

        client_factory = ApifyClient
    client = client_factory(apify_token)

    search_terms = keywords or DEFAULT_KEYWORDS
    postings: list[RawPosting] = []
    seen: set[tuple[str, str]] = set()
    for keyword in search_terms:
        run_input = {
            "keyword": [keyword],
            "location": "United States",
            "publishedAt": "r86400",  # last 24h — daily cadence
            "jobType": ["internship"],
            "experienceLevel": ["internship"],
            "maxItems": max_items,
            "saveOnlyUniqueItems": True,
        }
        run = client.actor(actor_id).call(run_input=run_input)
        dataset_id = _dataset_id(run)
        if not dataset_id:
            continue
        for item in client.dataset(dataset_id).iterate_items():
            if not isinstance(item, dict):
                continue
            company = str(item.get("companyName") or item.get("company") or "")
            title = str(item.get("jobTitle") or item.get("title") or "")
            link = str(item.get("jobUrl") or item.get("applyUrl") or item.get("url") or "")
            if not link:
                continue
            dedup_key = (company.lower().strip(), title.lower().strip())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            postings.append(
                RawPosting(
                    company=company,
                    title=title,
                    link=link,
                    location=str(item.get("location") or ""),
                    posted=str(item.get("postedAt") or item.get("listedAt") or ""),
                    source="linkedin",
                    description=str(item.get("description") or ""),
                    raw=item,
                )
            )
    return postings


def _dataset_id(run: Any) -> str:
    if hasattr(run, "default_dataset_id"):
        return str(run.default_dataset_id or "")
    if isinstance(run, dict):
        return str(run.get("defaultDatasetId") or "")
    return ""
