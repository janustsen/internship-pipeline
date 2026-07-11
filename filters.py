from __future__ import annotations

import re
from typing import Any

from models import RawPosting
import target_firms


CORPORATE_SUFFIXES = {
    "co",
    "company",
    "companies",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llc",
    "llp",
    "lp",
    "ltd",
    "limited",
    "plc",
    "group",
    "holdings",
    "partners",
}

# Seniority / non-internship signals — ALWAYS reject, even at an allowlisted firm
# and even when the title also contains an in-scope finance term (a "Senior
# Investment Banking Analyst" is still out of scope).
SENIORITY_REJECT_PATTERNS = [
    r"\bsenior\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\bvice president\b",
    r"\bmanaging director\b",
    r"\bph\.?d\b",
    r"\bdoctoral\b",
    r"\bpostdoc(?:toral)?\b",
    r"\bnew[- ]?grad(?:uate)?\b",
    r"\bgraduate program\b",
    r"\brecent graduate\b",
    r"\bexperienced\b",
]

# Out-of-scope role DOMAINS (engineering / product / design). These are skipped
# when the title clearly signals an in-scope finance/consulting/strategy role, so
# "Financial Engineering Summer Analyst" survives while "Software Engineering
# Intern" does not.
DOMAIN_REJECT_PATTERNS = [
    r"\bsoftware\b",
    r"\bswe\b",
    r"\bdeveloper\b",
    r"\bbackend\b",
    r"\bfront[- ]?end\b",
    r"\bfull[- ]?stack\b",
    r"\bdata engineer\b",
    r"\bmachine learning engineer\b",
    r"\bengineer(?:ing)?\b",
    r"\bmechanical engineer(?:ing)?\b",
    r"\belectrical engineer(?:ing)?\b",
    r"\bhardware\b",
    r"\baerospace\b",
    r"\bux\b",
    r"\bui\b",
    r"\bdesign(?:er)?\b",
    r"\bnursing\b",
    r"\bteacher\b",
]

# Title terms that mark a clearly in-scope role (finance / consulting / strategy /
# business). Their presence suppresses the DOMAIN rejects only — never seniority.
IN_SCOPE_TITLE_TERMS = [
    "banking",
    "finance",
    "financial",
    "investment",
    "investing",
    "equity",
    "capital markets",
    "markets",
    "trading",
    "trader",
    "quant",
    "portfolio",
    "asset management",
    "wealth",
    "m&a",
    "mergers",
    "restructuring",
    "private equity",
    "venture capital",
    "hedge fund",
    "consult",
    "strategy",
    "strategic",
    "corporate development",
    "business development",
    "bizops",
    "business",
    "economics",
    "advisory",
    "sales and trading",
    "actuar",
]

INTERNSHIP_SIGNALS = [
    "intern",
    "internship",
    "summer analyst",
    "summer associate",
    "analyst intern",
    "associate intern",
    "spring week",
    "early insight",
    "insight program",
    "sophomore",
    "first year",
    "first-year",
    "second year",
    "second-year",
    "co-op",
    "coop",
    "externship",
    "campus",
    "undergraduate",
]

INTERNSHIP_SIGNAL_PATTERNS = [
    r"\bsummer\b.*\b(analyst|associate|intern)\b",
    r"\b(analyst|associate|intern)\b.*\bsummer\b",
]

# Underclassman / target-cycle signals — used as a ranking boost, NOT a hard gate.
TARGET_CYCLE_SIGNALS = [
    "2027",
    "sophomore",
    "first year",
    "first-year",
    "second year",
    "second-year",
    "spring week",
    "early insight",
    "insight program",
    "diversity",
    "scholars",
]

# Years earlier than the target cycle that are unambiguously stale.
STALE_CYCLE_MAX_YEAR = 2025


def normalize_company_name(value: str) -> str:
    text = value.lower().replace("&", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [word for word in text.split() if word not in {"the"}]
    while words and words[-1] in CORPORATE_SUFFIXES:
        words.pop()
    return " ".join(words)


def normalize_title(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


_ALIAS_INDEX_CACHE: dict[str, dict[str, str]] | None = None


def _firm_alias_index() -> dict[str, dict[str, str]]:
    global _ALIAS_INDEX_CACHE
    if _ALIAS_INDEX_CACHE is None:
        index: dict[str, dict[str, str]] = {}
        for firm in target_firms.TARGET_FIRMS:
            canonical = str(firm["canonical"])
            tier = str(firm["tier"])
            aliases = [canonical, *firm.get("aliases", [])]
            for alias in aliases:
                normalized = normalize_company_name(str(alias))
                if normalized:
                    index[normalized] = {"canonical": canonical, "tier": tier}
        _ALIAS_INDEX_CACHE = index
    return _ALIAS_INDEX_CACHE


def reset_caches() -> None:
    """Clear memoized state (call after mutating target_firms.TARGET_FIRMS in tests)."""
    global _ALIAS_INDEX_CACHE
    _ALIAS_INDEX_CACHE = None


def firm_match(company: str | None) -> dict[str, str] | None:
    if not company:
        return None
    return _firm_alias_index().get(normalize_company_name(company))


def _title_for(posting: RawPosting | dict[str, Any] | str) -> str:
    if isinstance(posting, str):
        return posting
    if isinstance(posting, RawPosting):
        return posting.title
    return str(posting.get("title") or posting.get("name") or "")


def _signal_text_for(posting: RawPosting | dict[str, Any] | str) -> str:
    """Text used for internship-signal detection: title + category (never description,
    which routinely contains reject/off-cycle words that would kill recall)."""
    if isinstance(posting, str):
        return posting
    if isinstance(posting, RawPosting):
        return " ".join([posting.title, posting.category])
    return " ".join(str(posting.get(key) or "") for key in ("title", "name", "category"))


def exclusion_reason(posting: RawPosting | dict[str, Any] | str) -> str | None:
    """Role-scope rejection, evaluated on the TITLE only."""
    title = normalize_title(_title_for(posting))
    if not title:
        return None
    for pattern in SENIORITY_REJECT_PATTERNS:
        if re.search(pattern, title):
            return "out_of_scope_seniority"
    in_scope = any(term in title for term in IN_SCOPE_TITLE_TERMS)
    if not in_scope:
        for pattern in DOMAIN_REJECT_PATTERNS:
            if re.search(pattern, title):
                return "out_of_scope_role"
    return None


def _mentions_stale_cycle(title: str, target_year: int) -> bool:
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", title)]
    if not years:
        return False
    if target_year in years or any(y >= target_year for y in years):
        return False
    return all(y <= STALE_CYCLE_MAX_YEAR for y in years)


def has_internship_signal(posting: RawPosting | dict[str, Any] | str) -> bool:
    text = normalize_title(_signal_text_for(posting))
    return any(signal in text for signal in INTERNSHIP_SIGNALS) or any(
        re.search(pattern, text) for pattern in INTERNSHIP_SIGNAL_PATTERNS
    )


def is_target_cycle(posting: RawPosting | dict[str, Any] | str) -> bool:
    """Soft signal for ranking (does this look like the Summer 2027 / underclassman cycle)."""
    title = normalize_title(_title_for(posting))
    return "2027" in title or any(signal in title for signal in TARGET_CYCLE_SIGNALS)


def is_relevant_posting(
    posting: RawPosting | dict[str, Any] | str,
    *,
    target_year: int = 2027,
) -> bool:
    """High-recall relevance gate. At an allowlisted firm, an internship signal is
    sufficient; only clearly out-of-scope roles or explicitly-stale cycles are dropped.
    Cycle targeting (2027/sophomore) is a boost, not a hard requirement, so an undated
    'Summer Analyst' at a target firm is kept."""
    title = normalize_title(_title_for(posting))
    if not title:
        return False
    if exclusion_reason(posting):
        return False
    if not has_internship_signal(posting):
        return False
    if _mentions_stale_cycle(title, target_year):
        return False
    return True


def candidate_category(posting: RawPosting | dict[str, Any]) -> str:
    if isinstance(posting, RawPosting):
        text = normalize_title(" ".join([posting.title, posting.category]))
    else:
        text = normalize_title(
            " ".join(str(posting.get(key) or "") for key in ("title", "category"))
        )
    if any(term in text for term in ("quant", "trading", "research")):
        return "quant"
    if any(term in text for term in ("consult", "strategy")):
        return "consulting"
    if any(term in text for term in ("corp dev", "corporate development", "bizops", "business")):
        return "business"
    return "business"
