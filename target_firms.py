"""Cross-sector Tier-1 / Tier-2 prestige allowlist — the collector's firm gate.

Roster sourced from the 2026-07-10 /deep-research pass (investment banking, MBB +
strategy consulting, asset management — high-confidence, cited) combined with
domain coverage for PE / hedge funds / quant / VC / big tech / hot startups /
marquee corporates. ATS `sources` tokens marked "verified" were live-checked on
2026-07-10 via verify_tokens.py (HTTP 200 + real postings); firms without a token
are watched via the name-gated aggregator sources (LinkedIn / Adzuna / Serper /
Handshake) and by the discovery review queue.

Tiers: T1 = most prestigious / most selective; T2 = still excellent / target.
Public API is unchanged: TARGET_FIRMS (list of dicts) + all_source_tokens().
"""
from __future__ import annotations

from typing import Any

# Each row: (canonical, tier, [aliases], [(platform, token), ...])
# Aliases are matched exactly after normalization (lowercase, strip corp suffixes),
# so list the real variants that appear as a "company" string in job feeds.
_ROSTER: list[tuple[str, str, list[str], list[tuple[str, str]]]] = [
    # ── Investment banking — bulge brackets (T1) ──────────────────────────────
    ("Goldman Sachs", "T1", ["Goldman Sachs", "Goldman", "GS", "Goldman Sachs Group"], []),
    ("Morgan Stanley", "T1", ["Morgan Stanley", "Morgan Stanley Group"], []),
    ("JPMorgan", "T1", ["JPMorgan", "JPMorgan Chase", "J.P. Morgan", "J.P. Morgan Chase",
                        "JP Morgan", "JPMorgan Chase & Co", "JPMorgan Securities"], []),
    ("Bank of America", "T1", ["Bank of America", "BofA", "BofA Securities",
                               "Bank of America Merrill Lynch", "BAML"], []),
    ("Citi", "T1", ["Citi", "Citigroup", "Citibank", "Citi Group"], []),
    ("Barclays", "T1", ["Barclays", "Barclays Investment Bank", "Barclays Capital"], []),
    ("UBS", "T1", ["UBS", "UBS Group", "UBS Investment Bank"], []),
    ("Deutsche Bank", "T1", ["Deutsche Bank", "DB"], []),

    # ── Investment banking — elite boutiques (T1) ─────────────────────────────
    ("Centerview Partners", "T1", ["Centerview Partners", "Centerview"], []),
    ("Evercore", "T1", ["Evercore", "Evercore Partners"], []),
    ("Lazard", "T1", ["Lazard", "Lazard Freres"], []),
    ("Moelis & Company", "T1", ["Moelis & Company", "Moelis"], []),
    ("PJT Partners", "T1", ["PJT Partners", "PJT"], []),
    ("Perella Weinberg Partners", "T1", ["Perella Weinberg Partners", "Perella Weinberg", "PWP"], []),
    ("Qatalyst Partners", "T1", ["Qatalyst Partners", "Qatalyst"], []),
    ("Rothschild & Co", "T1", ["Rothschild & Co", "Rothschild", "Rothschild and Co"], []),
    ("Guggenheim Securities", "T1", ["Guggenheim Securities", "Guggenheim", "Guggenheim Partners"], []),
    ("Greenhill & Co", "T1", ["Greenhill & Co", "Greenhill"], []),

    # ── Investment banking — Tier 2 boutiques / upper-middle-market ────────────
    ("Jefferies", "T2", ["Jefferies", "Jefferies Group", "Jefferies Financial Group"], []),
    ("Houlihan Lokey", "T2", ["Houlihan Lokey", "HL"], []),
    ("LionTree", "T2", ["LionTree", "LionTree Advisors"], []),
    ("FT Partners", "T2", ["FT Partners", "Financial Technology Partners"], []),
    ("Allen & Company", "T2", ["Allen & Company", "Allen & Co"], []),
    ("Piper Sandler", "T2", ["Piper Sandler", "Piper Sandler Companies"], []),
    ("Baird", "T2", ["Baird", "Robert W. Baird", "Robert W Baird"], []),
    ("William Blair", "T2", ["William Blair", "William Blair & Company"], []),
    ("Lincoln International", "T2", ["Lincoln International"], []),
    ("Harris Williams", "T2", ["Harris Williams"], []),
    ("Raine Group", "T2", ["Raine Group", "The Raine Group"], []),
    ("Solomon Partners", "T2", ["Solomon Partners"], []),
    ("Wells Fargo", "T2", ["Wells Fargo", "Wells Fargo Securities"], []),
    ("RBC Capital Markets", "T2", ["RBC Capital Markets", "RBC", "Royal Bank of Canada"], []),
    ("Nomura", "T2", ["Nomura", "Nomura Holdings"], []),
    ("Mizuho", "T2", ["Mizuho", "Mizuho Financial Group", "Mizuho Securities"], []),
    ("Macquarie", "T2", ["Macquarie", "Macquarie Group", "Macquarie Capital"], []),
    ("BNP Paribas", "T2", ["BNP Paribas", "BNP"], []),
    ("HSBC", "T2", ["HSBC", "HSBC Holdings"], []),

    # ── Management / strategy consulting — MBB (T1) ────────────────────────────
    ("McKinsey & Company", "T1", ["McKinsey & Company", "McKinsey", "McKinsey and Company"], []),
    ("Boston Consulting Group", "T1", ["Boston Consulting Group", "BCG"], []),
    ("Bain & Company", "T1", ["Bain & Company", "Bain", "Bain and Company"], []),

    # ── Consulting — Tier 2 strategy set ──────────────────────────────────────
    ("Oliver Wyman", "T2", ["Oliver Wyman"], []),
    ("L.E.K. Consulting", "T2", ["L.E.K. Consulting", "LEK", "L.E.K."], []),
    ("Kearney", "T2", ["Kearney", "A.T. Kearney", "AT Kearney"], []),
    ("Roland Berger", "T2", ["Roland Berger"], []),
    ("Strategy&", "T2", ["Strategy&", "Strategy& (PwC)", "Booz & Company"], []),
    ("EY-Parthenon", "T2", ["EY-Parthenon", "EY Parthenon", "Parthenon-EY", "Parthenon"], []),
    ("Accenture", "T2", ["Accenture", "Accenture Strategy", "Accenture Song"], []),
    ("Deloitte", "T2", ["Deloitte", "Deloitte Consulting", "Monitor Deloitte"], []),
    ("PwC", "T2", ["PwC", "PricewaterhouseCoopers"], []),
    ("EY", "T2", ["EY", "Ernst & Young"], []),
    ("KPMG", "T2", ["KPMG"], []),
    ("Booz Allen Hamilton", "T2", ["Booz Allen Hamilton", "Booz Allen"], []),
    ("ZS Associates", "T2", ["ZS Associates", "ZS"], []),
    ("Analysis Group", "T2", ["Analysis Group"], []),
    ("Cornerstone Research", "T2", ["Cornerstone Research"], []),
    ("AlixPartners", "T2", ["AlixPartners"], [("greenhouse", "alixpartners")]),  # verified

    # ── Private equity / growth equity (T1) ───────────────────────────────────
    ("Blackstone", "T1", ["Blackstone", "The Blackstone Group", "Blackstone Group"], []),
    ("KKR", "T1", ["KKR", "Kohlberg Kravis Roberts"], []),
    ("Apollo", "T1", ["Apollo", "Apollo Global Management"], []),
    ("Carlyle", "T1", ["Carlyle", "The Carlyle Group", "Carlyle Group"], []),
    ("Bain Capital", "T1", ["Bain Capital"], []),
    ("TPG", "T1", ["TPG", "TPG Capital", "Texas Pacific Group"], [("greenhouse", "tpgcareers")]),  # verified
    ("Warburg Pincus", "T1", ["Warburg Pincus"], [("greenhouse", "warburgpincusllc")]),  # verified
    ("Silver Lake", "T1", ["Silver Lake", "Silver Lake Partners"], []),
    ("Vista Equity Partners", "T1", ["Vista Equity Partners", "Vista Equity"], []),
    ("Thoma Bravo", "T1", ["Thoma Bravo"], []),
    ("Advent International", "T1", ["Advent International", "Advent"], []),
    ("General Atlantic", "T1", ["General Atlantic"], [("greenhouse", "generalatlantic")]),  # verified
    ("Hellman & Friedman", "T1", ["Hellman & Friedman", "H&F"], []),
    ("Leonard Green & Partners", "T1", ["Leonard Green & Partners", "Leonard Green"], []),
    ("EQT", "T1", ["EQT", "EQT Partners"], []),
    ("CVC", "T1", ["CVC", "CVC Capital Partners"], []),
    ("Brookfield", "T1", ["Brookfield", "Brookfield Asset Management"], []),
    ("Insight Partners", "T1", ["Insight Partners"], []),
    ("Summit Partners", "T1", ["Summit Partners"], [("greenhouse", "summitpartnerslp")]),  # verified
    ("TA Associates", "T2", ["TA Associates"], []),

    # ── Hedge funds / quant / market makers (T1) ──────────────────────────────
    ("Citadel", "T1", ["Citadel", "Citadel LLC"], []),
    ("Citadel Securities", "T1", ["Citadel Securities"], []),
    ("Jane Street", "T1", ["Jane Street", "Jane Street Capital"], [("greenhouse", "janestreet")]),  # verified
    ("Two Sigma", "T1", ["Two Sigma", "Two Sigma Investments"], []),
    ("D.E. Shaw", "T1", ["D.E. Shaw", "DE Shaw", "The D. E. Shaw Group", "D. E. Shaw"], []),
    ("Millennium", "T1", ["Millennium", "Millennium Management"], []),
    ("Point72", "T1", ["Point72", "Point72 Asset Management"], [("greenhouse", "point72")]),  # verified
    ("Hudson River Trading", "T1", ["Hudson River Trading", "HRT"], []),
    ("Jump Trading", "T1", ["Jump Trading", "Jump"], []),
    ("DRW", "T1", ["DRW", "DRW Trading"], [("greenhouse", "drweng")]),  # verified
    ("Optiver", "T1", ["Optiver"], [("greenhouse", "optiverus")]),  # verified
    ("IMC Trading", "T1", ["IMC Trading", "IMC"], [("greenhouse", "imc")]),  # verified
    ("SIG", "T1", ["SIG", "Susquehanna", "Susquehanna International Group"], []),
    ("Akuna Capital", "T1", ["Akuna Capital", "Akuna"], [("greenhouse", "akunacapital")]),  # verified
    ("Virtu Financial", "T1", ["Virtu Financial", "Virtu"], [("greenhouse", "virtu")]),  # verified
    ("Bridgewater Associates", "T1", ["Bridgewater Associates", "Bridgewater"],
        [("greenhouse", "bridgewater89")]),  # verified
    ("Renaissance Technologies", "T1", ["Renaissance Technologies", "RenTec"], []),
    ("AQR", "T1", ["AQR", "AQR Capital Management"], []),
    ("Balyasny", "T1", ["Balyasny", "Balyasny Asset Management", "BAM"], []),
    ("ExodusPoint", "T2", ["ExodusPoint", "ExodusPoint Capital"], []),
    ("Wellington Management", "T2", ["Wellington Management", "Wellington"], []),

    # ── Asset & wealth management (BlackRock T1; rest T2) ──────────────────────
    ("BlackRock", "T1", ["BlackRock"], []),
    ("Vanguard", "T2", ["Vanguard", "The Vanguard Group"], []),
    ("Fidelity", "T2", ["Fidelity", "Fidelity Investments"], []),
    ("State Street", "T2", ["State Street", "State Street Global Advisors", "SSGA"], []),
    ("PIMCO", "T2", ["PIMCO"], []),
    ("T. Rowe Price", "T2", ["T. Rowe Price", "T Rowe Price"], []),
    ("Capital Group", "T2", ["Capital Group"], []),
    ("Invesco", "T2", ["Invesco"], []),

    # ── Big tech (T1) ─────────────────────────────────────────────────────────
    ("Google", "T1", ["Google", "Google LLC", "Alphabet", "Alphabet Inc"], []),
    ("Apple", "T1", ["Apple", "Apple Inc"], []),
    ("Meta", "T1", ["Meta", "Meta Platforms", "Facebook"], []),
    ("Microsoft", "T1", ["Microsoft", "Microsoft Corporation"], []),
    ("Amazon", "T1", ["Amazon", "Amazon.com", "AWS", "Amazon Web Services"], []),
    ("Nvidia", "T1", ["Nvidia", "NVIDIA Corporation"], []),

    # ── Strong tech (T2) ──────────────────────────────────────────────────────
    ("Netflix", "T2", ["Netflix"], []),
    ("Salesforce", "T2", ["Salesforce"], []),
    ("Adobe", "T2", ["Adobe"], []),
    ("Airbnb", "T2", ["Airbnb"], []),
    ("Uber", "T2", ["Uber", "Uber Technologies"], []),
    ("Palantir", "T2", ["Palantir", "Palantir Technologies"], []),
    ("Snowflake", "T2", ["Snowflake"], []),
    ("Tesla", "T2", ["Tesla", "Tesla Motors"], []),
    ("LinkedIn", "T2", ["LinkedIn"], []),

    # ── Hot startups / scale-ups ──────────────────────────────────────────────
    ("OpenAI", "T1", ["OpenAI"], [("ashby", "openai")]),  # verified
    ("Anthropic", "T1", ["Anthropic"], [("greenhouse", "anthropic")]),  # verified
    ("Stripe", "T1", ["Stripe", "Stripe Inc"], [("greenhouse", "stripe")]),  # verified
    ("Databricks", "T1", ["Databricks"], []),
    ("Anduril", "T1", ["Anduril", "Anduril Industries"], []),
    ("SpaceX", "T1", ["SpaceX", "Space Exploration Technologies"], []),
    ("Scale AI", "T1", ["Scale AI", "Scale"], []),
    ("Figma", "T1", ["Figma"], []),
    ("xAI", "T1", ["xAI"], []),
    ("Ramp", "T2", ["Ramp"], [("ashby", "ramp")]),  # verified
    ("Plaid", "T2", ["Plaid"], [("ashby", "plaid")]),  # verified
    ("Brex", "T2", ["Brex"], [("greenhouse", "brex")]),  # verified
    ("Affirm", "T2", ["Affirm"], [("greenhouse", "affirm")]),  # verified
    ("Coinbase", "T2", ["Coinbase"], [("greenhouse", "coinbase")]),  # verified
    ("Robinhood", "T2", ["Robinhood"], [("greenhouse", "robinhood")]),  # verified
    ("Rippling", "T2", ["Rippling"], []),
    ("Notion", "T2", ["Notion"], []),
    ("Perplexity", "T2", ["Perplexity", "Perplexity AI"], []),
    ("Mistral AI", "T2", ["Mistral AI", "Mistral"], []),
    ("Cohere", "T2", ["Cohere"], []),
    ("Mercury", "T2", ["Mercury"], []),
    ("Deel", "T2", ["Deel"], []),
    ("DoorDash", "T2", ["DoorDash"], []),
    ("Instacart", "T2", ["Instacart", "Maplebear"], []),

    # ── VC (T1) ───────────────────────────────────────────────────────────────
    ("Sequoia Capital", "T1", ["Sequoia Capital", "Sequoia"], []),
    ("Andreessen Horowitz", "T1", ["Andreessen Horowitz", "a16z"], [("greenhouse", "a16z")]),  # verified
    ("Founders Fund", "T1", ["Founders Fund"], []),
    ("Benchmark", "T1", ["Benchmark", "Benchmark Capital"], []),
    ("Accel", "T1", ["Accel", "Accel Partners"], []),
    ("Greylock", "T1", ["Greylock", "Greylock Partners"], []),
    ("Kleiner Perkins", "T1", ["Kleiner Perkins", "KPCB"], []),
    ("General Catalyst", "T1", ["General Catalyst"], [("greenhouse", "generalcatalyst")]),  # verified
    ("Bessemer Venture Partners", "T1", ["Bessemer Venture Partners", "Bessemer", "BVP"],
        [("greenhouse", "bvpanalyst")]),  # verified
    ("Lightspeed", "T1", ["Lightspeed", "Lightspeed Venture Partners"], []),
    ("Thrive Capital", "T1", ["Thrive Capital", "Thrive"], []),
    ("Index Ventures", "T1", ["Index Ventures"], []),

    # ── Marquee corporates & institutions ─────────────────────────────────────
    ("The Walt Disney Company", "T2", ["The Walt Disney Company", "Walt Disney", "Disney"], []),
    ("Nike", "T2", ["Nike", "Nike Inc"], []),
    ("Procter & Gamble", "T2", ["Procter & Gamble", "P&G"], []),
    ("PepsiCo", "T2", ["PepsiCo", "Pepsi"], []),
    ("The Coca-Cola Company", "T2", ["The Coca-Cola Company", "Coca-Cola", "Coca Cola"], []),
    ("Visa", "T2", ["Visa", "Visa Inc"], []),
    ("Mastercard", "T2", ["Mastercard"], []),
    ("American Express", "T2", ["American Express", "Amex"], []),
    ("Boeing", "T2", ["Boeing", "The Boeing Company"], []),
    ("Lockheed Martin", "T2", ["Lockheed Martin"], []),
    ("NASA", "T1", ["NASA", "National Aeronautics and Space Administration",
                    "NASA JPL", "Jet Propulsion Laboratory"], []),
    ("Federal Reserve", "T2", ["Federal Reserve", "Federal Reserve Bank", "The Fed"], []),
    ("World Bank", "T2", ["World Bank", "The World Bank"], []),
    ("International Monetary Fund", "T2", ["International Monetary Fund", "IMF"], []),
]


TARGET_FIRMS: list[dict[str, Any]] = [
    {
        "canonical": canonical,
        "tier": tier,
        "aliases": aliases,
        "sources": [{"platform": platform, "token": token} for platform, token in sources],
    }
    for canonical, tier, aliases, sources in _ROSTER
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
