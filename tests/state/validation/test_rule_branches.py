"""M1.6 branch tests — no-violation and alternate paths (full coverage of rules)."""

from __future__ import annotations

from typing import Any

from state.enums import LifecycleStatus
from state.ledgers import Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.enums import (
    ChallengeVerdict,
    GapStatus,
    GateResult,
    RecommendationStatus,
)
from state.sections.governance import ChallengeNotes
from state.sections.lifecycle import QualityGate
from state.sections.output import ConfidenceReport, Recommendations
from state.sections.scoping import Gap
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


def test_ref_002_unknown_finding_assumption_ref() -> None:
    block = AnalysisBlock(findings=[Finding(question="q", assumption_refs=["ghost"])])
    assert "REF-002" in _ids(_state(financial_analysis=block))


def test_struct_003_assumed_gap_without_assumption_ref() -> None:
    gap = Gap(question="q", status=GapStatus.ASSUMED)
    assert "STRUCT-003" in _ids(_state(information_gaps=[gap]))
