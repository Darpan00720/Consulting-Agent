"""Hypothesis / assumption / evidence / recommendation / decision mutators.

Every function here is the ONLY sanctioned way to add or change these records
on an ``EngagementState`` — keeping every invariant (evidence must exist
before a recommendation cites it, a hypothesis stays traceable across
revisions) enforced at one choke point rather than scattered across callers.
See ``errors.py`` for why ``MissingEvidenceError``/``UnknownEvidenceError``
are the one place this platform raises instead of reporting a result object.
"""

from __future__ import annotations

import dataclasses
import time

from app.consulting.errors import (
    MissingEvidenceError,
    UnknownAssumptionError,
    UnknownEvidenceError,
    UnknownHypothesisError,
)
from app.consulting.models import (
    Assumption,
    AssumptionStatus,
    Decision,
    Evidence,
    EvidenceQuality,
    EvidenceSourceType,
    Hypothesis,
    HypothesisRevision,
    HypothesisStatus,
    Recommendation,
    new_assumption_id,
    new_decision_id,
    new_evidence_id,
    new_hypothesis_id,
    new_recommendation_id,
)
from app.consulting.state import EngagementState

# ---- Hypothesis management (requester's "Hypothesis Management" section) --


def create_hypothesis(
    state: EngagementState, statement: str, confidence: float, rationale: str
) -> Hypothesis:
    hyp = Hypothesis(
        id=new_hypothesis_id(),
        statement=statement,
        confidence=confidence,
        rationale=rationale,
    )
    state.hypotheses[hyp.id] = hyp
    return hyp


def _get_hypothesis(state: EngagementState, hypothesis_id: str) -> Hypothesis:
    if hypothesis_id not in state.hypotheses:
        raise UnknownHypothesisError(
            f"no hypothesis {hypothesis_id!r} in this engagement"
        )
    return state.hypotheses[hypothesis_id]


def revise_hypothesis(
    state: EngagementState,
    hypothesis_id: str,
    *,
    statement: str | None = None,
    confidence: float | None = None,
    note: str = "",
) -> Hypothesis:
    """Every hypothesis remains traceable: the PRIOR statement/confidence is
    pushed onto ``revisions`` before the new value replaces it."""
    current = _get_hypothesis(state, hypothesis_id)
    prior = HypothesisRevision(
        statement=current.statement, confidence=current.confidence, note=note
    )
    updated = dataclasses.replace(
        current,
        statement=statement if statement is not None else current.statement,
        confidence=confidence if confidence is not None else current.confidence,
        status=HypothesisStatus.REVISED,
        revisions=(*current.revisions, prior),
    )
    state.hypotheses[hypothesis_id] = updated
    return updated


def _resolve_hypothesis(
    state: EngagementState,
    hypothesis_id: str,
    status: HypothesisStatus,
    evidence_ids: tuple[str, ...],
) -> Hypothesis:
    current = _get_hypothesis(state, hypothesis_id)
    if not evidence_ids:
        raise MissingEvidenceError(
            f"cannot {status.value} hypothesis {hypothesis_id!r} "
            "without supporting evidence"
        )
    missing = set(evidence_ids) - set(state.evidence.keys())
    if missing:
        raise UnknownEvidenceError(
            f"evidence ids not found in this engagement: {sorted(missing)}"
        )
    updated = dataclasses.replace(
        current, status=status, evidence_ids=(*current.evidence_ids, *evidence_ids)
    )
    state.hypotheses[hypothesis_id] = updated
    return updated


def confirm_hypothesis(
    state: EngagementState, hypothesis_id: str, evidence_ids: tuple[str, ...]
) -> Hypothesis:
    return _resolve_hypothesis(
        state, hypothesis_id, HypothesisStatus.CONFIRMED, evidence_ids
    )


def reject_hypothesis(
    state: EngagementState, hypothesis_id: str, evidence_ids: tuple[str, ...]
) -> Hypothesis:
    return _resolve_hypothesis(
        state, hypothesis_id, HypothesisStatus.REJECTED, evidence_ids
    )


def update_hypothesis_confidence(
    state: EngagementState, hypothesis_id: str, confidence: float
) -> Hypothesis:
    current = _get_hypothesis(state, hypothesis_id)
    updated = dataclasses.replace(current, confidence=confidence)
    state.hypotheses[hypothesis_id] = updated
    return updated


# ---- Assumption registry (requester's "Assumption Registry" section) ------


def create_assumption(
    state: EngagementState, description: str, owner: str, source: str, confidence: float
) -> Assumption:
    asm = Assumption(
        id=new_assumption_id(),
        description=description,
        owner=owner,
        source=source,
        confidence=confidence,
    )
    state.assumptions[asm.id] = asm
    return asm


def validate_assumption(
    state: EngagementState,
    assumption_id: str,
    *,
    validated: bool,
    related_analyses: tuple[str, ...] = (),
) -> Assumption:
    """Assumptions "evolve throughout the engagement" — this transitions
    UNVALIDATED -> VALIDATED/INVALIDATED and stamps ``date_validated``."""
    if assumption_id not in state.assumptions:
        raise UnknownAssumptionError(
            f"no assumption {assumption_id!r} in this engagement"
        )
    current = state.assumptions[assumption_id]
    updated = dataclasses.replace(
        current,
        validation_status=AssumptionStatus.VALIDATED
        if validated
        else AssumptionStatus.INVALIDATED,
        date_validated=time.time(),
        related_analyses=related_analyses or current.related_analyses,
    )
    state.assumptions[assumption_id] = updated
    return updated


# ---- Evidence model (requester's "Evidence Model" section) ----------------


def add_evidence(
    state: EngagementState,
    source: str,
    source_type: EvidenceSourceType,
    quality: EvidenceQuality,
    confidence: float,
    content: str = "",
    *,
    related_hypothesis_ids: tuple[str, ...] = (),
    related_recommendation_ids: tuple[str, ...] = (),
) -> Evidence:
    missing_hyps = set(related_hypothesis_ids) - set(state.hypotheses.keys())
    if missing_hyps:
        raise UnknownHypothesisError(
            f"hypothesis ids not found: {sorted(missing_hyps)}"
        )
    ev = Evidence(
        id=new_evidence_id(),
        source=source,
        source_type=source_type,
        quality=quality,
        confidence=confidence,
        content=content,
        related_hypothesis_ids=related_hypothesis_ids,
        related_recommendation_ids=related_recommendation_ids,
    )
    state.evidence[ev.id] = ev
    for hid in related_hypothesis_ids:
        h = state.hypotheses[hid]
        state.hypotheses[hid] = dataclasses.replace(
            h, evidence_ids=(*h.evidence_ids, ev.id)
        )
    return ev


# ---- Recommendations (requester: "No recommendation ... without evidence") -


def create_recommendation(
    state: EngagementState,
    statement: str,
    supporting_evidence_ids: tuple[str, ...],
    expected_impact: str,
    risks: tuple[str, ...],
    tradeoffs: tuple[str, ...],
    implementation_effort: str,
    confidence: float,
) -> Recommendation:
    """Hard invariant, not a lint: refuses to construct a recommendation with
    no evidence, or evidence ids that don't exist in this engagement."""
    if not supporting_evidence_ids:
        raise MissingEvidenceError(
            "a recommendation must cite at least one evidence id"
        )
    missing = set(supporting_evidence_ids) - set(state.evidence.keys())
    if missing:
        raise UnknownEvidenceError(
            f"evidence ids not found in this engagement: {sorted(missing)}"
        )
    rec = Recommendation(
        id=new_recommendation_id(),
        statement=statement,
        supporting_evidence_ids=supporting_evidence_ids,
        expected_impact=expected_impact,
        risks=risks,
        tradeoffs=tradeoffs,
        implementation_effort=implementation_effort,
        confidence=confidence,
    )
    state.recommendations[rec.id] = rec
    for eid in supporting_evidence_ids:
        e = state.evidence[eid]
        state.evidence[eid] = dataclasses.replace(
            e, related_recommendation_ids=(*e.related_recommendation_ids, rec.id)
        )
    return rec


# ---- Decision log -----------------------------------------------------------


def record_decision(
    state: EngagementState,
    decision: str,
    reasoning: str,
    alternatives_considered: tuple[str, ...],
    supporting_evidence_ids: tuple[str, ...],
    decision_owner: str,
    confidence: float,
) -> Decision:
    missing = set(supporting_evidence_ids) - set(state.evidence.keys())
    if missing:
        raise UnknownEvidenceError(
            f"evidence ids not found in this engagement: {sorted(missing)}"
        )
    entry = Decision(
        id=new_decision_id(),
        decision=decision,
        reasoning=reasoning,
        alternatives_considered=alternatives_considered,
        supporting_evidence_ids=supporting_evidence_ids,
        decision_owner=decision_owner,
        confidence=confidence,
    )
    state.decisions.append(entry)
    return entry
