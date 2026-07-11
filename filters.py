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

REJECT_TITLE_PATTERNS = [
    r"\bsenior\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\bph\.?d\b",
    r"\bdoctoral\b",
    r"\bpostdoc(?:toral)?\b",
    r"\bnew[- ]?grad(?:uate)?\b",
    r"\bgraduate program\b",
    r"\bfull[- ]?time\b",
    r"\bexperienced\b",
    r"\bsoftware\b",
    r"\bswe\b",
    r"\bdeveloper\b",
    r"\bbackend\b",
    r"\bfront[- ]?end\b",
    r"\bfull[- ]?stack\b",
    r"\bdata engineer\b",
    r"\bmachine learning engineer\b",
    r"\bmechanical engineer\b",
    r"\baerospace\b",
    r"\bdesign(?:er)?\b",
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
    "diversity",
    "scholars",
    "fellow",
    "fellowship",
    "externship",
]

TARGET_CYCLE_SIGNALS = [
    "2027",
    "summer 2027",
    "2027 summer",
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


def _firm_alias_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for firm in target_firms.TARGET_FIRMS:
        canonical = str(firm["canonical"])
        tier = str(firm["tier"])
        aliases = [canonical, *firm.get("aliases", [])]
        for alias in aliases:
            normalized = normalize_company_name(str(alias))
            if normalized:
                index[normalized] = {"canonical": canonical, "tier": tier}
    return index


def firm_match(company: str | None) -> dict[str, str] | None:
    if not company:
        return None
    return _firm_alias_index().get(normalize_company_name(company))


def _text_for(posting: RawPosting | dict[str, Any] | str) -> str:
    if isinstance(posting, str):
        return posting
    if isinstance(posting, RawPosting):
        return " ".join([posting.title, posting.category, posting.description])
    return " ".join(
        str(posting.get(key) or "") for key in ("title", "category", "description", "content")
    )


def exclusion_reason(posting: RawPosting | dict[str, Any] | str) -> str | None:
    text = normalize_title(_text_for(posting))
    for pattern in REJECT_TITLE_PATTERNS:
        if re.search(pattern, text):
            return "out_of_scope_role"
    return None


def is_relevant_posting(
    posting: RawPosting | dict[str, Any] | str,
    *,
    target_year: int = 2027,
) -> bool:
    text = normalize_title(_text_for(posting))
    if not text:
        return False
    if exclusion_reason(text):
        return False

    has_internship_signal = any(signal in text for signal in INTERNSHIP_SIGNALS)
    has_cycle_signal = str(target_year) in text or any(
        signal in text for signal in TARGET_CYCLE_SIGNALS
    )

    # At an allowlisted firm, a generic "2027 Summer Analyst Program" is enough.
    return has_internship_signal and has_cycle_signal


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
