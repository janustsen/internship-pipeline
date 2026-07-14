"""Cross-sector Tier-1 / Tier-2 / Tier-3 prestige allowlist — the collector's firm gate.

Roster sourced from the 2026-07-10 /deep-research pass (investment banking, MBB +
strategy consulting, asset management — high-confidence, cited) combined with
domain coverage for PE / hedge funds / quant / VC / big tech / hot startups /
marquee corporates. ATS `sources` tokens marked "verified" were live-checked on
2026-07-10 via verify_tokens.py (HTTP 200 + real postings); firms without a token
are watched via the name-gated aggregator sources (LinkedIn / Adzuna / Serper /
Handshake) and by the discovery review queue.

Tiers: T1 = most prestigious / most selective; T2 = still excellent / target;
T3 = solid in-domain prestige (smaller / specialist boutiques). See docs/roster-tiers.md.
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
    ("LionTree", "T2", ["LionTree", "LionTree Advisors"], [("greenhouse", "liontree")]),  # verified 2026-07-11
    ("FT Partners", "T2", ["FT Partners", "Financial Technology Partners"], []),
    ("Allen & Company", "T2", ["Allen & Company", "Allen & Co"], []),
    ("Piper Sandler", "T2", ["Piper Sandler", "Piper Sandler Companies"], []),
    ("Baird", "T2", ["Baird", "Robert W. Baird", "Robert W Baird"], []),
    ("William Blair", "T2", ["William Blair", "William Blair & Company"], [("greenhouse", "williamblair")]),  # verified 2026-07-11
    ("Lincoln International", "T2", ["Lincoln International"], [("greenhouse", "lincolninternational")]),  # verified 2026-07-11
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
    ("EQT", "T1", ["EQT", "EQT Partners"], [("greenhouse", "eqtpartners")]),  # verified 2026-07-11
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
    ("Jump Trading", "T1", ["Jump Trading", "Jump"], [("greenhouse", "jumptrading")]),  # verified 2026-07-11
    ("DRW", "T1", ["DRW", "DRW Trading"], [("greenhouse", "drweng")]),  # verified
    ("Optiver", "T1", ["Optiver"], [("greenhouse", "optiverus")]),  # verified
    ("IMC Trading", "T1", ["IMC Trading", "IMC"], [("greenhouse", "imc")]),  # verified
    ("SIG", "T1", ["SIG", "Susquehanna", "Susquehanna International Group"], []),
    ("Akuna Capital", "T1", ["Akuna Capital", "Akuna"], [("greenhouse", "akunacapital")]),  # verified
    ("Virtu Financial", "T1", ["Virtu Financial", "Virtu"], [("greenhouse", "virtu")]),  # verified
    ("Bridgewater Associates", "T1", ["Bridgewater Associates", "Bridgewater"],
        [("greenhouse", "bridgewater89")]),  # verified
    ("Renaissance Technologies", "T1", ["Renaissance Technologies", "RenTec"], []),
    ("AQR", "T1", ["AQR", "AQR Capital Management"], [("greenhouse", "aqr")]),  # verified 2026-07-11
    ("Balyasny", "T1", ["Balyasny", "Balyasny Asset Management", "BAM"], []),
    ("ExodusPoint", "T2", ["ExodusPoint", "ExodusPoint Capital"], [("greenhouse", "exoduspoint")]),  # verified 2026-07-11
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
    ("Airbnb", "T2", ["Airbnb"], [("greenhouse", "airbnb")]),  # verified 2026-07-11
    ("Uber", "T2", ["Uber", "Uber Technologies"], []),
    ("Palantir", "T2", ["Palantir", "Palantir Technologies"], [("lever", "palantir")]),  # verified 2026-07-11
    ("Snowflake", "T2", ["Snowflake"], [("ashby", "snowflake")]),  # verified 2026-07-11
    ("Tesla", "T2", ["Tesla", "Tesla Motors"], []),
    ("LinkedIn", "T2", ["LinkedIn"], []),

    # ── Hot startups / scale-ups ──────────────────────────────────────────────
    ("OpenAI", "T1", ["OpenAI"], [("ashby", "openai")]),  # verified
    ("Anthropic", "T1", ["Anthropic"], [("greenhouse", "anthropic")]),  # verified
    ("Stripe", "T1", ["Stripe", "Stripe Inc"], [("greenhouse", "stripe")]),  # verified
    ("Databricks", "T1", ["Databricks"], [("greenhouse", "databricks")]),  # verified 2026-07-11
    ("Anduril", "T1", ["Anduril", "Anduril Industries"], [("greenhouse", "andurilindustries")]),  # verified 2026-07-11
    ("SpaceX", "T1", ["SpaceX", "Space Exploration Technologies"], [("greenhouse", "spacex")]),  # verified 2026-07-11
    ("Scale AI", "T1", ["Scale AI", "Scale"], [("greenhouse", "scaleai")]),  # verified 2026-07-11
    ("Figma", "T1", ["Figma"], [("greenhouse", "figma")]),  # verified 2026-07-11
    ("xAI", "T1", ["xAI"], [("greenhouse", "xai")]),  # verified 2026-07-11
    ("Ramp", "T2", ["Ramp"], [("ashby", "ramp")]),  # verified
    ("Plaid", "T2", ["Plaid"], [("ashby", "plaid")]),  # verified
    ("Brex", "T2", ["Brex"], [("greenhouse", "brex")]),  # verified
    ("Affirm", "T2", ["Affirm"], [("greenhouse", "affirm")]),  # verified
    ("Coinbase", "T2", ["Coinbase"], [("greenhouse", "coinbase")]),  # verified
    ("Robinhood", "T2", ["Robinhood"], [("greenhouse", "robinhood")]),  # verified
    ("Rippling", "T2", ["Rippling"], []),
    ("Notion", "T2", ["Notion"], [("ashby", "notion")]),  # verified 2026-07-11
    ("Perplexity", "T2", ["Perplexity", "Perplexity AI"], [("ashby", "perplexity")]),  # verified 2026-07-11
    ("Mistral AI", "T2", ["Mistral AI", "Mistral"], []),
    ("Cohere", "T2", ["Cohere"], [("ashby", "cohere")]),  # verified 2026-07-11
    ("Mercury", "T2", ["Mercury"], [("greenhouse", "mercury")]),  # verified 2026-07-11
    ("Deel", "T2", ["Deel"], []),
    ("DoorDash", "T2", ["DoorDash"], []),
    ("Instacart", "T2", ["Instacart", "Maplebear"], [("greenhouse", "instacart")]),  # verified 2026-07-11

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

    # ── Roster expansion 2026-07-14 — feeds discovered + live-verified via
    #    discover_ats.py / discover_workday.py (see roster_ats_discovered.json). ──
    # Consulting
    ("Brattle Group", "T3", ["Brattle Group", "The Brattle Group", "Brattle"], [("greenhouse", "thebrattlegroup")]),
    ("Charles River Associates", "T3", ["Charles River Associates", "CRA", "CRA International"], [("greenhouse", "charlesriverassociates")]),
    ("ClearView Healthcare Partners", "T3", ["ClearView Healthcare Partners", "ClearView"], [("greenhouse", "clearviewhealthcarepartners")]),
    ("Huron Consulting Group", "T3", ["Huron Consulting Group", "Huron", "Huron Consulting"], [("workday", "https://huron.wd1.myworkdayjobs.com/wday/cxs/huron/huroncareers/jobs")]),
    ("Putnam Associates", "T3", ["Putnam Associates", "Putnam"], [("greenhouse", "putnamassociatesllc")]),
    ("ghSMART", "T3", ["ghSMART", "GH SMART"], [("lever", "ghsmartjobs")]),
    # Investment banking
    ("Ducera Partners", "T3", ["Ducera Partners", "Ducera"], [("greenhouse", "ducerapartners")]),
    ("ING", "T2", ["ING", "ING Group", "ING Bank"], [("workday", "https://ing.wd3.myworkdayjobs.com/wday/cxs/ing/ICSGBLCOR/jobs")]),
    # Private equity
    ("Adams Street Partners", "T2", ["Adams Street Partners", "Adams Street"], [("greenhouse", "adamsstreetpartners")]),
    ("Alpine Investors", "T3", ["Alpine Investors", "Alpine"], [("greenhouse", "alpineinvestors")]),
    ("Audax Group", "T2", ["Audax Group", "Audax", "Audax Private Equity"], [("greenhouse", "audaxgroup")]),
    ("DigitalBridge", "T3", ["DigitalBridge", "Digital Bridge"], [("greenhouse", "digitalbridge")]),
    ("H.I.G. Capital", "T3", ["H.I.G. Capital", "HIG Capital", "H.I.G."], [("workday", "https://higcapital.wd5.myworkdayjobs.com/wday/cxs/higcapital/LinkedIn/jobs")]),
    ("Level Equity", "T3", ["Level Equity"], [("greenhouse", "levelequity")]),
    ("Oaktree Capital", "T2", ["Oaktree Capital", "Oaktree", "Oaktree Capital Management"], [("workday", "https://oaktree.wd1.myworkdayjobs.com/wday/cxs/oaktree/oaktree/jobs")]),
    ("Providence Equity Partners", "T2", ["Providence Equity Partners", "Providence Equity"], [("workday", "https://provequity.wd5.myworkdayjobs.com/wday/cxs/provequity/PEP_External_Career_Site/jobs")]),
    ("The Riverside Company", "T3", ["The Riverside Company", "Riverside Company", "Riverside"], [("greenhouse", "theriversidecompany")]),
    # Venture capital
    ("5AM Ventures", "T3", ["5AM Ventures", "5AM"], [("lever", "5amventures")]),
    ("8VC", "T2", ["8VC"], [("ashby", "8vc")]),
    ("Bain Capital Ventures", "T2", ["Bain Capital Ventures", "BCV"], [("greenhouse", "baincapitalventures")]),
    ("Breakthrough Energy Ventures", "T3", ["Breakthrough Energy Ventures", "Breakthrough Energy", "BEV"], [("greenhouse", "breakthroughenergy")]),
    ("First Round Capital", "T2", ["First Round Capital", "First Round"], [("ashby", "firstround")]),
    ("Flagship Pioneering", "T2", ["Flagship Pioneering", "Flagship"], [("greenhouse", "flagshippioneeringinc")]),
    ("Georgian", "T2", ["Georgian", "Georgian Partners"], [("ashby", "georgian")]),
    ("Polychain Capital", "T3", ["Polychain Capital", "Polychain"], [("greenhouse", "polychaincapital")]),
    ("Samsung NEXT", "T3", ["Samsung NEXT"], [("greenhouse", "samsungnext")]),
    # Corporate strategy / BizOps
    ("3M", "T2", ["3M", "3M Company"], [("workday", "https://3m.wd1.myworkdayjobs.com/wday/cxs/3m/Search/jobs")]),
    ("Amgen", "T2", ["Amgen"], [("workday", "https://amgen.wd1.myworkdayjobs.com/wday/cxs/amgen/Careers/jobs")]),
    ("Block", "T2", ["Block", "Block Inc", "Square"], [("greenhouse", "block")]),
    ("Comcast", "T2", ["Comcast", "NBCUniversal"], [("workday", "https://comcast.wd5.myworkdayjobs.com/wday/cxs/comcast/Comcast_Careers/jobs")]),
    ("Datadog", "T2", ["Datadog"], [("greenhouse", "datadog")]),
    ("Elevance Health", "T2", ["Elevance Health", "Elevance", "Anthem"], [("workday", "https://elevancehealth.wd1.myworkdayjobs.com/wday/cxs/elevancehealth/ANT/jobs")]),
    ("Gilead Sciences", "T2", ["Gilead Sciences", "Gilead"], [("workday", "https://gilead.wd1.myworkdayjobs.com/wday/cxs/gilead/gileadcareers/jobs")]),
    ("Intel", "T1", ["Intel", "Intel Corporation"], [("workday", "https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/External/jobs")]),
    ("Lyft", "T2", ["Lyft"], [("greenhouse", "lyft")]),
    ("Medtronic", "T2", ["Medtronic"], [("workday", "https://medtronic.wd1.myworkdayjobs.com/wday/cxs/medtronic/MedtronicCareers/jobs")]),
    ("Spotify", "T2", ["Spotify"], [("lever", "spotify")]),
    ("T-Mobile", "T2", ["T-Mobile", "T Mobile", "TMobile"], [("workday", "https://tmobile.wd1.myworkdayjobs.com/wday/cxs/tmobile/External/jobs")]),
    ("Target", "T2", ["Target", "Target Corporation"], [("workday", "https://target.wd5.myworkdayjobs.com/wday/cxs/target/targetcareers/jobs")]),
    ("Vercel", "T2", ["Vercel"], [("greenhouse", "vercel")]),

    # ── Roster expansion pass 2 (2026-07-14) — discover_ats2.py deep sweep ──
    # Investment banking
    ("BMO Capital Markets", "T2", ["BMO Capital Markets", "BMO", "Bank of Montreal"], [("workday", "https://bmo.wd3.myworkdayjobs.com/wday/cxs/bmo/External/jobs")]),
    # Private equity
    ("GI Partners", "T3", ["GI Partners"], [("smartrecruiters", "GiPartners")]),
    # Venture capital
    ("Madrona Venture Group", "T3", ["Madrona Venture Group", "Madrona"], [("smartrecruiters", "MadronaVentureGroup")]),
    ("Pantera Capital", "T3", ["Pantera Capital", "Pantera"], [("greenhouse", "panteracapitalcareers")]),
    ("Y Combinator", "T2", ["Y Combinator", "YC"], [("ashby", "ycombinator")]),
    ("a16z Crypto", "T2", ["a16z Crypto", "Andreessen Horowitz Crypto"], [("ashby", "a16z-crypto")]),
    # Corporate strategy / BizOps
    ("Dropbox", "T2", ["Dropbox"], [("greenhouse", "dropbox")]),
    ("Micron Technology", "T1", ["Micron Technology", "Micron"], [("workday", "https://micron.wd1.myworkdayjobs.com/wday/cxs/micron/External/jobs")]),
    ("Okta", "T2", ["Okta"], [("greenhouse", "okta")]),
    ("Roblox", "T2", ["Roblox"], [("greenhouse", "roblox")]),
    ("Roku", "T2", ["Roku"], [("greenhouse", "roku")]),
    ("ServiceNow", "T1", ["ServiceNow"], [("smartrecruiters", "Servicenow")]),
    ("Twilio", "T2", ["Twilio"], [("greenhouse", "twilio")]),
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


TIER_ORDER = {"T1": 0, "T2": 1, "T3": 2}


import json as _json
from pathlib import Path as _Path

# Enrichment feeds discovered 2026-07-11 (Workday/ATS endpoints for the marquee
# roster firms that ship no inline source). Kept in a data file so the roster
# literal above stays clean and the feeds are easy to re-verify / extend.
_FEEDS_PATH = _Path(__file__).with_name("firm_feeds.json")
# Only these platforms are fetchable keyless by the collector; "careers" URLs in
# the feeds file are reference for the routine's WebSearch discovery net.
_KEYLESS_PLATFORMS = {"greenhouse", "lever", "ashby", "smartrecruiters", "workable", "workday"}


def _load_firm_feeds() -> dict[str, list[dict[str, str]]]:
    try:
        data = _json.loads(_FEEDS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def all_source_tokens() -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    tier_by_canonical = {f["canonical"]: f["tier"] for f in TARGET_FIRMS}

    def _add(platform: str, token: str, company: str, tier: str) -> None:
        platform, token = platform.strip().lower(), token.strip()
        if platform and token and (platform, token) not in seen:
            seen.add((platform, token))
            tokens.append({"platform": platform, "token": token, "company": company, "tier": tier})

    # 1. Inline roster sources.
    for firm in TARGET_FIRMS:
        for source in firm.get("sources", []):
            _add(str(source.get("platform") or ""), str(source.get("token") or ""),
                 firm["canonical"], firm["tier"])

    # 2. Enrichment feeds — only for roster firms (allowlist integrity), keyless only.
    for canonical, feeds in _load_firm_feeds().items():
        tier = tier_by_canonical.get(canonical)
        if not tier or not isinstance(feeds, list):
            continue
        for source in feeds:
            if not isinstance(source, dict):
                continue
            if str(source.get("platform") or "").strip().lower() in _KEYLESS_PLATFORMS:
                _add(str(source.get("platform") or ""), str(source.get("token") or ""), canonical, tier)
    return tokens
