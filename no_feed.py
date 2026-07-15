"""No-feed firm list — drives the judge routine's Path B (web-search) discovery.

A roster firm has a keyless machine feed iff its canonical name appears in
`all_source_tokens()`. Everyone else has NO feed and can only be found by
web-searching their careers page. This module derives that no-feed set and
splits it into:

  - curated_daily: the elite off-feed finance/consulting/PE/VC/HF marquees worth
    a web-search EVERY day (the names most likely to open a role you want and
    most costly to miss).
  - full: every no-feed roster firm — swept once a week (Tuesday) so the long
    tail is covered without paying for it daily.

The derived list lives in the committed `no_feed_firms.json`; regenerate it with
`python no_feed.py` whenever the roster or its feeds change. A test asserts the
committed file matches the current roster so it can't silently go stale.
"""
from __future__ import annotations

import json
from pathlib import Path

from target_firms import TARGET_FIRMS, TIER_ORDER, all_source_tokens

OUT_PATH = Path(__file__).with_name("no_feed_firms.json")

# Elite, off-feed finance-family firms worth a DAILY web-search. Intersected with
# the live no-feed set below, so a name that later gains a feed drops out
# automatically. Big-tech / gov proprietary portals (Google, Apple, NASA, …) are
# intentionally excluded from the DAILY sweep (web-search is low-yield there) —
# they still ride the weekly full sweep.
CURATED_MARQUEES = {
    # MBB + elite consulting
    "McKinsey & Company", "Boston Consulting Group", "Bain & Company",
    # bulge + elite IB boutiques
    "Goldman Sachs", "JPMorgan", "Bank of America", "UBS", "Evercore",
    "Centerview Partners", "Lazard", "PJT Partners", "Perella Weinberg Partners",
    "Qatalyst Partners", "Rothschild & Co", "Greenhill & Co",
    # PE megafunds / apex
    "KKR", "Carlyle", "Bain Capital", "Silver Lake", "Vista Equity Partners",
    "Thoma Bravo", "Hellman & Friedman", "Leonard Green & Partners", "CVC",
    "Insight Partners",
    # hedge funds / quant
    "Citadel", "Citadel Securities", "Two Sigma", "D.E. Shaw", "Millennium",
    "SIG", "Balyasny", "Hudson River Trading", "Renaissance Technologies",
    # elite VC
    "Sequoia Capital", "Benchmark", "Founders Fund", "Accel", "Greylock",
    "Kleiner Perkins", "Lightspeed", "Index Ventures", "Thrive Capital",
}


def compute_no_feed() -> dict[str, list[dict[str, str]]]:
    fed = {t["company"] for t in all_source_tokens()}
    no_feed = [
        {"company": f["canonical"], "tier": f["tier"]}
        for f in TARGET_FIRMS
        if f["canonical"] not in fed
    ]
    no_feed.sort(key=lambda r: (TIER_ORDER.get(r["tier"], 99), r["company"]))
    curated = [r for r in no_feed if r["company"] in CURATED_MARQUEES]
    return {"curated_daily": curated, "full": no_feed}


def render() -> str:
    return json.dumps(compute_no_feed(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT_PATH.write_text(render(), encoding="utf-8")
    data = compute_no_feed()
    print(f"wrote {OUT_PATH.name}: {len(data['curated_daily'])} curated-daily, "
          f"{len(data['full'])} full no-feed firms")
