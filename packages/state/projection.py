"""Projection — fold an ordered event log into an Engagement State (M1.5).

Contract (see docs/architecture/Event-Design-Principles.md §11):
- ``apply(state, event)`` is a **pure**, deterministic single-event reducer: it
  returns a new state and never mutates its input, performs no validation, and
  performs no IO.
- ``project(events)`` is the fold of ``apply`` over the log — replay is nothing more
  than this composition, not a separate algorithm. It always returns an
  ``EngagementState`` (empty log -> empty state).

Dispatch is modular: one registered reducer per event type (via
``functools.singledispatch``). Adding an event type means registering a reducer.
Internal module — not part of the public surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from functools import singledispatch
from typing import Any

from common.models import DomainObject
from state.enums import LifecycleStatus
from state.events import (
    AssumptionAdded,
    AssumptionInvalidated,
    AssumptionUpdated,
    CaseClassified,
    CaseReclassified,
    ChallengerCleared,
    ChallengeRecorded,
    ChallengerRejected,
    ConfidenceScored,
    ConstraintsRecorded,
    DeckGenerated,
    EngagementAborted,
    EngagementCompleted,
    EngagementCreated,
    EngagementFailed,
    EngagementPlanCreated,
    EngagementReplanned,
    Event,
    EvidenceAdded,
    EvidenceMarkedStale,
    EvidenceRejected,
    EvidenceValidated,
    FindingRecorded,
    FrameworkDeselected,
    FrameworkSelected,
    GapAnswered,
    GapAssumed,
    HumanInputProvided,
    HumanInputRequested,
    InformationGapIdentified,
    IssueTreeGenerated,
    IssueTreeNodeUpdated,
    KnowledgeGraphLinked,
    KnowledgeRetrieved,
    LessonCaptured,
    ModelGenerated,
    ObjectivesRecorded,
    PhaseTransitioned,
    ProblemDefined,
    ProblemUpdated,
    ProfileUpdated,
    RecommendationAccepted,
    RecommendationDrafted,
    ReportGenerated,
    ReviewerApproved,
    ReviewerRejected,
    ReviewerReviewed,
    SpecialistAnalysisCompleted,
    SpecialistAnalysisStarted,
    StakeholdersRecorded,
)
from state.identifiers import EngagementId, RecommendationId
from state.ledgers import AssumptionStatus
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock
from state.sections.enums import (
    AnalysisStatus,
    ChallengeVerdict,
    GapStatus,
    GateResult,
    PendingKind,
    RecommendationStatus,
    ReviewVerdict,
)
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.lifecycle import PendingRequirement, PhaseRecord, QualityGate
from state.sections.output import KnowledgeLink, Recommendations
from state.sections.scoping import ProblemDefinition

# v1: initial fold (M1.5). v2: apply() derives metadata.state_version from the
# event's seq (M1.7.2, design D4) — the same log now folds to a different state.
PROJECTION_VERSION = 2

# Fixed origin timestamp so projection stays deterministic for objects it builds.
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

_ANALYSIS_FIELDS = {
    "financial": "financial_analysis",
    "market": "market_analysis",
    "operations": "operations_analysis",
    "strategy": "strategy_analysis",
    "risk": "risk_analysis",
}


def _initial_state() -> EngagementState:
    """The empty projected state (before any event is applied)."""
    return EngagementState(
        metadata=EngagementMetadata(
            engagement_id=EngagementId(""),
            tenant_id="",
            slug="",
            created_at=_EPOCH,
            updated_at=_EPOCH,
        ),
        projection_version=PROJECTION_VERSION,
    )


def _replace[T: DomainObject](
    items: list[T], target_id: str, changes: dict[str, Any]
) -> list[T]:
    """Return a new list with the item whose id == target_id updated (pure)."""
    return [
        item.model_copy(update=changes) if item.id == target_id else item
        for item in items
    ]


@singledispatch
def _apply(event: object, state: EngagementState) -> EngagementState:
    """Default: unknown events leave the state unchanged (projection never fails)."""
    return state


def apply(state: EngagementState, event: Event) -> EngagementState:
    """Pure single-event reducer: (state, event) -> new state.

    Projection is the single authority for ``metadata.state_version``: it is
    derived solely from ``event.metadata.seq`` (projection v2, design D4). The
    stamp is unconditional, so no caller-assigned value survives an apply.
    """
    new_state = _apply(event, state)
    metadata = new_state.metadata.model_copy(
        update={"state_version": event.metadata.seq}
    )
    return new_state.model_copy(update={"metadata": metadata})


def project(events: Iterable[Event]) -> EngagementState:
    """Fold events into a state. Always returns a state (empty log -> empty state)."""
    state = _initial_state()
    for event in events:
        state = apply(state, event)
    return state


# --- intake -----------------------------------------------------------------


@_apply.register
def _ap_engagement_created(
    event: EngagementCreated, state: EngagementState
) -> EngagementState:
    metadata = EngagementMetadata(
        engagement_id=event.metadata.engagement_id,
        tenant_id=event.tenant_id,
        slug=event.slug,
        created_by=event.created_by,
        created_at=event.metadata.occurred_at,
        updated_at=event.metadata.occurred_at,
    )
    return state.model_copy(update={"metadata": metadata})


@_apply.register
def _ap_problem_defined(
    event: ProblemDefined, state: EngagementState
) -> EngagementState:
    problem = ProblemDefinition(
        id=event.metadata.event_id,
        raw_input=event.raw_input,
        real_question=event.real_question,
    )
    return state.model_copy(update={"problem": problem})


@_apply.register
def _ap_problem_updated(
    event: ProblemUpdated, state: EngagementState
) -> EngagementState:
    if state.problem is None:
        return state
    problem = state.problem.model_copy(
        update={
            "real_question": event.real_question,
            "restated_at": event.metadata.occurred_at,
        }
    )
    return state.model_copy(update={"problem": problem})


@_apply.register
def _ap_objectives_recorded(
    event: ObjectivesRecorded, state: EngagementState
) -> EngagementState:
    return state.model_copy(
        update={
            "objectives": event.objectives,
            "success_criteria": event.success_criteria,
        }
    )


@_apply.register
def _ap_constraints_recorded(
    event: ConstraintsRecorded, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"constraints": event.constraints})


@_apply.register
def _ap_stakeholders_recorded(
    event: StakeholdersRecorded, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"stakeholders": event.stakeholders})


# --- classification ---------------------------------------------------------


@_apply.register
def _ap_case_classified(
    event: CaseClassified, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"classification": event.classification})


@_apply.register
def _ap_case_reclassified(
    event: CaseReclassified, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"classification": event.classification})


@_apply.register
def _ap_information_gap_identified(
    event: InformationGapIdentified, state: EngagementState
) -> EngagementState:
    return state.model_copy(
        update={"information_gaps": [*state.information_gaps, event.gap]}
    )


@_apply.register
def _ap_gap_answered(event: GapAnswered, state: EngagementState) -> EngagementState:
    gaps = _replace(
        state.information_gaps,
        event.gap_id,
        {"status": GapStatus.ANSWERED, "resolution": event.resolution},
    )
    return state.model_copy(update={"information_gaps": gaps})


@_apply.register
def _ap_gap_assumed(event: GapAssumed, state: EngagementState) -> EngagementState:
    gaps = _replace(
        state.information_gaps,
        event.gap_id,
        {"status": GapStatus.ASSUMED, "assumption_ref": event.assumption_id},
    )
    return state.model_copy(update={"information_gaps": gaps})


# --- assumption -------------------------------------------------------------


@_apply.register
def _ap_assumption_added(
    event: AssumptionAdded, state: EngagementState
) -> EngagementState:
    return state.model_copy(
        update={"assumptions": [*state.assumptions, event.assumption]}
    )


@_apply.register
def _ap_assumption_updated(
    event: AssumptionUpdated, state: EngagementState
) -> EngagementState:
    assumptions = _replace(
        state.assumptions,
        event.assumption_id,
        {
            "statement": event.statement,
            "value": event.value,
            "rationale": event.rationale,
        },
    )
    return state.model_copy(update={"assumptions": assumptions})


@_apply.register
def _ap_assumption_invalidated(
    event: AssumptionInvalidated, state: EngagementState
) -> EngagementState:
    assumptions = _replace(
        state.assumptions, event.assumption_id, {"status": AssumptionStatus.INVALIDATED}
    )
    return state.model_copy(update={"assumptions": assumptions})


# --- planning ---------------------------------------------------------------


@_apply.register
def _ap_plan_created(
    event: EngagementPlanCreated, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"plan": event.plan})


@_apply.register
def _ap_replanned(
    event: EngagementReplanned, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"plan": event.plan})


@_apply.register
def _ap_framework_selected(
    event: FrameworkSelected, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"frameworks": [*state.frameworks, event.framework]})


@_apply.register
def _ap_framework_deselected(
    event: FrameworkDeselected, state: EngagementState
) -> EngagementState:
    frameworks = [f for f in state.frameworks if f.id != event.framework_id]
    return state.model_copy(update={"frameworks": frameworks})


@_apply.register
def _ap_issue_tree_generated(
    event: IssueTreeGenerated, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"issue_tree": event.nodes})


@_apply.register
def _ap_issue_tree_node_updated(
    event: IssueTreeNodeUpdated, state: EngagementState
) -> EngagementState:
    nodes = _replace(
        state.issue_tree,
        event.node_id,
        {"question": event.question, "status": event.status, "answer": event.answer},
    )
    return state.model_copy(update={"issue_tree": nodes})


# --- knowledge --------------------------------------------------------------


@_apply.register
def _ap_knowledge_retrieved(
    event: KnowledgeRetrieved, state: EngagementState
) -> EngagementState:
    return state.model_copy(
        update={
            "knowledge_references": [*state.knowledge_references, *event.references]
        }
    )


# --- evidence ---------------------------------------------------------------


@_apply.register
def _ap_evidence_added(event: EvidenceAdded, state: EngagementState) -> EngagementState:
    return state.model_copy(update={"evidence": [*state.evidence, event.evidence]})


@_apply.register
def _ap_evidence_validated(
    event: EvidenceValidated, state: EngagementState
) -> EngagementState:
    evidence = _replace(
        state.evidence,
        event.evidence_id,
        {"validated": True, "validator": event.validator},
    )
    return state.model_copy(update={"evidence": evidence})


@_apply.register
def _ap_evidence_rejected(
    event: EvidenceRejected, state: EngagementState
) -> EngagementState:
    evidence = _replace(state.evidence, event.evidence_id, {"validated": False})
    return state.model_copy(update={"evidence": evidence})


@_apply.register
def _ap_evidence_marked_stale(
    event: EvidenceMarkedStale, state: EngagementState
) -> EngagementState:
    # No dedicated staleness field; marking stale un-validates the evidence.
    evidence = _replace(state.evidence, event.evidence_id, {"validated": False})
    return state.model_copy(update={"evidence": evidence})


# --- analysis ---------------------------------------------------------------


@_apply.register
def _ap_analysis_started(
    event: SpecialistAnalysisStarted, state: EngagementState
) -> EngagementState:
    field = _ANALYSIS_FIELDS.get(event.analysis)
    if field is None:
        return state
    block = AnalysisBlock(
        id=event.metadata.event_id,
        owner=event.owner,
        node_refs=[str(ref) for ref in event.node_refs],
        status=AnalysisStatus.IN_PROGRESS,
    )
    return state.model_copy(update={field: block})


@_apply.register
def _ap_finding_recorded(
    event: FindingRecorded, state: EngagementState
) -> EngagementState:
    field = _ANALYSIS_FIELDS.get(event.analysis)
    if field is None:
        return state
    current: AnalysisBlock | None = getattr(state, field)
    if current is None:
        block = AnalysisBlock(id=event.metadata.event_id, findings=[event.finding])
    else:
        block = current.model_copy(
            update={"findings": [*current.findings, event.finding]}
        )
    return state.model_copy(update={field: block})


@_apply.register
def _ap_analysis_completed(
    event: SpecialistAnalysisCompleted, state: EngagementState
) -> EngagementState:
    field = _ANALYSIS_FIELDS.get(event.analysis)
    if field is None:
        return state
    current: AnalysisBlock | None = getattr(state, field)
    block = (current or AnalysisBlock(id=event.metadata.event_id)).model_copy(
        update={"status": event.status}
    )
    return state.model_copy(update={field: block})


# --- governance -------------------------------------------------------------


def _gate(event: Event, gate: str, result: GateResult) -> QualityGate:
    return QualityGate(
        id=event.metadata.event_id,
        gate=gate,
        result=result,
        by=event.metadata.actor,
        ts=event.metadata.occurred_at,
    )


@_apply.register
def _ap_reviewer_reviewed(
    event: ReviewerReviewed, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"reviewer_notes": event.notes})


@_apply.register
def _ap_reviewer_approved(
    event: ReviewerApproved, state: EngagementState
) -> EngagementState:
    gates = [*state.quality_gates, _gate(event, "reviewer", GateResult.PASS)]
    base = state.reviewer_notes or ReviewerNotes(id=event.metadata.event_id)
    notes = base.model_copy(update={"verdict": ReviewVerdict.APPROVED})
    return state.model_copy(update={"quality_gates": gates, "reviewer_notes": notes})


@_apply.register
def _ap_reviewer_rejected(
    event: ReviewerRejected, state: EngagementState
) -> EngagementState:
    gates = [*state.quality_gates, _gate(event, "reviewer", GateResult.FAIL)]
    base = state.reviewer_notes or ReviewerNotes(id=event.metadata.event_id)
    notes = base.model_copy(
        update={"verdict": ReviewVerdict.NEEDS_REWORK, "issues": event.issues}
    )
    return state.model_copy(update={"quality_gates": gates, "reviewer_notes": notes})


@_apply.register
def _ap_challenge_recorded(
    event: ChallengeRecorded, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"challenge_notes": event.notes})


@_apply.register
def _ap_challenger_cleared(
    event: ChallengerCleared, state: EngagementState
) -> EngagementState:
    gates = [*state.quality_gates, _gate(event, "challenger", GateResult.PASS)]
    base = state.challenge_notes or ChallengeNotes(id=event.metadata.event_id)
    notes = base.model_copy(
        update={"verdict": ChallengeVerdict.STANDS, "what_would_change": event.caveats}
    )
    return state.model_copy(update={"quality_gates": gates, "challenge_notes": notes})


@_apply.register
def _ap_challenger_rejected(
    event: ChallengerRejected, state: EngagementState
) -> EngagementState:
    gates = [*state.quality_gates, _gate(event, "challenger", GateResult.FAIL)]
    base = state.challenge_notes or ChallengeNotes(id=event.metadata.event_id)
    notes = base.model_copy(
        update={
            "verdict": ChallengeVerdict.NEEDS_REWORK,
            "counter_case": event.counter_case,
        }
    )
    return state.model_copy(update={"quality_gates": gates, "challenge_notes": notes})


# --- recommendation ---------------------------------------------------------


@_apply.register
def _ap_recommendation_drafted(
    event: RecommendationDrafted, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"recommendations": event.recommendation})


@_apply.register
def _ap_confidence_scored(
    event: ConfidenceScored, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"confidence": event.report})


@_apply.register
def _ap_recommendation_accepted(
    event: RecommendationAccepted, state: EngagementState
) -> EngagementState:
    current = state.recommendations or Recommendations(
        id=RecommendationId(event.metadata.event_id)
    )
    rec = current.model_copy(
        update={"decision": event.decision, "status": RecommendationStatus.ACCEPTED}
    )
    return state.model_copy(update={"recommendations": rec})


# --- delivery ---------------------------------------------------------------


@_apply.register
def _ap_report_generated(
    event: ReportGenerated, state: EngagementState
) -> EngagementState:
    return state.model_copy(
        update={"deliverables": [*state.deliverables, event.deliverable]}
    )


@_apply.register
def _ap_deck_generated(event: DeckGenerated, state: EngagementState) -> EngagementState:
    return state.model_copy(
        update={"deliverables": [*state.deliverables, event.deliverable]}
    )


@_apply.register
def _ap_model_generated(
    event: ModelGenerated, state: EngagementState
) -> EngagementState:
    return state.model_copy(
        update={"deliverables": [*state.deliverables, event.deliverable]}
    )


# --- hitl -------------------------------------------------------------------


@_apply.register
def _ap_human_input_requested(
    event: HumanInputRequested, state: EngagementState
) -> EngagementState:
    pending = PendingRequirement(
        id=event.metadata.event_id,
        kind=PendingKind.HUMAN_INPUT,
        description=event.prompt,
        ref=event.target,
    )
    return state.model_copy(
        update={"pending_requirements": [*state.pending_requirements, pending]}
    )


@_apply.register
def _ap_human_input_provided(
    event: HumanInputProvided, state: EngagementState
) -> EngagementState:
    remaining = [p for p in state.pending_requirements if p.description != event.prompt]
    return state.model_copy(update={"pending_requirements": remaining})


# --- lifecycle --------------------------------------------------------------


@_apply.register
def _ap_phase_transitioned(
    event: PhaseTransitioned, state: EngagementState
) -> EngagementState:
    record = PhaseRecord(
        id=event.metadata.event_id,
        phase=event.to_status,
        entered_at=event.metadata.occurred_at,
    )
    return state.model_copy(
        update={
            "status": event.to_status,
            "phase_history": [*state.phase_history, record],
        }
    )


@_apply.register
def _ap_engagement_completed(
    event: EngagementCompleted, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"status": LifecycleStatus.COMPLETED})


@_apply.register
def _ap_engagement_failed(
    event: EngagementFailed, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"status": LifecycleStatus.FAILED})


@_apply.register
def _ap_engagement_aborted(
    event: EngagementAborted, state: EngagementState
) -> EngagementState:
    return state.model_copy(update={"status": LifecycleStatus.ABORTED})


# --- curation (no projected-state effect; curated to the vault) -------------


@_apply.register
def _ap_lesson_captured(
    event: LessonCaptured, state: EngagementState
) -> EngagementState:
    return state


@_apply.register
def _ap_knowledge_graph_linked(
    event: KnowledgeGraphLinked, state: EngagementState
) -> EngagementState:
    link = KnowledgeLink(
        id=event.metadata.event_id,
        graph_node=event.graph_node,
        relationship=event.relationship,
    )
    return state.model_copy(update={"knowledge_links": [*state.knowledge_links, link]})


@_apply.register
def _ap_profile_updated(
    event: ProfileUpdated, state: EngagementState
) -> EngagementState:
    return state
