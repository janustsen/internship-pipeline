from __future__ import annotations

from typing import Any


# Seed roster from the approved design. The full production list is expected to
# be expanded from the /deep-research output without changing the matching API.
TARGET_FIRMS: list[dict[str, Any]] = [
    {
        "canonical": "JPMorgan",
        "tier": "T1",
        "aliases": [
            "JPMorgan",
            "JPMorgan Chase",
            "J.P. Morgan",
            "J.P. Morgan Chase",
            "JP Morgan",
            "JP Morgan Chase",
            "JPMorgan Chase & Co.",
        ],
        "sources": [{"platform": "greenhouse", "token": "jpmorgan"}],
    },
    {
        "canonical": "Morgan Stanley",
        "tier": "T1",
        "aliases": ["Morgan Stanley", "Morgan Stanley Group"],
        "sources": [],
    },
    {
        "canonical": "Goldman Sachs",
        "tier": "T1",
        "aliases": ["Goldman Sachs", "Goldman Sachs Group", "Goldman Sachs & Co."],
        "sources": [],
    },
    {
        "canonical": "McKinsey & Company",
        "tier": "T1",
        "aliases": ["McKinsey", "McKinsey & Company", "McKinsey and Company"],
        "sources": [],
    },
    {
        "canonical": "Boston Consulting Group",
        "tier": "T1",
        "aliases": ["BCG", "Boston Consulting Group"],
        "sources": [],
    },
    {
        "canonical": "Bain & Company",
        "tier": "T1",
        "aliases": ["Bain", "Bain & Company", "Bain and Company"],
        "sources": [],
    },
    {
        "canonical": "Blackstone",
        "tier": "T1",
        "aliases": ["Blackstone", "The Blackstone Group"],
        "sources": [],
    },
    {
        "canonical": "Citadel",
        "tier": "T1",
        "aliases": ["Citadel", "Citadel Securities"],
        "sources": [],
    },
    {
        "canonical": "Jane Street",
        "tier": "T1",
        "aliases": ["Jane Street", "Jane Street Capital"],
        "sources": [],
    },
    {
        "canonical": "Google",
        "tier": "T1",
        "aliases": ["Google", "Google LLC", "Alphabet", "Alphabet Inc."],
        "sources": [],
    },
    {
        "canonical": "Meta",
        "tier": "T1",
        "aliases": ["Meta", "Meta Platforms", "Facebook"],
        "sources": [],
    },
    {
        "canonical": "NASA",
        "tier": "T1",
        "aliases": ["NASA", "National Aeronautics and Space Administration"],
        "sources": [],
    },
    {
        "canonical": "Evercore",
        "tier": "T2",
        "aliases": ["Evercore", "Evercore Partners"],
        "sources": [],
    },
    {
        "canonical": "Lazard",
        "tier": "T2",
        "aliases": ["Lazard", "Lazard Freres"],
        "sources": [],
    },
    {
        "canonical": "Stripe",
        "tier": "T2",
        "aliases": ["Stripe", "Stripe Inc."],
        "sources": [],
    },
]


TIER_ORDER = {"T1": 0, "T2": 1}


def all_source_tokens() -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    for firm in TARGET_FIRMS:
        for source in firm.get("sources", []):
            platform = str(source.get("platform") or "").strip()
            token = str(source.get("token") or "").strip()
            if platform and token:
                tokens.append(
                    {
                        "platform": platform,
                        "token": token,
                        "company": firm["canonical"],
                        "tier": firm["tier"],
                    }
                )
    return tokens
