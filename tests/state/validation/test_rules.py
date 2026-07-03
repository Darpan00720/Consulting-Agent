"""M1.6 per-rule tests: one negative test per rule (slug-named for traceability)."""

from __future__ import annotations

from typing import Any

from state.enums import LifecycleStatus
from state.ledgers import Assumption, AssumptionStatus, Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.enums import (
    GapStatus,
    GateResult,
    RecommendationStatus,
    ReviewVerdict,
)
from state.sections.governance import ReviewerNotes
from state.sections.lifecycle import PhaseRecord, QualityGate
from state.sections.output import ConfidenceReport, Recommendations
from state.sections.planning import IssueNode
from state.sections.scoping import Gap
from state.validation import validate


def _state(**kwargs: Any) -> EngagementState:
    meta = EngagementMetadata(engagement_id="e", tenant_id="t", slug="s")
    return EngagementState(metadata=meta, **kwargs)


def _ids(state: EngagementState) -> set[str]:
    return {v.rule_id for v in validate(state).violations}


def test_valid_bare_state_has_no_violations() -> None:
    report = validate(_state())
    assert report.valid
    assert report.violations == []


# --- structural -------------------------------------------------------------


def test_struct_001_leaf_without_owner() -> None:
    assert "STRUCT-001" in _ids(_state(issue_tree=[IssueNode(question="q")]))


def test_struct_002_finding_without_evidence() -> None:
    block = AnalysisBlock(findings=[Finding(question="q")])
    assert "STRUCT-002" in _ids(_state(financial_analysis=block))


def test_struct_003_answered_gap_without_resolution() -> None:
    gap = Gap(question="q", status=GapStatus.ANSWERED)
    assert "STRUCT-003" in _ids(_state(information_gaps=[gap]))


# --- lifecycle --------------------------------------------------------------


def test_life_001_reporting_without_gates() -> None:
    assert "LIFE-001" in _ids(_state(status=LifecycleStatus.REPORTING))


def test_life_002_completed_without_outputs() -> None:
    assert "LIFE-002" in _ids(_state(status=LifecycleStatus.COMPLETED))


def test_life_003_illegal_transition() -> None:
    history = [
        PhaseRecord(phase=LifecycleStatus.INTAKE),
        PhaseRecord(phase=LifecycleStatus.REPORTING),
    ]
    state = _state(status=LifecycleStatus.REPORTING, phase_history=history)
    assert "LIFE-003" in _ids(state)


def test_life_004_status_does_not_match_history() -> None:
    history = [PhaseRecord(phase=LifecycleStatus.ANALYSIS)]
    assert "LIFE-004" in _ids(
        _state(status=LifecycleStatus.INTAKE, phase_history=history)
    )


def test_life_005_planning_preconditions_missing() -> None:
    ids = _ids(_state(status=LifecycleStatus.PLANNING))
    assert "LIFE-005" in ids


def test_life_006_analysis_preconditions_missing() -> None:
    ids = _ids(_state(status=LifecycleStatus.ANALYSIS))
    assert "LIFE-006" in ids


def test_life_007_unanswered_leaf_blocks_review() -> None:
    node = IssueNode(question="q", owner="o")  # status defaults to OPEN
    ids = _ids(_state(status=LifecycleStatus.REVIEW, issue_tree=[node]))
    assert "LIFE-007" in ids


def test_life_008_challenge_requires_reviewer_approval() -> None:
    ids = _ids(_state(status=LifecycleStatus.CHALLENGE))
    assert "LIFE-008" in ids


# --- referential ------------------------------------------------------------


def test_ref_001_unknown_gap_assumption_ref() -> None:
    gap = Gap(question="q", assumption_ref="ghost")
    assert "REF-001" in _ids(_state(information_gaps=[gap]))


def test_ref_002_unknown_finding_evidence_ref() -> None:
    block = AnalysisBlock(findings=[Finding(question="q", evidence_refs=["ghost"])])
    assert "REF-002" in _ids(_state(financial_analysis=block))


def test_ref_003_unknown_node_parent() -> None:
    node = IssueNode(question="q", owner="x", parent="ghost")
    assert "REF-003" in _ids(_state(issue_tree=[node]))


def test_ref_004_unknown_node_evidence_ref() -> None:
    node = IssueNode(question="q", owner="x", evidence_refs=["ghost"])
    assert "REF-004" in _ids(_state(issue_tree=[node]))


# --- business ---------------------------------------------------------------


def test_biz_001_confidence_exceeds_evidence() -> None:
    ev = Evidence(
        claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5, validated=True
    )
    state = _state(
        recommendations=Recommendations(decision="d"),
        confidence=ConfidenceReport(overall=0.9),
        evidence=[ev],
    )
    assert "BIZ-001" in _ids(state)


def test_biz_002_recommendation_without_validated_evidence() -> None:
    assert "BIZ-002" in _ids(_state(recommendations=Recommendations(decision="d")))


def test_biz_003_rests_on_invalidated_assumption() -> None:
    a = Assumption(
        statement="s",
        value="v",
        rationale="r",
        owner="o",
        confidence=0.5,
        status=AssumptionStatus.INVALIDATED,
    )
    ev = Evidence(
        claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5, validated=True
    )
    block = AnalysisBlock(
        findings=[Finding(question="q", evidence_refs=[ev.id], assumption_refs=[a.id])]
    )
    state = _state(
        recommendations=Recommendations(decision="d"),
        evidence=[ev],
        assumptions=[a],
        financial_analysis=block,
    )
    assert "BIZ-003" in _ids(state)


# --- governance -------------------------------------------------------------


def test_gov_001_acceptance_without_gates() -> None:
    rec = Recommendations(decision="d", status=RecommendationStatus.ACCEPTED)
    assert "GOV-001" in _ids(_state(recommendations=rec))


def test_gov_002_rework_without_actionable_fix() -> None:
    notes = ReviewerNotes(verdict=ReviewVerdict.NEEDS_REWORK)
    assert "GOV-002" in _ids(_state(reviewer_notes=notes))


def test_gov_003_failed_gate_without_rework() -> None:
    gate = QualityGate(gate="reviewer", result=GateResult.FAIL)
    assert "GOV-003" in _ids(_state(quality_gates=[gate]))
