"""Tests for the analysis block contract validator (packages/analysis/contracts.py).

All tests are deterministic and filesystem-free.
"""

from __future__ import annotations

from analysis import (
    ANALYST_SECTION_OWNERS,
    ContractReport,
    FindingViolation,
    validate_analysis_block,
)
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.enums import AnalysisStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _block(
    findings: list[Finding] | None = None,
    status: AnalysisStatus = AnalysisStatus.COMPLETE,
    owner: str | None = "financial-analyst",
) -> AnalysisBlock:
    return AnalysisBlock(
        owner=owner,
        findings=findings or [],
        status=status,
    )


def _finding(
    question: str = "Is revenue declining?",
    answer: str | None = "Yes",
    evidence_refs: list[str] | None = None,
    assumption_refs: list[str] | None = None,
) -> Finding:
    return Finding(
        question=question,
        answer=answer,
        evidence_refs=evidence_refs or [],
        assumption_refs=assumption_refs or [],
    )


# ---------------------------------------------------------------------------
# Empty findings
# ---------------------------------------------------------------------------


def test_empty_findings_fails() -> None:
    report = validate_analysis_block(_block(findings=[]))
    assert not report.valid
    assert any(v.rule == "NO_FINDINGS" for v in report.violations)


# ---------------------------------------------------------------------------
# No owner on COMPLETE block
# ---------------------------------------------------------------------------


def test_complete_block_without_owner_fails() -> None:
    f = _finding(evidence_refs=["ev_001"])
    report = validate_analysis_block(_block(findings=[f], owner=None))
    assert not report.valid
    assert any(v.rule == "NO_OWNER" for v in report.violations)


def test_pending_block_without_owner_passes() -> None:
    f = _finding(evidence_refs=["ev_001"])
    report = validate_analysis_block(
        _block(findings=[f], status=AnalysisStatus.PENDING, owner=None)
    )
    # Only COMPLETE blocks require an owner
    assert not any(v.rule == "NO_OWNER" for v in report.violations)


# ---------------------------------------------------------------------------
# Evidence traceability
# ---------------------------------------------------------------------------


def test_answered_finding_with_evidence_passes() -> None:
    f = _finding(answer="Revenue fell 12%.", evidence_refs=["ev_001"])
    report = validate_analysis_block(_block(findings=[f]))
    assert report.valid, report.violations


def test_answered_finding_with_assumption_only_passes() -> None:
    f = _finding(answer="Revenue fell 12%.", assumption_refs=["assum_001"])
    report = validate_analysis_block(_block(findings=[f]))
    assert report.valid, report.violations


def test_answered_finding_no_refs_fails() -> None:
    f = _finding(answer="Revenue fell 12%.", evidence_refs=[], assumption_refs=[])
    report = validate_analysis_block(_block(findings=[f]))
    assert not report.valid
    assert any(v.rule == "UNEVIDENCED_ANSWER" for v in report.violations)


def test_unanswered_finding_no_refs_is_ok_in_pending() -> None:
    f = _finding(answer=None, evidence_refs=[])
    report = validate_analysis_block(
        _block(findings=[f], status=AnalysisStatus.PENDING)
    )
    assert not any(v.rule == "UNEVIDENCED_ANSWER" for v in report.violations)


# ---------------------------------------------------------------------------
# COMPLETE block must have all findings answered
# ---------------------------------------------------------------------------


def test_complete_block_with_unanswered_finding_fails() -> None:
    f = _finding(answer=None, evidence_refs=[])
    report = validate_analysis_block(_block(findings=[f]))
    assert not report.valid
    assert any(v.rule == "UNANSWERED_FINDING" for v in report.violations)


def test_complete_block_all_answered_passes() -> None:
    f = _finding(answer="Yes.", evidence_refs=["ev_001"])
    report = validate_analysis_block(_block(findings=[f]))
    assert report.valid, report.violations


# ---------------------------------------------------------------------------
# Multiple findings — violations accumulate
# ---------------------------------------------------------------------------


def test_multiple_violations_reported() -> None:
    f1 = _finding(question="Q1?", answer="A1")  # unevidenced
    f2 = _finding(question="Q2?", answer=None)  # unanswered in COMPLETE block
    report = validate_analysis_block(_block(findings=[f1, f2]))
    rules = {v.rule for v in report.violations}
    assert "UNEVIDENCED_ANSWER" in rules
    assert "UNANSWERED_FINDING" in rules


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_report_type() -> None:
    f = _finding(evidence_refs=["ev_001"])
    report = validate_analysis_block(_block(findings=[f]))
    assert isinstance(report, ContractReport)
    assert isinstance(report.valid, bool)
    assert isinstance(report.violations, tuple)


def test_violation_type() -> None:
    f = _finding(answer="Yes.", evidence_refs=[])  # unevidenced
    report = validate_analysis_block(_block(findings=[f]))
    for v in report.violations:
        assert isinstance(v, FindingViolation)
        assert isinstance(v.rule, str)
        assert isinstance(v.detail, str)
        assert isinstance(v.finding_index, int)


# ---------------------------------------------------------------------------
# ANALYST_SECTION_OWNERS
# ---------------------------------------------------------------------------


def test_analyst_section_owners_has_five_entries() -> None:
    assert len(ANALYST_SECTION_OWNERS) == 5


def test_analyst_section_owners_keys() -> None:
    expected = {
        "financial_analysis",
        "market_analysis",
        "operations_analysis",
        "strategy_analysis",
        "risk_analysis",
    }
    assert set(ANALYST_SECTION_OWNERS) == expected


def test_analyst_section_owners_values_are_agent_names() -> None:
    for _section, agent in ANALYST_SECTION_OWNERS.items():
        assert "-" in agent, f"{agent!r} is not a kebab-case agent name"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_block_same_result() -> None:
    f = _finding(answer="Yes.", evidence_refs=["ev_001"])
    block = _block(findings=[f])
    r1 = validate_analysis_block(block)
    r2 = validate_analysis_block(block)
    assert r1.valid == r2.valid
    assert r1.violations == r2.violations
