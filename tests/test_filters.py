from __future__ import annotations

import filters
from filters import firm_match, is_relevant_posting


def test_allowlist_alias_gate() -> None:
    assert firm_match("J.P. Morgan Chase Inc.") == {"canonical": "JPMorgan", "tier": "T1"}
    assert firm_match("Morgan Stanley Group") == {"canonical": "Morgan Stanley", "tier": "T1"}
    assert firm_match("Morgan & Morgan LLC") is None
    assert firm_match("Random Startup") is None


def test_generic_tier_one_internship_passes_without_finance_keyword() -> None:
    assert not hasattr(filters, "is_finance_domain")
    assert is_relevant_posting({"title": "2027 Summer Analyst Program", "company": "JPMorgan"})


def test_filter_rejects_senior_phd_new_grad_and_out_of_scope_roles() -> None:
    assert not is_relevant_posting({"title": "2027 Senior Summer Analyst Internship"})
    assert not is_relevant_posting({"title": "2027 PhD Quant Research Internship"})
    assert not is_relevant_posting({"title": "2027 New Grad Analyst Program"})
    assert not is_relevant_posting({"title": "2027 Software Engineering Internship"})
    assert is_relevant_posting({"title": "2027 Sophomore Summer Analyst Program"})
