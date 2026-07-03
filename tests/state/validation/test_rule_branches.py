"""M1.6 branch tests — no-violation and alternate paths (full coverage of rules)."""

from __future__ import annotations

from typing import Any

from state.enums import LifecycleStatus
from state.ledgers import Assumption, Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.enums import (
    CaseArchetype,
    ChallengeVerdict,
    GapCriticality,
    GapStatus,
    GateResult,
    IssueNodeStatus,
    RecommendationStatus,
    ReviewVerdict,
)
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.lifecycle import QualityGate
from state.sections.output import ConfidenceReport, Recommendations
from state.sections.planning import EngagementPlan, IssueNode
from state.sections.scoping import CaseClassification, Gap, ProblemDefinition
from state.validation import validate


def _state(**kwargs: Any) -> EngagementState:
    meta = EngagementMetadata(engagement_id="e", tenant_id="t", slug="s")
    return EngagementState(metadata=meta, **kwargs)


def _ids(state: EngagementState) -> set[str]:
    return {v.rule_id for v in validate(state).violations}


def _validated(conf: float = 0.5) -> Evidence:
    return Evidence(
        claim="c", type=EvidenceType.CLIENT_FACT, confidence=conf, validated=True
    )


def _pass_gates() -> list[QualityGate]:
    return [
        QualityGate(gate="reviewer", result=GateResult.PASS),
        QualityGate(gate="challenger", result=GateResult.PASS),
    ]


def test_biz_001_skipped_without_validated_evidence() -> None:
    state = _state(
        recommendations=Recommendations(decision="d"),
        confidence=ConfidenceReport(overall=0.9),
    )
    assert "BIZ-001" not in _ids(state)


def test_biz_001_within_bound_is_ok() -> None:
    state = _state(
        recommendations=Recommendations(decision="d"),
        confidence=ConfidenceReport(overall=0.4),
        evidence=[_validated(0.5)],
    )
    assert "BIZ-001" not in _ids(state)


def test_gov_001_ok_when_gates_passed() -> None:
    rec = Recommendations(decision="d", status=RecommendationStatus.ACCEPTED)
    assert "GOV-001" not in _ids(
        _state(recommendations=rec, quality_gates=_pass_gates())
    )


def test_gov_002_challenge_rework_without_counter_case() -> None:
    notes = ChallengeNotes(verdict=ChallengeVerdict.NEEDS_REWORK)
    assert "GOV-002" in _ids(_state(challenge_notes=notes))


def test_gov_003_ok_for_passing_gate() -> None:
    gate = QualityGate(gate="reviewer", result=GateResult.PASS)
    assert "GOV-003" not in _ids(_state(quality_gates=[gate]))


def test_gov_003_challenger_fail_without_rework() -> None:
    gate = QualityGate(gate="challenger", result=GateResult.FAIL)
    assert "GOV-003" in _ids(_state(quality_gates=[gate]))


def test_life_001_ok_when_gates_passed() -> None:
    state = _state(status=LifecycleStatus.REPORTING, quality_gates=_pass_gates())
    assert "LIFE-001" not in _ids(state)


def test_life_005_fires_at_or_beyond_planning() -> None:
    # missing planning preconditions still violate at a LATER phase
    assert "LIFE-005" in _ids(_state(status=LifecycleStatus.ANALYSIS))
    # and a load-bearing open gap is named even when the rest is satisfied
    open_gap = Gap(question="q", criticality=GapCriticality.LOAD_BEARING)
    state = _state(
        status=LifecycleStatus.PLANNING,
        classification=CaseClassification(
            primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8
        ),
        problem=ProblemDefinition(raw_input="r", real_question="why?"),
        information_gaps=[open_gap, Gap(question="minor")],
    )
    report = validate(state)
    life_005 = [v for v in report.violations if v.rule_id == "LIFE-005"]
    assert len(life_005) == 1
    assert life_005[0].object_id == open_gap.id


def test_life_005_006_satisfied_states_pass() -> None:
    answered_leaf = IssueNode(question="q", owner="o", status=IssueNodeStatus.ANSWERED)
    assumption = Assumption(
        statement="s", value="v", rationale="r", owner="o", confidence=0.5
    )
    state = _state(
        status=LifecycleStatus.ANALYSIS,
        classification=CaseClassification(
            primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8
        ),
        problem=ProblemDefinition(raw_input="r", real_question="why?"),
        information_gaps=[
            Gap(
                question="g",
                criticality=GapCriticality.LOAD_BEARING,
                status=GapStatus.ASSUMED,
                assumption_ref=assumption.id,
            )
        ],
        assumptions=[assumption],
        plan=EngagementPlan(),
        issue_tree=[answered_leaf],
    )
    ids = _ids(state)
    assert "LIFE-005" not in ids
    assert "LIFE-006" not in ids


def test_life_007_non_leaf_and_answered_leaf_ok() -> None:
    parent = IssueNode(question="root", owner="o")  # OPEN, but not a leaf
    child = IssueNode(
        question="leaf", owner="o", parent=parent.id, status=IssueNodeStatus.ANSWERED
    )
    ids = _ids(_state(status=LifecycleStatus.REVIEW, issue_tree=[parent, child]))
    assert "LIFE-007" not in ids


def test_life_008_ok_when_reviewer_approved() -> None:
    notes = ReviewerNotes(verdict=ReviewVerdict.APPROVED)
    ids = _ids(_state(status=LifecycleStatus.CHALLENGE, reviewer_notes=notes))
    assert "LIFE-008" not in ids


def test_life_preconditions_exempt_when_ended() -> None:
    for status in (
        LifecycleStatus.COMPLETED,
        LifecycleStatus.FAILED,
        LifecycleStatus.ABORTED,
    ):
        ids = _ids(_state(status=status))
        for rule in ("LIFE-005", "LIFE-006", "LIFE-007", "LIFE-008"):
            assert rule not in ids, f"{rule} must not fire for {status}"


def test_ref_002_unknown_finding_assumption_ref() -> None:
    block = AnalysisBlock(findings=[Finding(question="q", assumption_refs=["ghost"])])
    assert "REF-002" in _ids(_state(financial_analysis=block))


def test_struct_003_assumed_gap_without_assumption_ref() -> None:
    gap = Gap(question="q", status=GapStatus.ASSUMED)
    assert "STRUCT-003" in _ids(_state(information_gaps=[gap]))
