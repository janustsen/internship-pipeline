"""Workday endpoint discovery — flip corporates/PE from Path B to Path A.

Workday exposes an unauthenticated feed at
    https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
The hard-to-guess parts are the shard (wdN) and the career-site path. For each
firm we try a best-guess (tenant, shard) plus a spread of common site names, hit
the board ONCE, and keep only endpoints that return live postings. Nothing is
fabricated — unvalidated candidates are discarded and the firm stays on Path B.

Merges hits into roster_ats_discovered.json.  Run: python3 discover_workday.py
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from http_client import RetryingHttpClient

# (firm, tenant, shard, [exact site guesses first]).  Site spread is added below.
# Confidence varies; validation is the arbiter. Empty exact-site list = rely on spread.
CANDIDATES: list[tuple[str, str, str, list[str]]] = [
    # ── PE (failed seeds — right tenant, wrong site last time) ────────────────
    ("Brookfield", "brookfield", "wd5", ["External", "BrookfieldGlobal"]),
    ("Ares Management", "ares", "wd1", ["Ares_External_Careers", "External"]),
    ("Oaktree Capital", "oaktree", "wd1", ["OaktreeExternalCareers", "External"]),
    ("Apax Partners", "apax", "wd3", ["ApaxExternalCareers", "External"]),
    ("Bridgepoint", "bridgepoint", "wd3", ["External"]),
    ("Neuberger Berman", "neubergerberman", "wd1", ["NBExternalCareerSite", "External"]),
    # ── Financial / fintech corporates ───────────────────────────────────────
    ("Qualcomm", "qualcomm", "wd12", ["External"]),
    ("Discover Financial", "discover", "wd5", ["Discover", "External"]),
    ("American Express", "aexp", "wd1", ["External", "Amex"]),
    # ── Healthcare / pharma ──────────────────────────────────────────────────
    ("Johnson & Johnson", "jnj", "wd1", ["jjcareers", "External"]),
    ("Gilead Sciences", "gilead", "wd1", ["gileadcareers", "Careers"]),
    ("Medtronic", "medtronic", "wd1", ["MedtronicCareers", "External"]),
    ("Amgen", "amgen", "wd1", ["Careers", "External"]),
    ("Elevance Health", "elevancehealth", "wd1", ["ANT", "External"]),
    ("CVS Health", "cvshealth", "wd1", ["External", "CVSHealthJobs"]),
    # ── Consumer / retail ────────────────────────────────────────────────────
    ("Nike", "nike", "wd1", ["nike", "External"]),
    ("PepsiCo", "pepsico", "wd3", ["PepsiCoCareers", "External"]),
    ("Walmart", "walmart", "wd5", ["WalmartExternal", "External"]),
    ("Target", "target", "wd5", ["targetcareers", "External"]),
    ("Starbucks", "starbucks", "wd5", ["External", "StarbucksCareers"]),
    ("The Home Depot", "homedepot", "wd1", ["External", "HomeDepot"]),
    ("Estee Lauder", "elcompanies", "wd5", ["ELCCareers", "External"]),
    ("The Coca-Cola Company", "coke", "wd1", ["coca-cola-careers"]),
    # ── Media / telecom ──────────────────────────────────────────────────────
    ("The Walt Disney Company", "disney", "wd5", ["disneycareer", "External"]),
    ("Comcast", "comcast", "wd5", ["Comcast_Careers", "External"]),
    ("Warner Bros. Discovery", "wbd", "wd5", ["WBDExternal", "External"]),
    ("Paramount Global", "paramount", "wd5", ["ParamountCareers", "External"]),
    ("AT&T", "att", "wd1", ["External", "ATTCareers"]),
    ("T-Mobile", "tmobile", "wd1", ["External", "TMobile"]),
    # ── Aerospace / industrials ──────────────────────────────────────────────
    ("Boeing", "boeing", "wd1", ["External", "BoeingCareers"]),
    ("Lockheed Martin", "lockheedmartin", "wd1", ["External"]),
    ("RTX", "rtx", "wd5", ["External", "RTX"]),
    ("Honeywell", "honeywell", "wd1", ["External", "HoneywellCareers"]),
    ("General Electric", "ge", "wd5", ["External", "GECareers"]),
    ("3M", "3m", "wd1", ["Search", "External"]),
    ("Caterpillar", "caterpillar", "wd5", ["External", "CaterpillarCareers"]),
    ("UPS", "ups", "wd5", ["UPSJobs", "External"]),
    ("Delta Air Lines", "delta", "wd1", ["External", "DeltaCareers"]),
    ("American Airlines", "aa", "wd1", ["External"]),
]

# Generic site names tried for every firm on top of its exact guesses.
_SITE_SPREAD = ["External", "Careers", "External_Career_Site", "Global"]


def _sites(tenant: str, exact: list[str]) -> list[str]:
    cap = tenant.capitalize()
    spread = exact + _SITE_SPREAD + [tenant, f"{tenant}careers", f"{cap}Careers", f"{cap}_Careers"]
    seen: list[str] = []
    for s in spread:
        if s and s not in seen:
            seen.append(s)
    return seen


def _validate(tenant: str, shard: str, site: str, client: RetryingHttpClient):
    endpoint = f"https://{tenant}.{shard}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = client.post(endpoint, json={"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": ""},
                        headers={"Content-Type": "application/json", "Accept": "application/json"})
        p = r.json()
    except Exception:
        return None
    if not isinstance(p, dict):
        return None
    total = p.get("total")
    jp = p.get("jobPostings") or []
    if not (isinstance(total, int) and total > 0) and not jp:
        return None
    sample = None
    if jp and isinstance(jp[0], dict):
        sample = {"title": jp[0].get("title"), "location": jp[0].get("locationsText")}
    return {"endpoint": endpoint, "total": total if isinstance(total, int) else len(jp), "sample": sample}


def discover_one(firm: str, tenant: str, shard: str, exact: list[str]) -> dict | None:
    client = RetryingHttpClient(max_retries=0, timeout=7)
    for site in _sites(tenant, exact):
        hit = _validate(tenant, shard, site, client)
        if hit:
            return {"firm": firm, **hit}
    return None


def main() -> int:
    print(f"probing {len(CANDIDATES)} Workday tenants…\n")
    hits: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(discover_one, f, t, s, e): f for f, t, s, e in CANDIDATES}
        for fut in as_completed(futs):
            h = fut.result()
            if h:
                hits[h["firm"]] = h
                print(f"  ✓ {h['firm'][:30]:<31}{h['total']:>5} jobs  {h['endpoint']}")
    print(f"\n{len(hits)}/{len(CANDIDATES)} Workday feeds confirmed.")

    # Merge into roster_ats_discovered.json.
    root = Path(__file__).resolve().parent
    path = root / "roster_ats_discovered.json"
    res = json.loads(path.read_text(encoding="utf-8"))
    merged = 0
    for r in res:
        h = hits.get(r["name"])
        if h and not r.get("feed"):
            r["feed"] = {"platform": "workday", "token": h["endpoint"], "jobs": h["total"],
                         "source": "workday-discovery", "sample": h["sample"]}
            merged += 1
    path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    conf = [r for r in res if r.get("feed")]
    pathb = [r for r in res if not r.get("feed")]
    print(f"merged {merged} new feeds → roster_ats_discovered.json")
    print(f"CONFIRMED keyless feeds now: {len(conf)}   |   Path B: {len(pathb)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
