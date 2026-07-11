from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawPosting:
    company: str
    title: str
    link: str
    source: str
    location: str = ""
    posted: str = ""
    category: str = "business"
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    tier_hint: str
    category: str
    company: str
    title: str
    location: str
    link: str
    source: str
    posted: str = ""

    def to_json(self) -> dict[str, str]:
        return {
            "tier_hint": self.tier_hint,
            "category": self.category,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "link": self.link,
            "source": self.source,
            "posted": self.posted,
        }


REQUIRED_CANDIDATE_FIELDS = tuple(Candidate.__dataclass_fields__.keys())


def raw_posting_from_mapping(item: dict[str, Any], source: str | None = None) -> RawPosting:
    actual_source = str(item.get("source") or source or "").strip()
    return RawPosting(
        company=str(item.get("company") or item.get("company_name") or "").strip(),
        title=str(item.get("title") or item.get("name") or "").strip(),
        link=str(item.get("link") or item.get("url") or item.get("absolute_url") or "").strip(),
        source=actual_source,
        location=str(item.get("location") or "").strip(),
        posted=str(item.get("posted") or item.get("created_at") or item.get("date") or "").strip(),
        category=str(item.get("category") or "business").strip() or "business",
        description=str(item.get("description") or item.get("content") or "").strip(),
        raw=dict(item),
    )
