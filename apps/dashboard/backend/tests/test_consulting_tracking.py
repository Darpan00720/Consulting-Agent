"""Tests for hypothesis / assumption / evidence / recommendation / decision
tracking — including the hard "no unsupported findings" invariants."""

from __future__ import annotations

import pytest

from app.consulting import tracking
from app.consulting.errors import (
    MissingEvidenceError,
    UnknownAssumptionError,
    UnknownEvidenceError,
    UnknownHypothesisError,
)
from app.consulting.models import (
    AssumptionStatus,
    ConsultingStage,
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
    HypothesisStatus,
)
from app.consulting.state import EngagementState, EngagementStatus


def _state() -> EngagementState:
    return EngagementState(
        engagement_id="e1",
        workflow_id="workflow.business_case",
        workflow_version="1.0.0",
        category=EngagementCategory.BUSINESS_CASE,
        status=EngagementStatus.IN_PROGRESS,
        current_stage=ConsultingStage.PROBLEM_DEFINITION,
    )


# ---- Hypothesis lifecycle ---------------------------------------------------


def test_create_hypothesis():
    state = _state()
    h = tracking.create_hypothesis(
        state, "Price elasticity is low", 0.6, "prior launches"
    )
    assert h.id in state.hypotheses
    assert h.status is HypothesisStatus.OPEN


def test_revise_hypothesis_keeps_prior_version_traceable():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    revised = tracking.revise_hypothesis(
        state, h.id, statement="Statement B", confidence=0.7, note="new data"
    )
    assert revised.statement == "Statement B"
    assert revised.status is HypothesisStatus.REVISED
    assert len(revised.revisions) == 1
    assert revised.revisions[0].statement == "Statement A"
    assert revised.revisions[0].confidence == 0.5


def test_confirm_hypothesis_requires_evidence():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    with pytest.raises(MissingEvidenceError):
        tracking.confirm_hypothesis(state, h.id, ())


def test_confirm_hypothesis_rejects_unknown_evidence_id():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    with pytest.raises(UnknownEvidenceError):
        tracking.confirm_hypothesis(state, h.id, ("ev-ghost",))


def test_confirm_hypothesis_with_real_evidence():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    ev = tracking.add_evidence(
        state, "source", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
    )
    confirmed = tracking.confirm_hypothesis(state, h.id, (ev.id,))
    assert confirmed.status is HypothesisStatus.CONFIRMED
    assert ev.id in confirmed.evidence_ids


def test_reject_hypothesis_requires_evidence():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    with pytest.raises(MissingEvidenceError):
        tracking.reject_hypothesis(state, h.id, ())


def test_unknown_hypothesis_id_raises():
    state = _state()
    with pytest.raises(UnknownHypothesisError):
        tracking.revise_hypothesis(state, "hyp-ghost", statement="x")


def test_update_hypothesis_confidence():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    updated = tracking.update_hypothesis_confidence(state, h.id, 0.9)
    assert updated.confidence == 0.9


# ---- Assumption registry ----------------------------------------------------


def test_create_and_validate_assumption():
    state = _state()
    asm = tracking.create_assumption(
        state, "Market grows 5%/yr", "analyst", "industry report", 0.6
    )
    assert asm.validation_status is AssumptionStatus.UNVALIDATED
    validated = tracking.validate_assumption(state, asm.id, validated=True)
    assert validated.validation_status is AssumptionStatus.VALIDATED
    assert validated.date_validated is not None


def test_invalidate_assumption():
    state = _state()
    asm = tracking.create_assumption(state, "desc", "owner", "source", 0.5)
    updated = tracking.validate_assumption(state, asm.id, validated=False)
    assert updated.validation_status is AssumptionStatus.INVALIDATED


def test_unknown_assumption_raises():
    state = _state()
    with pytest.raises(UnknownAssumptionError):
        tracking.validate_assumption(state, "asm-ghost", validated=True)


# ---- Evidence model ----------------------------------------------------------


def test_add_evidence_links_back_to_hypothesis():
    state = _state()
    h = tracking.create_hypothesis(state, "Statement A", 0.5, "rationale")
    ev = tracking.add_evidence(
        state,
        "source",
        EvidenceSourceType.KNOWLEDGE_LIBRARY,
        EvidenceQuality.MEDIUM,
        0.5,
        related_hypothesis_ids=(h.id,),
    )
    assert ev.id in state.hypotheses[h.id].evidence_ids


def test_add_evidence_rejects_unknown_hypothesis():
    state = _state()
    with pytest.raises(UnknownHypothesisError):
        tracking.add_evidence(
            state,
            "source",
            EvidenceSourceType.KNOWLEDGE_LIBRARY,
            EvidenceQuality.MEDIUM,
            0.5,
            related_hypothesis_ids=("hyp-ghost",),
        )


# ---- Recommendations — "no recommendation without evidence" ----------------


def test_create_recommendation_requires_evidence():
    state = _state()
    with pytest.raises(MissingEvidenceError):
        tracking.create_recommendation(
            state, "Do X", (), "impact", ("risk",), ("tradeoff",), "low", 0.7
        )


def test_create_recommendation_rejects_unknown_evidence():
    state = _state()
    with pytest.raises(UnknownEvidenceError):
        tracking.create_recommendation(
            state, "Do X", ("ev-ghost",), "impact", ("risk",), ("tradeoff",), "low", 0.7
        )


def test_create_recommendation_links_back_to_evidence():
    state = _state()
    ev = tracking.add_evidence(
        state, "source", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
    )
    rec = tracking.create_recommendation(
        state, "Do X", (ev.id,), "impact", ("risk",), ("tradeoff",), "low", 0.7
    )
    assert rec.id in state.evidence[ev.id].related_recommendation_ids


# ---- Decision log -----------------------------------------------------------


def test_record_decision():
    state = _state()
    ev = tracking.add_evidence(
        state, "source", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
    )
    decision = tracking.record_decision(
        state,
        "Proceed with plan A",
        "highest NPV",
        ("plan B", "plan C"),
        (ev.id,),
        "CFO",
        0.8,
    )
    assert decision in state.decisions
    assert decision.decision_owner == "CFO"


def test_record_decision_rejects_unknown_evidence():
    state = _state()
    with pytest.raises(UnknownEvidenceError):
        tracking.record_decision(
            state, "Proceed", "reason", (), ("ev-ghost",), "CFO", 0.8
        )
