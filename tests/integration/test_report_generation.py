"""Integration tests: report generation from EngagementState (M7).

Verifies that ``render_report`` produces deterministic, well-structured Markdown
with all required sections, evidence citations, and assumption labels.
"""

from __future__ import annotations

import pytest

from reporting import render_report
from state.identifiers import EngagementId
from state.models import EngagementMetadata, EngagementState
from tests.fixtures.golden_state import make_golden_profitability_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_state() -> EngagementState:
    return EngagementState(
        metadata=EngagementMetadata(
            engagement_id=EngagementId("eng_report_test"),
            tenant_id="t_report",
            slug="report-test",
        )
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_state_same_report() -> None:
    state = make_golden_profitability_state()
    r1 = render_report(state)
    r2 = render_report(state)
    assert r1 == r2


def test_minimal_state_deterministic() -> None:
    state = _minimal_state()
    assert render_report(state) == render_report(state)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_render_returns_string() -> None:
    assert isinstance(render_report(make_golden_profitability_state()), str)


def test_render_non_empty() -> None:
    result = render_report(make_golden_profitability_state())
    assert len(result) > 100


# ---------------------------------------------------------------------------
# Required section headers present
# ---------------------------------------------------------------------------

_REQUIRED_HEADERS = [
    "# Consulting Report:",
    "## Executive Summary",
    "## Situation Assessment",
    "## Framework & Analytical Approach",
    "## Issue Tree",
    "## Analysis",
    "## Recommendation",
    "## Risks & What Would Change the Answer",
    "## Implementation Roadmap",
    "## Appendix A: Assumptions Ledger",
    "## Appendix B: Evidence References",
    "## Appendix C: Confidence Scores",
    "## Appendix D: Knowledge References",
]


@pytest.mark.parametrize("header", _REQUIRED_HEADERS)
def test_required_section_present(header: str) -> None:
    report = render_report(make_golden_profitability_state())
    assert header in report, f"Missing section: {header!r}"


# ---------------------------------------------------------------------------
# Engagement metadata in header
# ---------------------------------------------------------------------------


def test_header_contains_engagement_id() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    assert state.metadata.engagement_id in report


def test_header_contains_slug() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    assert state.metadata.slug in report


def test_header_contains_archetype() -> None:
    report = render_report(make_golden_profitability_state())
    assert "Profitability" in report


# ---------------------------------------------------------------------------
# Evidence citations in report body
# ---------------------------------------------------------------------------


def test_evidence_appendix_contains_ev_ids() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    for ev in state.evidence:
        assert ev.id[:8] in report, f"Evidence `{ev.id[:8]}` missing from report"


def test_assumption_ids_in_appendix() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    for a in state.assumptions:
        assert a.id[:8] in report, f"Assumption `{a.id[:8]}` missing from appendix"


def test_assumption_has_breakeven_in_appendix() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    # The golden state has one load-bearing assumption with a breakeven
    assum = state.assumptions[0]
    assert assum.breakeven is not None
    # Breakeven text appears in the assumption row (truncated to 40 chars)
    truncated = assum.breakeven[:40]
    assert truncated in report


# ---------------------------------------------------------------------------
# Assumption labeling in analysis section
# ---------------------------------------------------------------------------


def test_assumption_only_finding_labeled() -> None:
    report = render_report(make_golden_profitability_state())
    # The financial block has one finding that uses only assumption_refs
    assert "[ASSUMPTION:" in report


def test_assumption_label_not_on_evidenced_finding() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    # The revenue decline finding is evidence-backed; its answer should NOT be labeled
    assert "Revenue fell 12% YoY" in report
    # Find the line with this text
    for line in report.splitlines():
        if "Revenue fell 12% YoY" in line:
            assert (
                "[ASSUMPTION:" not in line
            ), "Evidence-backed finding should not carry [ASSUMPTION:] label"


# ---------------------------------------------------------------------------
# Recommendation section
# ---------------------------------------------------------------------------


def test_recommendation_decision_present() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    assert state.recommendations is not None
    assert state.recommendations.decision is not None
    assert "pricing recovery" in report.lower() or "price" in report.lower()


def test_next_steps_in_report() -> None:
    report = render_report(make_golden_profitability_state())
    assert "Re-price" in report


def test_rejected_alternatives_in_report() -> None:
    report = render_report(make_golden_profitability_state())
    assert "headcount" in report.lower()


# ---------------------------------------------------------------------------
# Challenger / risks section
# ---------------------------------------------------------------------------


def test_challenger_verdict_in_report() -> None:
    report = render_report(make_golden_profitability_state())
    assert "stands_with_caveats" in report


def test_what_would_change_items_in_report() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    assert state.challenge_notes is not None
    for item in state.challenge_notes.what_would_change:
        assert item in report, f"what_would_change item missing: {item!r}"


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def test_footer_contains_gate_verdicts() -> None:
    report = render_report(make_golden_profitability_state())
    assert "approved" in report
    assert "stands_with_caveats" in report
    assert "StratAgent RC1" in report


def test_footer_contains_generated_timestamp() -> None:
    report = render_report(make_golden_profitability_state())
    # ISO timestamp pattern: YYYY-MM-DDTHH:MM:SSZ
    import re

    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", report)


# ---------------------------------------------------------------------------
# Minimal state — graceful empty-section handling
# ---------------------------------------------------------------------------


def test_minimal_state_no_frameworks_omits_section() -> None:
    report = render_report(_minimal_state())
    assert "## Framework" not in report


def test_minimal_state_no_issue_tree_omits_section() -> None:
    report = render_report(_minimal_state())
    assert "## Issue Tree" not in report


def test_minimal_state_recommendation_pending() -> None:
    report = render_report(_minimal_state())
    assert "pending" in report.lower()


def test_minimal_state_still_has_header_and_footer() -> None:
    report = render_report(_minimal_state())
    assert "# Consulting Report:" in report
    assert "StratAgent RC1" in report


# ---------------------------------------------------------------------------
# Issue tree rendering
# ---------------------------------------------------------------------------


def test_issue_tree_shows_root_question() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    root = next(n for n in state.issue_tree if n.parent is None)
    assert root.question in report


def test_issue_tree_leaf_shows_owner() -> None:
    report = render_report(make_golden_profitability_state())
    assert "financial-analyst" in report


def test_issue_tree_answered_node_has_checkmark() -> None:
    report = render_report(make_golden_profitability_state())
    assert "✓" in report


# ---------------------------------------------------------------------------
# Confidence appendix
# ---------------------------------------------------------------------------


def test_confidence_appendix_shows_overall() -> None:
    report = render_report(make_golden_profitability_state())
    assert "**Overall:**" in report
    assert "82%" in report


def test_confidence_appendix_by_section() -> None:
    report = render_report(make_golden_profitability_state())
    assert "financial_analysis" in report
    assert "market_analysis" in report


# ---------------------------------------------------------------------------
# Section separator
# ---------------------------------------------------------------------------


def test_sections_separated_by_hr() -> None:
    report = render_report(make_golden_profitability_state())
    assert "\n\n---\n\n" in report
