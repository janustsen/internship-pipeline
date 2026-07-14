"""One-shot roster consolidation + ATS-endpoint discovery.

Reads the ~5 Perplexity research passes (PE, VC, consulting, IB, strategy/BizOps)
into a single deduped firm roster, then LIVE-PROBES each firm's keyless ATS feed
so we know exactly which firms Path A (deterministic ATS poll) can watch and which
must fall to Path B (LLM web-search discovery).

Two moves per firm:
  1. Validate any keyless endpoint the research already found (greenhouse / lever /
     ashby / smartrecruiters / workday), by actually fetching it.
  2. For firms with no confirmed keyless feed, GUESS slug variants and probe
     greenhouse -> lever -> ashby. A hit = HTTP 200 + >=1 real posting.

Guessed hits are marked `needs_review` (a slug can collide with an unrelated
board); the live pipeline re-gates every posting by firm name anyway, so a wrong
board is caught downstream. Known-proprietary stacks (Taleo / iCIMS / Oleeo /
Avature / Eightfold / Workday-with-unknown-site / email) are NOT guessed — they
route to Path B by design.

Outputs (repo root, uncommitted):
  - roster_candidates.json   the full deduped name list (deliverable: "the list")
  - roster_ats_discovered.json   per-firm probe result + confirmed feeds
Run:  python3 discover_ats.py            (probe everything)
      python3 discover_ats.py --no-probe (just (re)build the name list)
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_client import RetryingHttpClient  # noqa: E402
from sources import ats, workday  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# ROSTER — every firm from the 5 research files, as (name, domain, tier).
# domains: consulting | ib | pe | vc | hf | corp   (hf folded in where present)
# tiers as given by each file (T1/T2/T3); corp giants keep their file's tier.
# ─────────────────────────────────────────────────────────────────────────────
def _rows(domain: str, tier: str, names: str) -> list[tuple[str, str, str]]:
    return [(n.strip(), domain, tier) for n in names.split("|") if n.strip()]


ROSTER: list[tuple[str, str, str]] = []

# ── Consulting ───────────────────────────────────────────────────────────────
ROSTER += _rows("consulting", "T1", "McKinsey & Company|Boston Consulting Group|Bain & Company")
ROSTER += _rows("consulting", "T2",
    "Oliver Wyman|Strategy&|EY-Parthenon|Monitor Deloitte|KPMG Strategy|Kearney|"
    "L.E.K. Consulting|Roland Berger|Accenture Strategy|Booz Allen Hamilton|Arthur D. Little")
ROSTER += _rows("consulting", "T3",
    "Simon-Kucher|ZS Associates|OC&C Strategy Consultants|Analysis Group|Cornerstone Research|"
    "Charles River Associates|Brattle Group|Bates White|Alvarez & Marsal|AlixPartners|FTI Consulting|"
    "Huron Consulting Group|ghSMART|Stax|Putnam Associates|ClearView Healthcare Partners|"
    "Health Advances|Altman Solon|Avasant|NERA Economic Consulting|Compass Lexecon|"
    "Edgeworth Economics|Economists Incorporated|Frontier Economics|Oxera|Copenhagen Economics|"
    "RBB Economics|E.CA Economics|Oslo Economics|Vivaldi Group|The Value Engineers|Horvath|"
    "Nova Reperta|Marakon|Kaiser Associates|Trinity Life Sciences")

# ── Investment banking / M&A ─────────────────────────────────────────────────
ROSTER += _rows("ib", "T1",
    "Goldman Sachs|Morgan Stanley|J.P. Morgan|Evercore|Centerview Partners|Lazard|"
    "Qatalyst Partners|Allen & Company")
ROSTER += _rows("ib", "T2",
    "PJT Partners|Moelis & Company|Perella Weinberg Partners|Rothschild & Co|Guggenheim Securities|"
    "Houlihan Lokey|Jefferies|Bank of America|Citi|Barclays|UBS|Deutsche Bank|RBC Capital Markets|"
    "HSBC|BNP Paribas|Credit Agricole CIB|Societe Generale|Nomura|Mizuho|Macquarie|"
    "Standard Chartered|TD Securities|Santander|SMBC Nikko|Daiwa|BMO Capital Markets|Scotiabank|ING")
ROSTER += _rows("ib", "T3",
    "William Blair|Baird|Harris Williams|Piper Sandler|Raymond James|Stifel|TD Cowen|"
    "Lincoln International|LionTree|FT Partners|Union Square Advisors|Solomon Partners|Ducera Partners|"
    "Foros|DBO Partners|Leerink Partners|Wells Fargo Securities|Canaccord Genuity|Stephens|"
    "Cantor Fitzgerald|Truist Securities|Oppenheimer|KBW|Cain Brothers|Marathon Capital|"
    "Needham & Company|ARMA Partners|Zaoui & Co|Alantra|Greenhill|MUFG")

# ── Private equity / growth equity ───────────────────────────────────────────
ROSTER += _rows("pe", "T1",
    "Blackstone|KKR|The Carlyle Group|Apollo Global Management|TPG|Bain Capital|Warburg Pincus|"
    "Advent International|Silver Lake|Vista Equity Partners|Thoma Bravo|EQT|CVC Capital Partners|"
    "Hellman & Friedman|Brookfield|Ares Management|Partners Group|Hg|General Atlantic|"
    "Clayton Dubilier & Rice|Insight Partners")
ROSTER += _rows("pe", "T2",
    "HarbourVest Partners|Hamilton Lane|Adams Street Partners|Permira|Leonard Green & Partners|GTCR|"
    "Francisco Partners|Summit Partners|TA Associates|Providence Equity Partners|Apax Partners|Ardian|"
    "BC Partners|Cinven|L Catterton|Clearlake Capital|Genstar Capital|Platinum Equity|"
    "New Mountain Capital|Lone Star Funds|Oaktree Capital|Sycamore Partners|Madison Dearborn Partners|"
    "Onex Partners|Cerberus Capital Management|Fortress Investment Group|Searchlight Capital Partners|"
    "Thomas H. Lee Partners|Audax Group|General Catalyst|Tiger Global|Neuberger Berman|Pantheon")
ROSTER += _rows("pe", "T3",
    "H.I.G. Capital|Golden Gate Capital|Charlesbank Capital Partners|GI Partners|HGGC|Sun Capital Partners|"
    "Arcline Investment Management|Bridgepoint|TSG Consumer Partners|KSL Capital Partners|Riverstone Holdings|"
    "EIG|NGP|Reverence Capital Partners|Parthenon Capital Partners|Vistria Group|K1 Investment Management|"
    "Battery Ventures|Great Hill Partners|Alpine Investors|ABRY Partners|Kohlberg & Company|Oak Hill Capital|"
    "One Rock Capital Partners|Sentinel Capital Partners|Arlington Capital Partners|Arsenal Capital Partners|"
    "Gridiron Capital|Marlin Equity Partners|STG Partners|DigitalBridge|Lime Rock Partners|"
    "Altaris Capital Partners|Aquiline Capital Partners|Arctos Partners|The Riverside Company|"
    "Paine Schwartz Partners|Wind Point Partners|Flexpoint Ford|Kinderhook Industries|Waud Capital Partners|"
    "Sumeru Equity Partners|Thompson Street Capital Partners|Mainsail Partners|Serent Capital|Level Equity|"
    "Lincolnshire Management|Primus Capital|Rotunda Capital Partners|Bow River Capital|NMS Capital|"
    "Twin Brook Capital Partners")

# ── Venture capital ──────────────────────────────────────────────────────────
ROSTER += _rows("vc", "T1",
    "Sequoia Capital|Andreessen Horowitz|Accel|Benchmark|Founders Fund|Greylock|Kleiner Perkins|"
    "Lightspeed Venture Partners|Bessemer Venture Partners|New Enterprise Associates|Index Ventures|"
    "Khosla Ventures|Thrive Capital|Coatue Management|SoftBank Vision Fund|Dragoneer Investment Group")
ROSTER += _rows("vc", "T2",
    "TCV|IVP|ICONIQ Growth|Bain Capital Ventures|Menlo Ventures|Redpoint Ventures|Union Square Ventures|"
    "First Round Capital|Felicis Ventures|Meritech Capital Partners|Sapphire Ventures|Norwest Venture Partners|"
    "GGV Capital|B Capital|DST Global|Ribbit Capital|Accel-KKR|TPG Growth|WestCap|Prosus Ventures|"
    "Mubadala Capital|CPP Investments|8VC|Social Capital|Scale Venture Partners|Highland Capital Partners|"
    "Georgian|NewView Capital|Y Combinator|Flagship Pioneering|ARCH Venture Partners|Lux Capital|"
    "DCVC|GV|a16z Crypto|Paradigm|QED Investors")
ROSTER += _rows("vc", "T3",
    "Lowercarbon Capital|Breakthrough Energy Ventures|Energy Impact Partners|Congruent Ventures|"
    "Atlas Venture|Third Rock Ventures|5AM Ventures|Versant Ventures|OrbiMed Advisors|Deerfield Management|"
    "F-Prime Capital|Radical Ventures|Amplify Partners|Zetta Venture Partners|FirstMark Capital|"
    "Playground Global|Craft Ventures|Initialized Capital|Homebrew|BoxGroup|Lerer Hippeau|Slow Ventures|"
    "Susa Ventures|Upfront Ventures|Madrona Venture Group|RRE Ventures|Valar Ventures|Nyca Partners|"
    "Pantera Capital|Polychain Capital|Electric Capital|Blockchain Capital|Intel Capital|Salesforce Ventures|"
    "M12|Qualcomm Ventures|Samsung NEXT|Cisco Investments|Toyota Ventures|BMW i Ventures|SOSV")

# ── Corporate strategy / BizOps / corp dev (large US companies) ───────────────
ROSTER += _rows("corp", "T1",
    "Google|Amazon|Apple|Meta|Microsoft|Nvidia|Tesla|Netflix|Salesforce|Oracle|Adobe|Stripe|Uber|"
    "Airbnb|Palantir|ServiceNow|Snowflake|Intuit|Cisco|IBM|SAP|LinkedIn|Intel|Qualcomm|Broadcom|"
    "Micron Technology|Dell Technologies")
ROSTER += _rows("corp", "T2",
    "Visa|Mastercard|PayPal|Block|Shopify|Workday|Atlassian|Datadog|Twilio|Okta|Zoom|Snap|Spotify|"
    "Roblox|Electronic Arts|Roku|DoorDash|Lyft|Dropbox|HP|Vercel|Capital One|American Express|"
    "Jane Street|Citadel|Citadel Securities|Hudson River Trading|Discover Financial|Wells Fargo|"
    "Johnson & Johnson|CVS Health|Elevance Health|Amgen|Gilead Sciences|Medtronic|Procter & Gamble|"
    "The Coca-Cola Company|PepsiCo|Nike|Walmart|Costco Wholesale|Starbucks|Target|The Home Depot|"
    "McDonald's|Estee Lauder|The Walt Disney Company|Comcast|Warner Bros. Discovery|Paramount Global|"
    "AT&T|Verizon|T-Mobile|Boeing|Lockheed Martin|RTX|Honeywell|General Electric|3M|Caterpillar|"
    "UPS|FedEx|Delta Air Lines|United Airlines|American Airlines|World Wide Technology")

# ─────────────────────────────────────────────────────────────────────────────
# SEEDS — keyless endpoints already found (validate, don't guess).
#   value: (platform, token)  OR  list of them.  workday tokens = full landing URL.
# Only listed where the token is NOT trivially the firm-name slug (those the
# guesser derives on its own) or where it's a Workday feed worth validating.
# ─────────────────────────────────────────────────────────────────────────────
SEED_KEYLESS: dict[str, object] = {
    # greenhouse (non-obvious slugs)
    "Warburg Pincus": ("greenhouse", "warburgpincusllc"),
    "Silver Lake": ("greenhouse", "silverlakedsp"),
    "Summit Partners": ("greenhouse", "summitpartnerslp"),
    "Brattle Group": ("greenhouse", "thebrattlegroup"),
    "FT Partners": ("greenhouse", "financialtechnologypartners"),
    "Social Capital": ("greenhouse", "socialcapital57"),
    "Flagship Pioneering": ("greenhouse", "flagshippioneeringinc"),
    "Putnam Associates": ("greenhouse", "putnamassociatesllc"),
    "ClearView Healthcare Partners": ("greenhouse", "clearviewhealthcarepartners"),
    "Bessemer Venture Partners": ("greenhouse", "bvpanalyst"),
    "Lyft": ("greenhouse", "lyft"),
    "Datadog": ("greenhouse", "datadog"),
    "Anthropic": ("greenhouse", "anthropic"),
    # lever
    "Compass Lexecon": ("lever", "compasslexecon"),
    "ghSMART": ("lever", "ghsmartjobs"),
    "Prosus Ventures": ("lever", "prosus"),
    "Palantir": ("lever", "palantir"),
    # ashby
    "First Round Capital": ("ashby", "firstround"),
    "8VC": ("ashby", "8vc"),
    "Snowflake": ("ashby", "snowflake"),
    # smartrecruiters
    "CPP Investments": ("smartrecruiters", "CPPInvestmentsInvestissementsRPC"),
    # workday (full careers landing URL -> converted to /wday/cxs/.../jobs)
    "Blackstone": ("workday", "https://blackstone.wd1.myworkdayjobs.com/Blackstone_Careers"),
    "Apollo Global Management": ("workday", "https://athene.wd5.myworkdayjobs.com/Apollo_Careers"),
    "Advent International": ("workday", "https://adventinternational.wd12.myworkdayjobs.com/AdventAgency"),
    "Brookfield": ("workday", "https://brookfield.wd5.myworkdayjobs.com/BrookfieldCareers"),
    "Ares Management": ("workday", "https://ares.wd1.myworkdayjobs.com/Ares_Careers"),
    "Oaktree Capital": ("workday", "https://oaktree.wd1.myworkdayjobs.com/OaktreeCareers"),
    "Providence Equity Partners": ("workday", "https://provequity.wd5.myworkdayjobs.com/PEP_External_Career_Site"),
    "Apax Partners": ("workday", "https://apax.wd3.myworkdayjobs.com/ApaxCareers"),
    "H.I.G. Capital": ("workday", "https://higcapital.wd5.myworkdayjobs.com/LinkedIn"),
    "Bridgepoint": ("workday", "https://bridgepoint.wd3.myworkdayjobs.com/BridgepointCareers"),
    "DigitalBridge": ("workday", "https://digitalbridge.wd1.myworkdayjobs.com/DigitalBridgeCareers"),
    "Harris Williams": ("workday", "https://pnc.wd5.myworkdayjobs.com/HarrisWilliams"),
    "Huron Consulting Group": ("workday", "https://huron.wd1.myworkdayjobs.com/huroncareers"),
    "Cornerstone Research": ("workday", "https://cornerstone.wd501.myworkdayjobs.com/CornerstoneResearch_Careers"),
    "Piper Sandler": ("workday", "https://pipersandler.wd501.myworkdayjobs.com/Piper_Sandler_Careers"),
    "Strategy&": ("workday", "https://pwc.wd3.myworkdayjobs.com/Global_Campus_Careers"),
    "Accenture Strategy": ("workday", "https://accenture.wd103.myworkdayjobs.com/AccentureCareers"),
    "Adobe": ("workday", "https://adobe.wd5.myworkdayjobs.com/external_experienced"),
    "Intel": ("workday", "https://intel.wd1.myworkdayjobs.com/External"),
    "Mastercard": ("workday", "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers"),
    "ING": ("workday", "https://ing.wd3.myworkdayjobs.com/ICSGBLCOR"),
    "The Coca-Cola Company": ("workday", "https://coke.wd1.myworkdayjobs.com/coca-cola-careers"),
}

# Firms whose only known channel is a stack the collector can't fetch keyless.
# These skip slug-guessing and route straight to Path B (web search).
NOTE: dict[str, str] = {
    # MBB / big-4 strategy — proprietary or Avature/Workday-campus (kept for Path B)
    "McKinsey & Company": "proprietary", "Boston Consulting Group": "proprietary",
    "Bain & Company": "proprietary", "EY-Parthenon": "proprietary",
    "Monitor Deloitte": "proprietary", "KPMG Strategy": "avature",
    "Oliver Wyman": "proprietary", "Roland Berger": "proprietary", "Arthur D. Little": "icims",
    "Booz Allen Hamilton": "proprietary",
    # economic / specialist consulting
    "NERA Economic Consulting": "proprietary", "Analysis Group": "icims",
    "Bates White": "proprietary", "Edgeworth Economics": "proprietary",
    "Economists Incorporated": "cannot-confirm", "Frontier Economics": "proprietary",
    "Oxera": "proprietary", "Copenhagen Economics": "proprietary", "RBB Economics": "proprietary",
    "E.CA Economics": "personio", "Oslo Economics": "proprietary", "Simon-Kucher": "csod",
    "ZS Associates": "proprietary", "Alvarez & Marsal": "proprietary", "FTI Consulting": "selectminds",
    "Stax": "trakstar", "Health Advances": "hrmdirect", "Avasant": "applytojob",
    "Vivaldi Group": "cannot-confirm", "The Value Engineers": "cannot-confirm", "Horvath": "proprietary",
    "Nova Reperta": "proprietary", "Marakon": "cannot-confirm", "Kaiser Associates": "cannot-confirm",
    "Trinity Life Sciences": "proprietary",
    # IB — Oleeo (tal.net) / Taleo / iCIMS / proprietary / email
    "Goldman Sachs": "oleeo", "J.P. Morgan": "proprietary", "Bank of America": "proprietary",
    "Citi": "proprietary", "Evercore": "oleeo", "Centerview Partners": "email", "Lazard": "oleeo",
    "Qatalyst Partners": "proprietary", "Allen & Company": "no-ats", "PJT Partners": "proprietary",
    "Moelis & Company": "oleeo", "Perella Weinberg Partners": "oleeo", "Rothschild & Co": "proprietary",
    "Guggenheim Securities": "proprietary", "Jefferies": "oleeo", "UBS": "proprietary",
    "Barclays": "proprietary", "Deutsche Bank": "proprietary", "HSBC": "eightfold",
    "BNP Paribas": "proprietary", "Credit Agricole CIB": "proprietary", "Societe Generale": "taleo",
    "RBC Capital Markets": "proprietary", "Nomura": "proprietary", "Mizuho": "proprietary",
    "Macquarie": "proprietary", "Standard Chartered": "proprietary", "TD Securities": "proprietary",
    "Santander": "proprietary", "SMBC Nikko": "proprietary", "Daiwa": "proprietary",
    "BMO Capital Markets": "proprietary", "Scotiabank": "proprietary", "Houlihan Lokey": "proprietary",
    "Baird": "proprietary", "Raymond James": "taleo", "Stifel": "icims", "KBW": "icims",
    "Cain Brothers": "icims", "Canaccord Genuity": "proprietary", "Stephens": "proprietary",
    "Cantor Fitzgerald": "proprietary", "Truist Securities": "proprietary", "Oppenheimer": "hrmdirect",
    "Marathon Capital": "applytojob", "Needham & Company": "oleeo", "ARMA Partners": "trakstar",
    "Zaoui & Co": "email", "Alantra": "proprietary", "Greenhill": "email", "MUFG": "cannot-confirm",
    "Morgan Stanley": "workday", "Wells Fargo": "proprietary", "Wells Fargo Securities": "proprietary",
    "TD Cowen": "proprietary",
    # PE — proprietary / email / no-ats / secretive
    "The Carlyle Group": "proprietary", "CVC Capital Partners": "cannot-confirm",
    "Thoma Bravo": "cannot-confirm", "Hellman & Friedman": "cannot-confirm", "Partners Group": "proprietary",
    "Hg": "pinpoint", "Clayton Dubilier & Rice": "cannot-confirm", "Adams Street Partners": "cannot-confirm",
    "Leonard Green & Partners": "cannot-confirm", "GTCR": "cannot-confirm", "TA Associates": "getro",
    "BC Partners": "cannot-confirm", "Cinven": "pinpoint", "Clearlake Capital": "cannot-confirm",
    "Genstar Capital": "no-ats", "Platinum Equity": "cannot-confirm", "Lone Star Funds": "no-ats",
    "Sycamore Partners": "cannot-confirm", "Madison Dearborn Partners": "email", "Onex Partners": "proprietary",
    "Cerberus Capital Management": "proprietary", "Fortress Investment Group": "proprietary",
    "Searchlight Capital Partners": "cannot-confirm", "Thomas H. Lee Partners": "email",
    "Tiger Global": "cannot-confirm", "Neuberger Berman": "workday", "Pantheon": "cannot-confirm",
    "Golden Gate Capital": "cannot-confirm", "Charlesbank Capital Partners": "cannot-confirm",
    "GI Partners": "cannot-confirm", "HGGC": "cannot-confirm", "Sun Capital Partners": "cannot-confirm",
    "Arcline Investment Management": "cannot-confirm", "TSG Consumer Partners": "cannot-confirm",
    "KSL Capital Partners": "cannot-confirm", "Riverstone Holdings": "cannot-confirm", "EIG": "cannot-confirm",
    "NGP": "cannot-confirm", "Reverence Capital Partners": "cannot-confirm",
    "Parthenon Capital Partners": "cannot-confirm", "Vistria Group": "cannot-confirm",
    "K1 Investment Management": "cannot-confirm", "Great Hill Partners": "cannot-confirm",
    "ABRY Partners": "cannot-confirm", "Kohlberg & Company": "cannot-confirm", "Oak Hill Capital": "cannot-confirm",
    "One Rock Capital Partners": "cannot-confirm", "Sentinel Capital Partners": "cannot-confirm",
    "Arlington Capital Partners": "cannot-confirm", "Arsenal Capital Partners": "cannot-confirm",
    "Gridiron Capital": "cannot-confirm", "Marlin Equity Partners": "cannot-confirm", "STG Partners": "cannot-confirm",
    "Lime Rock Partners": "cannot-confirm", "Altaris Capital Partners": "cannot-confirm",
    "Aquiline Capital Partners": "cannot-confirm", "Arctos Partners": "cannot-confirm",
    "Paine Schwartz Partners": "cannot-confirm", "Wind Point Partners": "cannot-confirm",
    "Flexpoint Ford": "cannot-confirm", "Kinderhook Industries": "cannot-confirm",
    "Waud Capital Partners": "cannot-confirm", "Sumeru Equity Partners": "cannot-confirm",
    "Thompson Street Capital Partners": "cannot-confirm", "Serent Capital": "cannot-confirm",
    "Level Equity": "cannot-confirm", "Lincolnshire Management": "cannot-confirm", "Primus Capital": "cannot-confirm",
    "Rotunda Capital Partners": "cannot-confirm", "Bow River Capital": "cannot-confirm", "NMS Capital": "cannot-confirm",
    "Twin Brook Capital Partners": "proprietary",
    # VC — Consider portfolio boards (not firm's own keyless feed) / secretive / email
    "Sequoia Capital": "consider", "Accel": "consider", "Greylock": "consider",
    "Lightspeed Venture Partners": "consider", "Kleiner Perkins": "consider", "Khosla Ventures": "consider",
    "Coatue Management": "consider", "New Enterprise Associates": "consider", "Index Ventures": "proprietary",
    "Benchmark": "no-ats", "Founders Fund": "cannot-confirm", "Thrive Capital": "cannot-confirm",
    "SoftBank Vision Fund": "ventureloop", "Dragoneer Investment Group": "cannot-confirm",
    "TCV": "consider", "IVP": "consider", "ICONIQ Growth": "proprietary", "Bain Capital Ventures": "consider",
    "Menlo Ventures": "consider", "Redpoint Ventures": "consider", "Union Square Ventures": "consider",
    "Felicis Ventures": "consider", "Meritech Capital Partners": "cannot-confirm", "Sapphire Ventures": "consider",
    "Norwest Venture Partners": "consider", "GGV Capital": "consider", "B Capital": "cannot-confirm",
    "DST Global": "cannot-confirm", "Ribbit Capital": "cannot-confirm", "Accel-KKR": "cannot-confirm",
    "TPG Growth": "cannot-confirm", "WestCap": "cannot-confirm", "Mubadala Capital": "careers-page",
    "Scale Venture Partners": "cannot-confirm", "Highland Capital Partners": "cannot-confirm",
    "Georgian": "cannot-confirm", "NewView Capital": "cannot-confirm", "Y Combinator": "proprietary",
    "ARCH Venture Partners": "email", "Lux Capital": "consider", "DCVC": "consider", "GV": "consider",
    "a16z Crypto": "consider", "Paradigm": "consider", "QED Investors": "consider",
    "Lowercarbon Capital": "getro", "Breakthrough Energy Ventures": "consider",
    "Energy Impact Partners": "cannot-confirm", "Congruent Ventures": "cannot-confirm",
    "Atlas Venture": "cannot-confirm", "Third Rock Ventures": "cannot-confirm", "5AM Ventures": "cannot-confirm",
    "Versant Ventures": "cannot-confirm", "OrbiMed Advisors": "cannot-confirm", "Deerfield Management": "cannot-confirm",
    "F-Prime Capital": "cannot-confirm", "Radical Ventures": "cannot-confirm",
    "Zetta Venture Partners": "cannot-confirm", "FirstMark Capital": "cannot-confirm",
    "Playground Global": "cannot-confirm", "Craft Ventures": "cannot-confirm", "Initialized Capital": "cannot-confirm",
    "Homebrew": "cannot-confirm", "BoxGroup": "cannot-confirm", "Lerer Hippeau": "cannot-confirm",
    "Slow Ventures": "cannot-confirm", "Susa Ventures": "cannot-confirm", "Upfront Ventures": "cannot-confirm",
    "Madrona Venture Group": "cannot-confirm", "RRE Ventures": "cannot-confirm", "Valar Ventures": "cannot-confirm",
    "Nyca Partners": "cannot-confirm", "Pantera Capital": "cannot-confirm", "Polychain Capital": "cannot-confirm",
    "Electric Capital": "cannot-confirm", "Blockchain Capital": "cannot-confirm", "Intel Capital": "cannot-confirm",
    "Salesforce Ventures": "cannot-confirm", "M12": "cannot-confirm", "Qualcomm Ventures": "cannot-confirm",
    "Samsung NEXT": "cannot-confirm", "Cisco Investments": "cannot-confirm", "Toyota Ventures": "cannot-confirm",
    "BMW i Ventures": "cannot-confirm", "SOSV": "cannot-confirm",
    # Corp giants — proprietary / Workday-unknown-site / Eightfold / SuccessFactors
    "Google": "proprietary", "Amazon": "proprietary", "Apple": "proprietary", "Meta": "proprietary",
    "Microsoft": "eightfold", "Nvidia": "proprietary", "Tesla": "proprietary", "Netflix": "proprietary",
    "Salesforce": "proprietary", "Oracle": "oraclecloud", "Uber": "proprietary", "ServiceNow": "proprietary",
    "Intuit": "proprietary", "Cisco": "proprietary", "IBM": "proprietary", "SAP": "successfactors",
    "LinkedIn": "proprietary", "Qualcomm": "workday", "Broadcom": "proprietary", "Micron Technology": "proprietary",
    "Dell Technologies": "proprietary", "Visa": "proprietary", "PayPal": "proprietary", "Shopify": "proprietary",
    "Workday": "proprietary", "Atlassian": "proprietary", "Twilio": "proprietary", "Okta": "proprietary",
    "Zoom": "proprietary", "Snap": "proprietary", "Spotify": "greenhouse", "Roblox": "proprietary",
    "Electronic Arts": "avature", "Roku": "proprietary", "DoorDash": "proprietary", "Dropbox": "proprietary",
    "HP": "proprietary", "Capital One": "proprietary", "American Express": "taleo", "Citadel": "proprietary",
    "Citadel Securities": "proprietary", "Hudson River Trading": "proprietary", "Discover Financial": "workday",
    "Johnson & Johnson": "workday", "CVS Health": "workday", "Elevance Health": "workday", "Amgen": "workday",
    "Gilead Sciences": "workday", "Medtronic": "workday", "Procter & Gamble": "workday",
    "PepsiCo": "workday", "Nike": "workday", "Walmart": "workday", "Costco Wholesale": "proprietary",
    "Starbucks": "workday", "Target": "workday", "The Home Depot": "workday", "McDonald's": "workday",
    "Estee Lauder": "workday", "The Walt Disney Company": "workday", "Comcast": "workday",
    "Warner Bros. Discovery": "workday", "Paramount Global": "workday", "AT&T": "workday", "Verizon": "proprietary",
    "T-Mobile": "workday", "Boeing": "workday", "Lockheed Martin": "workday", "RTX": "workday",
    "Honeywell": "workday", "General Electric": "workday", "3M": "workday", "Caterpillar": "workday",
    "UPS": "workday", "FedEx": "proprietary", "Delta Air Lines": "workday", "United Airlines": "proprietary",
    "American Airlines": "workday", "World Wide Technology": "proprietary",
}

# Notes that still merit slug-guessing (a real keyless board may exist anyway).
GUESSABLE_NOTES = {"cannot-confirm", "consider", "getro", "none", "no-ats", "greenhouse", ""}
# Platforms the collector can actually fetch keyless.
KEYLESS = ("greenhouse", "lever", "ashby", "smartrecruiters", "workable")
_SUFFIXES = ("company", "partners", "capital", "management", "group", "ventures", "associates",
             "advisors", "holdings", "international", "securities", "consulting", "llc", "inc",
             "lp", "llp", "co", "and", "the")


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ").replace("+", " plus ")
    return "".join(ch if ch.isalnum() else " " for ch in s)


def slug_variants(name: str) -> list[str]:
    words = [w for w in _norm(name).split() if w]
    out: list[str] = []

    def add(v: str) -> None:
        if v and v not in out:
            out.append(v)

    add("".join(words))                                  # leonardgreenandpartners
    trimmed = list(words)
    while len(trimmed) > 1 and trimmed[-1] in _SUFFIXES:  # drop trailing suffix words
        trimmed = trimmed[:-1]
        add("".join(trimmed))
    add("".join(w for w in words if w not in _SUFFIXES))  # drop all suffix words
    add("".join(words) + "llc")
    return out[:5]


def _workday_endpoint(landing: str) -> str | None:
    """Turn a Workday careers landing URL into its /wday/cxs/{tenant}/{site}/jobs feed."""
    parts = urlsplit(landing)
    host = parts.netloc
    if "myworkdayjobs.com" not in host:
        return None
    tenant = host.split(".")[0]
    segs = [s for s in parts.path.split("/") if s and not (len(s) == 5 and s[2] == "-")]
    if not segs:
        return None
    site = segs[-1]
    return urlunsplit((parts.scheme, host, f"/wday/cxs/{tenant}/{site}/jobs", "", ""))


def _probe_keyless(platform: str, token: str, http: RetryingHttpClient) -> tuple[int, dict] | None:
    fetchers = {"greenhouse": ats.fetch_greenhouse, "lever": ats.fetch_lever,
                "ashby": ats.fetch_ashby, "smartrecruiters": ats.fetch_smartrecruiters,
                "workable": ats.fetch_workable, "workday": workday.fetch_workday}
    fn = fetchers.get(platform)
    if fn is None:
        return None
    try:
        postings = fn(token, http=http)
    except Exception:
        return None
    if not postings:
        return None
    p0 = postings[0]
    return len(postings), {"title": p0.title, "location": p0.location, "link": p0.link}


def probe_firm(entry: dict) -> dict:
    http = RetryingHttpClient()
    name, note = entry["name"], entry.get("note", "")
    result = dict(entry)
    result["feed"] = None

    # 1. Validate a known keyless seed first.
    seed = SEED_KEYLESS.get(name)
    seeds = seed if isinstance(seed, list) else ([seed] if seed else [])
    for platform, raw in seeds:
        token = raw
        if platform == "workday":
            token = _workday_endpoint(raw) or raw
        hit = _probe_keyless(platform, token, http)
        if hit:
            n, sample = hit
            result["feed"] = {"platform": platform, "token": token, "jobs": n,
                              "source": "seed", "sample": sample}
            return result

    # 2. Guess slugs for firms that plausibly self-host a keyless board.
    if note in GUESSABLE_NOTES:
        for slug in slug_variants(name):
            for platform in ("greenhouse", "lever", "ashby"):
                hit = _probe_keyless(platform, slug, http)
                if hit:
                    n, sample = hit
                    result["feed"] = {"platform": platform, "token": slug, "jobs": n,
                                      "source": "guess", "needs_review": True, "sample": sample}
                    return result
    return result


def build_roster() -> list[dict]:
    seen: dict[str, dict] = {}
    for name, domain, tier in ROSTER:
        key = _norm(name)
        if key in seen:
            seen[key].setdefault("also", []).append(f"{domain}/{tier}")
            continue
        seen[key] = {"name": name, "domain": domain, "tier": tier, "note": NOTE.get(name, "")}
    return list(seen.values())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-probe", action="store_true", help="just rebuild the name list")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args(argv)

    roster = build_roster()
    root = Path(__file__).resolve().parent
    (root / "roster_candidates.json").write_text(
        json.dumps(roster, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"roster_candidates.json — {len(roster)} unique firms "
          f"(from {len(ROSTER)} rows across 5 files)")
    if args.no_probe:
        return 0

    print(f"probing keyless ATS feeds ({args.workers} workers)…\n")
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(probe_firm, e): e for e in roster}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            if r["feed"]:
                f = r["feed"]
                flag = "≈" if f.get("needs_review") else "✓"
                print(f"  {flag} {r['name'][:32]:<32} {f['platform']:<15}{f['token'][:34]:<35}"
                      f"{f['jobs']:>4} jobs")
            if i % 50 == 0:
                print(f"    …{i}/{len(roster)}")

    results.sort(key=lambda r: (r["domain"], r["tier"], r["name"]))
    (root / "roster_ats_discovered.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Summary.
    confirmed = [r for r in results if r["feed"]]
    seeded = [r for r in confirmed if r["feed"]["source"] == "seed"]
    guessed = [r for r in confirmed if r["feed"]["source"] == "guess"]
    pathb = [r for r in results if not r["feed"]]
    print("\n" + "=" * 60)
    print(f"CONFIRMED keyless feeds : {len(confirmed):>3}  "
          f"(seed-validated {len(seeded)}, newly discovered {len(guessed)})")
    print(f"→ Path B (web search)   : {len(pathb):>3}")
    by_domain: dict[str, list[int]] = {}
    for r in results:
        d = by_domain.setdefault(r["domain"], [0, 0])
        d[0 if r["feed"] else 1] += 1
    print("\n  domain        keyless  path-B")
    for d in ("consulting", "ib", "pe", "vc", "corp"):
        if d in by_domain:
            k, b = by_domain[d]
            print(f"  {d:<13}{k:>6}{b:>8}")
    print("=" * 60)
    print("wrote roster_ats_discovered.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
