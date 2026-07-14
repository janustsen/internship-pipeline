"""Deeper ATS discovery — pass 2+.  Re-attacks the current Path-B set only.

Reads roster_ats_discovered.json, targets firms with feed==None, and tries harder:
  1. expanded slug variants across ALL keyless ATS platforms (gh/lever/ashby/SR/workable)
  2. a Workday shard+site SWEEP for corporate/finance firms — find the live shard by a
     fast 404(host-exists)-vs-ConnectionError(no-such-host) probe on site "External",
     then sweep site names on that shard
  3. lever-EU (api.eu.lever.co) for the handful on EU Lever
Low concurrency to avoid rate-limit false-negatives. Idempotent: only fills empty
feeds, merges hits back into roster_ats_discovered.json, prints the new yield.

Run:  python3 discover_ats2.py [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from http_client import RetryingHttpClient
from models import RawPosting
from sources import ats

ROOT = Path(__file__).resolve().parent
DISC = ROOT / "roster_ats_discovered.json"
_COLL = ROOT / "ats_collisions.json"
BLOCKLIST = set(json.loads(_COLL.read_text()).get("blocklist", {})) if _COLL.exists() else set()

_SUFFIX = {"company", "companies", "partners", "capital", "management", "group", "ventures",
           "associates", "advisors", "advisers", "holdings", "international", "securities",
           "consulting", "consultants", "llc", "inc", "lp", "llp", "co", "and", "the",
           "global", "technologies", "labs", "systems"}
# Known Workday tenants/abbreviations for big firms whose tenant != name slug.
WD_TENANT_HINTS = {
    "Johnson & Johnson": ["jnj"], "Nike": ["nike"], "PepsiCo": ["pepsico", "pepsicojobs"],
    "Walmart": ["walmart"], "Starbucks": ["starbucks"], "Costco Wholesale": ["costco"],
    "Caterpillar": ["caterpillar"], "Honeywell": ["honeywell"], "General Electric": ["ge", "geaerospace"],
    "UPS": ["ups"], "Delta Air Lines": ["delta"], "American Airlines": ["aa", "americanairlines"],
    "United Airlines": ["united", "ual"], "AT&T": ["att"], "Verizon": ["verizon"],
    "Paramount Global": ["paramount"], "Warner Bros. Discovery": ["wbd", "warnermedia"],
    "CVS Health": ["cvshealth", "cvs"], "Qualcomm": ["qualcomm"], "Discover Financial": ["discover"],
    "American Express": ["aexp", "amex"], "Lockheed Martin": ["lockheedmartin", "lmco"],
    "RTX": ["rtx", "raytheon"], "Estee Lauder": ["elcompanies"], "The Home Depot": ["homedepot"],
    "Capital One": ["capitalone"], "McDonald's": ["mcdonalds"], "Target": ["target"],
    "Broadcom": ["broadcom"], "Micron Technology": ["micron"], "Dell Technologies": ["dell", "delltechnologies"],
    "Oracle": ["oracle"], "IBM": ["ibm"], "Cisco": ["cisco"], "PayPal": ["paypal", "pypl"],
    "Workday": ["workday"], "ServiceNow": ["servicenow"], "Atlassian": ["atlassian"],
    "TD Cowen": ["cowen"], "Truist Securities": ["truist"], "BMO Capital Markets": ["bmo"],
    "Scotiabank": ["scotiabank", "bns"], "TD Securities": ["td", "tdbank"], "Nomura": ["nomura"],
    "Macquarie": ["macquarie"], "Neuberger Berman": ["neubergerberman", "nb"],
    "Fortress Investment Group": ["fortress"], "Ares Management": ["ares"], "Apax Partners": ["apax"],
    "Bridgepoint": ["bridgepoint"], "Sixth Street": ["sixthstreet"], "Stone Point Capital": ["stonepoint"],
}
WD_SHARDS = ["wd1", "wd3", "wd5", "wd2", "wd10", "wd12", "wd101", "wd102", "wd103", "wd501", "wd502", "wd505"]
WD_SITES = ["External", "Careers", "External_Career_Site", "Global", "Search", "Campus",
            "INTERN", "Professional", "{t}", "{t}careers", "{C}Careers", "{C}_Careers",
            "{C}ExternalCareerSite", "{C}External", "External_Careers", "careers"]
# Firms known to be on EU Lever.
LEVER_EU = {"Prosus Ventures": "prosus"}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ").replace("+", " plus ")
    return "".join(ch if ch.isalnum() else " " for ch in s)


def slug_variants(name: str) -> list[str]:
    words = [w for w in _norm(name).split() if w]
    out: list[str] = []
    def add(v: str) -> None:
        if v and len(v) >= 3 and v not in out:
            out.append(v)
    add("".join(words))
    trimmed = list(words)
    while len(trimmed) > 1 and trimmed[-1] in _SUFFIX:
        trimmed = trimmed[:-1]; add("".join(trimmed))
    nosuf = [w for w in words if w not in _SUFFIX]
    add("".join(nosuf))
    add("".join(words) + "llc"); add("".join(words) + "inc")
    add("".join(nosuf) + "careers"); add("".join(words) + "careers")
    add("-".join(nosuf)); add("-".join(words))
    if len(nosuf) >= 2:
        add("".join(nosuf[:2]))
    return out[:9]


def _pascal(name: str) -> list[str]:
    words = [w for w in _norm(name).split() if w and w not in {"the", "and"}]
    if not words:
        return []
    cap = "".join(w.capitalize() for w in words)
    return [cap, "".join(w.capitalize() for w in words if w not in _SUFFIX)][:2]


def _one(fn, tok, http) -> tuple[int, dict] | None:
    try:
        p: list[RawPosting] = fn(tok, http=http)
    except Exception:
        return None
    if not p:
        return None
    return len(p), {"title": p[0].title, "location": p[0].location, "link": p[0].link}


def _lever_eu(tok: str, http: RetryingHttpClient) -> tuple[int, dict] | None:
    try:
        r = http.get(f"https://api.eu.lever.co/v0/postings/{tok}", params={"mode": "json"})
        data = r.json()
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    j = data[0]
    return len(data), {"title": j.get("text", ""), "location": "", "link": j.get("hostedUrl", "")}


def _wd_probe(tenant: str, shard: str, site: str, http: RetryingHttpClient):
    C = tenant.capitalize()
    site = site.replace("{t}", tenant).replace("{C}", C)
    ep = f"https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = http.post(ep, json={"appliedFacets": {}, "limit": 3, "offset": 0, "searchText": ""},
                      headers={"Content-Type": "application/json", "Accept": "application/json"})
    except Exception:
        return ("nohost", None)  # DNS/conn error → wrong shard
    try:
        p = r.json()
    except Exception:
        return ("host", None)
    if isinstance(p, dict) and (isinstance(p.get("total"), int) and p["total"] > 0 or p.get("jobPostings")):
        jp = p.get("jobPostings") or []
        s = {"title": jp[0].get("title"), "location": jp[0].get("locationsText")} if jp else None
        return ("hit", {"endpoint": ep, "total": p.get("total") or len(jp), "sample": s})
    return ("host", None)  # site 404/empty but host exists


def discover_workday(name: str, http: RetryingHttpClient):
    tenants = list(dict.fromkeys(WD_TENANT_HINTS.get(name, []) + slug_variants(name)[:2]))
    for tenant in tenants:
        live_shard = None
        for shard in WD_SHARDS:
            kind, hit = _wd_probe(tenant, shard, "External", http)
            if kind == "hit":
                return {"platform": "workday", "token": hit["endpoint"], "jobs": hit["total"],
                        "sample": hit["sample"]}
            if kind == "host":
                live_shard = shard; break
        if live_shard:
            for site in WD_SITES:
                kind, hit = _wd_probe(tenant, live_shard, site, http)
                if kind == "hit":
                    return {"platform": "workday", "token": hit["endpoint"], "jobs": hit["total"],
                            "sample": hit["sample"]}
    return None


SKIP_SLUG_NOTES = {"oleeo", "taleo", "icims", "avature", "eightfold", "successfactors",
                   "email", "hrmdirect", "pinpoint", "applytojob", "trakstar", "personio",
                   "csod", "careers-page", "ventureloop", "oraclecloud", "selectminds"}
WD_DOMAINS = {"corp", "ib", "pe", "consulting"}


def probe_firm(entry: dict) -> dict | None:
    http = RetryingHttpClient(max_retries=1, timeout=8)
    name, note, domain = entry["name"], entry.get("note", ""), entry["domain"]
    if name in BLOCKLIST:  # known slug-collision → never auto-accept
        return None

    # 1. Slug-guess ATS boards (skip firms whose note says a stack we can't fetch).
    if note not in SKIP_SLUG_NOTES:
        slugs = slug_variants(name)
        for slug in slugs:
            for plat, fn in (("greenhouse", ats.fetch_greenhouse), ("lever", ats.fetch_lever),
                             ("ashby", ats.fetch_ashby), ("workable", ats.fetch_workable)):
                hit = _one(fn, slug, http)
                if hit:
                    n, s = hit
                    return {**entry, "feed": {"platform": plat, "token": slug, "jobs": n,
                                              "source": "guess2", "needs_review": True, "sample": s}}
        for pas in _pascal(name):
            hit = _one(ats.fetch_smartrecruiters, pas, http)
            if hit:
                n, s = hit
                return {**entry, "feed": {"platform": "smartrecruiters", "token": pas, "jobs": n,
                                          "source": "guess2", "needs_review": True, "sample": s}}

    # 2. EU Lever.
    if name in LEVER_EU:
        hit = _lever_eu(LEVER_EU[name], http)
        if hit:
            n, s = hit
            return {**entry, "feed": {"platform": "lever-eu", "token": LEVER_EU[name], "jobs": n,
                                      "source": "guess2", "needs_review": True, "sample": s}}

    # 3. Workday shard+site sweep for corporate/finance firms.
    if domain in WD_DOMAINS or name in WD_TENANT_HINTS:
        wd = discover_workday(name, http)
        if wd:
            return {**entry, "feed": {**wd, "source": "workday-sweep", "needs_review": True}}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    res = json.loads(DISC.read_text())
    pathb = [r for r in res if not r.get("feed")]
    print(f"Path-B firms to re-attack: {len(pathb)}  ({args.workers} workers)\n")

    found: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(probe_firm, e): e["name"] for e in pathb}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r:
                f = r["feed"]; found[r["name"]] = f
                print(f"  + {r['name'][:30]:<31}{f['platform']:<13}{f['token'][:40]:<41}{f['jobs']:>4} jobs")
            if i % 60 == 0:
                print(f"    …{i}/{len(pathb)}  (found {len(found)})")

    for r in res:
        if r["name"] in found and not r.get("feed"):
            r["feed"] = found[r["name"]]
    DISC.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    conf = [r for r in res if r.get("feed")]
    print(f"\n{'='*56}\nNEW feeds this pass: {len(found)}")
    print(f"CONFIRMED total now: {len(conf)}   |   Path B: {len(res)-len(conf)}\n{'='*56}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
