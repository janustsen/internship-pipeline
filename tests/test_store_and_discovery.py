from __future__ import annotations

from models import Candidate
from sources.ats import discover_tokens
from store import InternshipStore


def test_discovery_writes_pending_without_activating_or_scraping(tmp_path) -> None:
    store = InternshipStore(tmp_path / "seen.db")
    try:
        count = discover_tokens(
            [
                {"platform": "greenhouse", "token": "new-bank", "company": "JPMorgan"},
                {"platform": "lever", "token": "new-consulting", "company": "Morgan Stanley"},
            ],
            store,
        )

        assert count == 2
        assert len(store.list_pending_tokens()) == 2
        assert store.active_tokens() == []
    finally:
        store.close()


def test_lifetime_dedup_exact_url_then_semantic(tmp_path) -> None:
    store = InternshipStore(tmp_path / "seen.db")
    first = Candidate("T1", "business", "JPMorgan", "2027 Summer Analyst Program", "NY", "https://x/1", "adzuna")
    exact = Candidate("T1", "business", "JPMorgan", "2027 Summer Analyst Program", "NY", "https://x/1", "adzuna")
    semantic = Candidate("T1", "business", "JPMorgan Chase", "2027 Summer Analyst Program", "NY", "https://x/2", "adzuna")
    try:
        result = store.dedupe([first], dry_run=False)
        assert result.new == [first]

        result = store.dedupe([exact, semantic], dry_run=True)
        assert result.new == []
        assert result.duplicates == [exact, semantic]
    finally:
        store.close()
