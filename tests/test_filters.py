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


def test_undated_internship_at_target_firm_is_kept() -> None:
    # Recall fix: cycle is a boost, not a hard gate — an undated "Summer Analyst"
    # at an allowlisted firm must NOT be dropped for lacking a year token.
    assert is_relevant_posting({"title": "Summer Analyst, Investment Banking"})
    assert is_relevant_posting({"title": "Investment Banking Internship"})
    assert is_relevant_posting("Summer Associate Intern")


def test_description_words_do_not_cause_rejection() -> None:
    # Recall fix: reject words in the DESCRIPTION must not exclude a valid role.
    posting = {
        "title": "Investment Banking Summer Analyst Intern",
        "description": (
            "Collaborate with software engineers and designers; strong performers "
            "may receive a full-time offer. Design financial models."
        ),
    }
    assert is_relevant_posting(posting)


def test_in_scope_finance_title_survives_domain_reject_word() -> None:
    # "Financial Engineering" is a legit quant-finance role; the domain 'engineering'
    # reject is suppressed by the in-scope finance term.
    assert is_relevant_posting({"title": "Financial Engineering Summer Analyst Intern"})
    # ...but seniority still applies even with an in-scope term present.
    assert not is_relevant_posting({"title": "Senior Investment Banking Analyst"})


def test_out_of_scope_domain_without_finance_term_is_rejected() -> None:
    assert not is_relevant_posting({"title": "Product Design Intern"})
    assert not is_relevant_posting({"title": "Mechanical Engineering Summer Intern"})


def test_stale_cycle_year_is_rejected_but_current_is_kept() -> None:
    assert not is_relevant_posting({"title": "2024 Summer Analyst Internship"})
    assert not is_relevant_posting({"title": "Summer 2025 Investment Banking Intern"})
    # 2026/2027 and mixed years that include the target are kept (recall-favoring).
    assert is_relevant_posting({"title": "Summer 2026 Investment Banking Intern"})
    assert is_relevant_posting({"title": "2026 & 2027 Summer Analyst Intern"})
