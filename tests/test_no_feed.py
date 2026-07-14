from __future__ import annotations

import json
from pathlib import Path

import no_feed


def test_no_feed_json_matches_roster() -> None:
    # no_feed_firms.json is a committed derived file — it must stay in sync with the
    # current roster + its feeds. If this fails, run:  python no_feed.py
    committed = json.loads(
        Path(no_feed.__file__).with_name("no_feed_firms.json").read_text(encoding="utf-8")
    )
    assert committed == no_feed.compute_no_feed(), "no_feed_firms.json is stale — run `python no_feed.py`"


def test_curated_daily_is_nonempty_subset_of_full() -> None:
    data = no_feed.compute_no_feed()
    full = {f["company"] for f in data["full"]}
    assert data["curated_daily"], "curated_daily is empty"
    assert all(f["company"] in full for f in data["curated_daily"])


def test_fed_firms_are_not_in_no_feed() -> None:
    # A firm with a keyless token must never appear on the no-feed list.
    from target_firms import all_source_tokens

    fed = {t["company"] for t in all_source_tokens()}
    no_feed_companies = {f["company"] for f in no_feed.compute_no_feed()["full"]}
    assert fed.isdisjoint(no_feed_companies)
