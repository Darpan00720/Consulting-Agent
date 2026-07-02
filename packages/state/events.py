"""The Engagement event catalog (ADR-002 §Event Model; see docs/api/Events.md).

Events are **facts** (past tense), **immutable** (frozen), **self-contained**
(understandable without reading current state), carry an explicit `schema_version`,
and reference domain objects by **strongly-typed ids**. Every event carries an
`EventMetadata` envelope and belongs to exactly one `EventCategory`. The full set is
a discriminated union (`Event`) keyed on `type`.

Out of scope here (later sub-milestones): applying events (projection, M1.5), `seq`
allocation + concurrency (M1.7), persistence (M1.8), replay (M1.9).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from core.base import StratAgentModel
from state.enums import LifecycleStatus
from state.identifiers import (
    AssumptionId,
    EngagementId,
    EventId,
    EvidenceId,
    FrameworkId,
    GapId,
    IssueNodeId,
    RecommendationId,
    new_event_id,
)
from state.ledgers import Assumption, Evidence
from state.sections.analysis import Finding
from state.sections.enums import AnalysisStatus, IssueNodeStatus
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.output import ConfidenceReport, Deliverable, Recommendations
from state.sections.planning import (
    EngagementPlan,
    FrameworkSelection,
    IssueNode,
    KnowledgeReference,
)
from state.sections.scoping import (
    CaseClassification,
    Constraint,
    Gap,
    Objective,
    Stakeholder,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EventSource(StrEnum):
    """How an event entered the system (distinct from *who* — the actor)."""

    CLI = "cli"
    API = "api"
    AGENT = "agent"
    SYSTEM = "system"
    IMPORT = "import"
    OTHER = "other"


class EventCategory(StrEnum):
    """The category an event belongs to (every event maps to exactly one)."""

    INTAKE = "intake"
    CLASSIFICATION = "classification"
    ASSUMPTION = "assumption"
    PLANNING = "planning"
    KNOWLEDGE = "knowledge"
    EVIDENCE = "evidence"
    ANALYSIS = "analysis"
    GOVERNANCE = "governance"
    RECOMMENDATION = "recommendation"
    DELIVERY = "delivery"
    HITL = "hitl"
    LIFECYCLE = "lifecycle"
    CURATION = "curation"


class EventType(StrEnum):
    """Canonical event type identifiers (past-tense facts)."""

    ENGAGEMENT_CREATED = "engagement_created"
    PROBLEM_DEFINED = "problem_defined"
    PROBLEM_UPDATED = "problem_updated"
    OBJECTIVES_RECORDED = "objectives_recorded"
    CONSTRAINTS_RECORDED = "constraints_recorded"
    STAKEHOLDERS_RECORDED = "stakeholders_recorded"
    CASE_CLASSIFIED = "case_classified"
    CASE_RECLASSIFIED = "case_reclassified"
    INFORMATION_GAP_IDENTIFIED = "information_gap_identified"
    GAP_ANSWERED = "gap_answered"
    GAP_ASSUMED = "gap_assumed"
    ASSUMPTION_ADDED = "assumption_added"
    ASSUMPTION_UPDATED = "assumption_updated"
    ASSUMPTION_INVALIDATED = "assumption_invalidated"
    ENGAGEMENT_PLAN_CREATED = "engagement_plan_created"
    ENGAGEMENT_REPLANNED = "engagement_replanned"
    FRAMEWORK_SELECTED = "framework_selected"
    FRAMEWORK_DESELECTED = "framework_deselected"
    ISSUE_TREE_GENERATED = "issue_tree_generated"
    ISSUE_TREE_NODE_UPDATED = "issue_tree_node_updated"
    KNOWLEDGE_RETRIEVED = "knowledge_retrieved"
    EVIDENCE_ADDED = "evidence_added"
    EVIDENCE_VALIDATED = "evidence_validated"
    EVIDENCE_REJECTED = "evidence_rejected"
    EVIDENCE_MARKED_STALE = "evidence_marked_stale"
    SPECIALIST_ANALYSIS_STARTED = "specialist_analysis_started"
    FINDING_RECORDED = "finding_recorded"
    SPECIALIST_ANALYSIS_COMPLETED = "specialist_analysis_completed"
    REVIEWER_REVIEWED = "reviewer_reviewed"
    REVIEWER_APPROVED = "reviewer_approved"
    REVIEWER_REJECTED = "reviewer_rejected"
    CHALLENGE_RECORDED = "challenge_recorded"
    CHALLENGER_CLEARED = "challenger_cleared"
    CHALLENGER_REJECTED = "challenger_rejected"
    RECOMMENDATION_DRAFTED = "recommendation_drafted"
    CONFIDENCE_SCORED = "confidence_scored"
    RECOMMENDATION_ACCEPTED = "recommendation_accepted"
    REPORT_GENERATED = "report_generated"
    DECK_GENERATED = "deck_generated"
    MODEL_GENERATED = "model_generated"
    HUMAN_INPUT_REQUESTED = "human_input_requested"
    HUMAN_INPUT_PROVIDED = "human_input_provided"
    PHASE_TRANSITIONED = "phase_transitioned"
    ENGAGEMENT_COMPLETED = "engagement_completed"
    ENGAGEMENT_FAILED = "engagement_failed"
    ENGAGEMENT_ABORTED = "engagement_aborted"
    LESSON_CAPTURED = "lesson_captured"
    KNOWLEDGE_GRAPH_LINKED = "knowledge_graph_linked"
    PROFILE_UPDATED = "profile_updated"


class EventMetadata(StratAgentModel):
    """Reusable event envelope (ADR-002 §Event Model)."""

    model_config = ConfigDict(frozen=True)

    event_id: EventId = Field(default_factory=new_event_id, frozen=True)
    engagement_id: EngagementId
    seq: int = 0
    occurred_at: datetime = Field(default_factory=_utcnow)
    recorded_at: datetime = Field(default_factory=_utcnow)
    actor: str
    source: EventSource = EventSource.SYSTEM
    schema_version: int = 1
    causation_id: EventId | None = None
    correlation_id: str | None = None


class _EventBase(StratAgentModel):
    """Common base for all events: immutable, carrying an EventMetadata envelope."""

    model_config = ConfigDict(frozen=True)

    metadata: EventMetadata


# --- intake -----------------------------------------------------------------


class EngagementCreated(_EventBase):
    type: Literal[EventType.ENGAGEMENT_CREATED] = EventType.ENGAGEMENT_CREATED
    slug: str
    tenant_id: str
    created_by: Literal["human", "system"] = "human"


class ProblemDefined(_EventBase):
    type: Literal[EventType.PROBLEM_DEFINED] = EventType.PROBLEM_DEFINED
    raw_input: str
    real_question: str | None = None


class ProblemUpdated(_EventBase):
    type: Literal[EventType.PROBLEM_UPDATED] = EventType.PROBLEM_UPDATED
    real_question: str
    reason: str | None = None


class ObjectivesRecorded(_EventBase):
    type: Literal[EventType.OBJECTIVES_RECORDED] = EventType.OBJECTIVES_RECORDED
    objectives: list[Objective] = []
    success_criteria: list[str] = []


class ConstraintsRecorded(_EventBase):
    type: Literal[EventType.CONSTRAINTS_RECORDED] = EventType.CONSTRAINTS_RECORDED
    constraints: list[Constraint] = []


class StakeholdersRecorded(_EventBase):
    type: Literal[EventType.STAKEHOLDERS_RECORDED] = EventType.STAKEHOLDERS_RECORDED
    stakeholders: list[Stakeholder] = []


# --- classification ---------------------------------------------------------


class CaseClassified(_EventBase):
    type: Literal[EventType.CASE_CLASSIFIED] = EventType.CASE_CLASSIFIED
    classification: CaseClassification


class CaseReclassified(_EventBase):
    type: Literal[EventType.CASE_RECLASSIFIED] = EventType.CASE_RECLASSIFIED
    classification: CaseClassification
    reason: str


class InformationGapIdentified(_EventBase):
    type: Literal[EventType.INFORMATION_GAP_IDENTIFIED] = (
        EventType.INFORMATION_GAP_IDENTIFIED
    )
    gap: Gap


class GapAnswered(_EventBase):
    type: Literal[EventType.GAP_ANSWERED] = EventType.GAP_ANSWERED
    gap_id: GapId
    question: str
    resolution: str


class GapAssumed(_EventBase):
    type: Literal[EventType.GAP_ASSUMED] = EventType.GAP_ASSUMED
    gap_id: GapId
    question: str
    assumption_id: AssumptionId


# --- assumption -------------------------------------------------------------


class AssumptionAdded(_EventBase):
    type: Literal[EventType.ASSUMPTION_ADDED] = EventType.ASSUMPTION_ADDED
    assumption: Assumption


class AssumptionUpdated(_EventBase):
    type: Literal[EventType.ASSUMPTION_UPDATED] = EventType.ASSUMPTION_UPDATED
    assumption_id: AssumptionId
    statement: str
    value: str
    rationale: str | None = None


class AssumptionInvalidated(_EventBase):
    type: Literal[EventType.ASSUMPTION_INVALIDATED] = EventType.ASSUMPTION_INVALIDATED
    assumption_id: AssumptionId
    statement: str
    reason: str


# --- planning ---------------------------------------------------------------


class EngagementPlanCreated(_EventBase):
    type: Literal[EventType.ENGAGEMENT_PLAN_CREATED] = EventType.ENGAGEMENT_PLAN_CREATED
    plan: EngagementPlan


class EngagementReplanned(_EventBase):
    type: Literal[EventType.ENGAGEMENT_REPLANNED] = EventType.ENGAGEMENT_REPLANNED
    plan: EngagementPlan
    reason: str


class FrameworkSelected(_EventBase):
    type: Literal[EventType.FRAMEWORK_SELECTED] = EventType.FRAMEWORK_SELECTED
    framework: FrameworkSelection


class FrameworkDeselected(_EventBase):
    type: Literal[EventType.FRAMEWORK_DESELECTED] = EventType.FRAMEWORK_DESELECTED
    framework_id: FrameworkId
    name: str
    reason: str


class IssueTreeGenerated(_EventBase):
    type: Literal[EventType.ISSUE_TREE_GENERATED] = EventType.ISSUE_TREE_GENERATED
    nodes: list[IssueNode] = []


class IssueTreeNodeUpdated(_EventBase):
    type: Literal[EventType.ISSUE_TREE_NODE_UPDATED] = EventType.ISSUE_TREE_NODE_UPDATED
    node_id: IssueNodeId
    question: str
    status: IssueNodeStatus
    answer: str | None = None


# --- knowledge --------------------------------------------------------------


class KnowledgeRetrieved(_EventBase):
    type: Literal[EventType.KNOWLEDGE_RETRIEVED] = EventType.KNOWLEDGE_RETRIEVED
    references: list[KnowledgeReference] = []


# --- evidence ---------------------------------------------------------------


class EvidenceAdded(_EventBase):
    type: Literal[EventType.EVIDENCE_ADDED] = EventType.EVIDENCE_ADDED
    evidence: Evidence


class EvidenceValidated(_EventBase):
    type: Literal[EventType.EVIDENCE_VALIDATED] = EventType.EVIDENCE_VALIDATED
    evidence_id: EvidenceId
    claim: str
    validator: str


class EvidenceRejected(_EventBase):
    type: Literal[EventType.EVIDENCE_REJECTED] = EventType.EVIDENCE_REJECTED
    evidence_id: EvidenceId
    claim: str
    reason: str


class EvidenceMarkedStale(_EventBase):
    type: Literal[EventType.EVIDENCE_MARKED_STALE] = EventType.EVIDENCE_MARKED_STALE
    evidence_id: EvidenceId
    claim: str
    reason: str
    as_of: datetime | None = None


# --- analysis ---------------------------------------------------------------


class SpecialistAnalysisStarted(_EventBase):
    type: Literal[EventType.SPECIALIST_ANALYSIS_STARTED] = (
        EventType.SPECIALIST_ANALYSIS_STARTED
    )
    analysis: str
    owner: str
    node_refs: list[IssueNodeId] = []


class FindingRecorded(_EventBase):
    type: Literal[EventType.FINDING_RECORDED] = EventType.FINDING_RECORDED
    analysis: str
    finding: Finding


class SpecialistAnalysisCompleted(_EventBase):
    type: Literal[EventType.SPECIALIST_ANALYSIS_COMPLETED] = (
        EventType.SPECIALIST_ANALYSIS_COMPLETED
    )
    analysis: str
    status: AnalysisStatus
    finding_count: int = 0


# --- governance -------------------------------------------------------------


class ReviewerReviewed(_EventBase):
    type: Literal[EventType.REVIEWER_REVIEWED] = EventType.REVIEWER_REVIEWED
    notes: ReviewerNotes


class ReviewerApproved(_EventBase):
    type: Literal[EventType.REVIEWER_APPROVED] = EventType.REVIEWER_APPROVED
    summary: str


class ReviewerRejected(_EventBase):
    type: Literal[EventType.REVIEWER_REJECTED] = EventType.REVIEWER_REJECTED
    summary: str
    issues: list[str] = []


class ChallengeRecorded(_EventBase):
    type: Literal[EventType.CHALLENGE_RECORDED] = EventType.CHALLENGE_RECORDED
    notes: ChallengeNotes


class ChallengerCleared(_EventBase):
    type: Literal[EventType.CHALLENGER_CLEARED] = EventType.CHALLENGER_CLEARED
    summary: str
    caveats: list[str] = []


class ChallengerRejected(_EventBase):
    type: Literal[EventType.CHALLENGER_REJECTED] = EventType.CHALLENGER_REJECTED
    summary: str
    counter_case: str


# --- recommendation ---------------------------------------------------------


class RecommendationDrafted(_EventBase):
    type: Literal[EventType.RECOMMENDATION_DRAFTED] = EventType.RECOMMENDATION_DRAFTED
    recommendation: Recommendations


class ConfidenceScored(_EventBase):
    type: Literal[EventType.CONFIDENCE_SCORED] = EventType.CONFIDENCE_SCORED
    report: ConfidenceReport


class RecommendationAccepted(_EventBase):
    type: Literal[EventType.RECOMMENDATION_ACCEPTED] = EventType.RECOMMENDATION_ACCEPTED
    recommendation_id: RecommendationId
    decision: str
    accepted_by: str


# --- delivery ---------------------------------------------------------------


class ReportGenerated(_EventBase):
    type: Literal[EventType.REPORT_GENERATED] = EventType.REPORT_GENERATED
    deliverable: Deliverable


class DeckGenerated(_EventBase):
    type: Literal[EventType.DECK_GENERATED] = EventType.DECK_GENERATED
    deliverable: Deliverable


class ModelGenerated(_EventBase):
    type: Literal[EventType.MODEL_GENERATED] = EventType.MODEL_GENERATED
    deliverable: Deliverable


# --- hitl -------------------------------------------------------------------


class HumanInputRequested(_EventBase):
    type: Literal[EventType.HUMAN_INPUT_REQUESTED] = EventType.HUMAN_INPUT_REQUESTED
    prompt: str
    target: str


class HumanInputProvided(_EventBase):
    type: Literal[EventType.HUMAN_INPUT_PROVIDED] = EventType.HUMAN_INPUT_PROVIDED
    prompt: str
    response: str
    provided_by: str


# --- lifecycle --------------------------------------------------------------


class PhaseTransitioned(_EventBase):
    type: Literal[EventType.PHASE_TRANSITIONED] = EventType.PHASE_TRANSITIONED
    from_status: LifecycleStatus
    to_status: LifecycleStatus


class EngagementCompleted(_EventBase):
    type: Literal[EventType.ENGAGEMENT_COMPLETED] = EventType.ENGAGEMENT_COMPLETED
    summary: str


class EngagementFailed(_EventBase):
    type: Literal[EventType.ENGAGEMENT_FAILED] = EventType.ENGAGEMENT_FAILED
    reason: str


class EngagementAborted(_EventBase):
    type: Literal[EventType.ENGAGEMENT_ABORTED] = EventType.ENGAGEMENT_ABORTED
    reason: str
    aborted_by: str


# --- curation ---------------------------------------------------------------


class LessonCaptured(_EventBase):
    type: Literal[EventType.LESSON_CAPTURED] = EventType.LESSON_CAPTURED
    lesson: str
    applies_to: str | None = None


class KnowledgeGraphLinked(_EventBase):
    type: Literal[EventType.KNOWLEDGE_GRAPH_LINKED] = EventType.KNOWLEDGE_GRAPH_LINKED
    graph_node: str
    relationship: str


class ProfileUpdated(_EventBase):
    type: Literal[EventType.PROFILE_UPDATED] = EventType.PROFILE_UPDATED
    company: str
    summary: str


# --- discriminated union + category mapping ---------------------------------

Event = Annotated[
    EngagementCreated
    | ProblemDefined
    | ProblemUpdated
    | ObjectivesRecorded
    | ConstraintsRecorded
    | StakeholdersRecorded
    | CaseClassified
    | CaseReclassified
    | InformationGapIdentified
    | GapAnswered
    | GapAssumed
    | AssumptionAdded
    | AssumptionUpdated
    | AssumptionInvalidated
    | EngagementPlanCreated
    | EngagementReplanned
    | FrameworkSelected
    | FrameworkDeselected
    | IssueTreeGenerated
    | IssueTreeNodeUpdated
    | KnowledgeRetrieved
    | EvidenceAdded
    | EvidenceValidated
    | EvidenceRejected
    | EvidenceMarkedStale
    | SpecialistAnalysisStarted
    | FindingRecorded
    | SpecialistAnalysisCompleted
    | ReviewerReviewed
    | ReviewerApproved
    | ReviewerRejected
    | ChallengeRecorded
    | ChallengerCleared
    | ChallengerRejected
    | RecommendationDrafted
    | ConfidenceScored
    | RecommendationAccepted
    | ReportGenerated
    | DeckGenerated
    | ModelGenerated
    | HumanInputRequested
    | HumanInputProvided
    | PhaseTransitioned
    | EngagementCompleted
    | EngagementFailed
    | EngagementAborted
    | LessonCaptured
    | KnowledgeGraphLinked
    | ProfileUpdated,
    Field(discriminator="type"),
]

EVENT_CATEGORIES: dict[EventType, EventCategory] = {
    EventType.ENGAGEMENT_CREATED: EventCategory.INTAKE,
    EventType.PROBLEM_DEFINED: EventCategory.INTAKE,
    EventType.PROBLEM_UPDATED: EventCategory.INTAKE,
    EventType.OBJECTIVES_RECORDED: EventCategory.INTAKE,
    EventType.CONSTRAINTS_RECORDED: EventCategory.INTAKE,
    EventType.STAKEHOLDERS_RECORDED: EventCategory.INTAKE,
    EventType.CASE_CLASSIFIED: EventCategory.CLASSIFICATION,
    EventType.CASE_RECLASSIFIED: EventCategory.CLASSIFICATION,
    EventType.INFORMATION_GAP_IDENTIFIED: EventCategory.CLASSIFICATION,
    EventType.GAP_ANSWERED: EventCategory.CLASSIFICATION,
    EventType.GAP_ASSUMED: EventCategory.CLASSIFICATION,
    EventType.ASSUMPTION_ADDED: EventCategory.ASSUMPTION,
    EventType.ASSUMPTION_UPDATED: EventCategory.ASSUMPTION,
    EventType.ASSUMPTION_INVALIDATED: EventCategory.ASSUMPTION,
    EventType.ENGAGEMENT_PLAN_CREATED: EventCategory.PLANNING,
    EventType.ENGAGEMENT_REPLANNED: EventCategory.PLANNING,
    EventType.FRAMEWORK_SELECTED: EventCategory.PLANNING,
    EventType.FRAMEWORK_DESELECTED: EventCategory.PLANNING,
    EventType.ISSUE_TREE_GENERATED: EventCategory.PLANNING,
    EventType.ISSUE_TREE_NODE_UPDATED: EventCategory.PLANNING,
    EventType.KNOWLEDGE_RETRIEVED: EventCategory.KNOWLEDGE,
    EventType.EVIDENCE_ADDED: EventCategory.EVIDENCE,
    EventType.EVIDENCE_VALIDATED: EventCategory.EVIDENCE,
    EventType.EVIDENCE_REJECTED: EventCategory.EVIDENCE,
    EventType.EVIDENCE_MARKED_STALE: EventCategory.EVIDENCE,
    EventType.SPECIALIST_ANALYSIS_STARTED: EventCategory.ANALYSIS,
    EventType.FINDING_RECORDED: EventCategory.ANALYSIS,
    EventType.SPECIALIST_ANALYSIS_COMPLETED: EventCategory.ANALYSIS,
    EventType.REVIEWER_REVIEWED: EventCategory.GOVERNANCE,
    EventType.REVIEWER_APPROVED: EventCategory.GOVERNANCE,
    EventType.REVIEWER_REJECTED: EventCategory.GOVERNANCE,
    EventType.CHALLENGE_RECORDED: EventCategory.GOVERNANCE,
    EventType.CHALLENGER_CLEARED: EventCategory.GOVERNANCE,
    EventType.CHALLENGER_REJECTED: EventCategory.GOVERNANCE,
    EventType.RECOMMENDATION_DRAFTED: EventCategory.RECOMMENDATION,
    EventType.CONFIDENCE_SCORED: EventCategory.RECOMMENDATION,
    EventType.RECOMMENDATION_ACCEPTED: EventCategory.RECOMMENDATION,
    EventType.REPORT_GENERATED: EventCategory.DELIVERY,
    EventType.DECK_GENERATED: EventCategory.DELIVERY,
    EventType.MODEL_GENERATED: EventCategory.DELIVERY,
    EventType.HUMAN_INPUT_REQUESTED: EventCategory.HITL,
    EventType.HUMAN_INPUT_PROVIDED: EventCategory.HITL,
    EventType.PHASE_TRANSITIONED: EventCategory.LIFECYCLE,
    EventType.ENGAGEMENT_COMPLETED: EventCategory.LIFECYCLE,
    EventType.ENGAGEMENT_FAILED: EventCategory.LIFECYCLE,
    EventType.ENGAGEMENT_ABORTED: EventCategory.LIFECYCLE,
    EventType.LESSON_CAPTURED: EventCategory.CURATION,
    EventType.KNOWLEDGE_GRAPH_LINKED: EventCategory.CURATION,
    EventType.PROFILE_UPDATED: EventCategory.CURATION,
}

__all__ = [
    "EVENT_CATEGORIES",
    "AssumptionAdded",
    "AssumptionInvalidated",
    "AssumptionUpdated",
    "CaseClassified",
    "CaseReclassified",
    "ChallengeRecorded",
    "ChallengerCleared",
    "ChallengerRejected",
    "ConfidenceScored",
    "ConstraintsRecorded",
    "DeckGenerated",
    "EngagementAborted",
    "EngagementCompleted",
    "EngagementCreated",
    "EngagementFailed",
    "EngagementPlanCreated",
    "EngagementReplanned",
    "Event",
    "EventCategory",
    "EventMetadata",
    "EventSource",
    "EventType",
    "EvidenceAdded",
    "EvidenceMarkedStale",
    "EvidenceRejected",
    "EvidenceValidated",
    "FindingRecorded",
    "FrameworkDeselected",
    "FrameworkSelected",
    "GapAnswered",
    "GapAssumed",
    "HumanInputProvided",
    "HumanInputRequested",
    "InformationGapIdentified",
    "IssueTreeGenerated",
    "IssueTreeNodeUpdated",
    "KnowledgeGraphLinked",
    "KnowledgeRetrieved",
    "LessonCaptured",
    "ModelGenerated",
    "ObjectivesRecorded",
    "PhaseTransitioned",
    "ProblemDefined",
    "ProblemUpdated",
    "ProfileUpdated",
    "RecommendationAccepted",
    "RecommendationDrafted",
    "ReportGenerated",
    "ReviewerApproved",
    "ReviewerRejected",
    "ReviewerReviewed",
    "SpecialistAnalysisCompleted",
    "SpecialistAnalysisStarted",
    "StakeholdersRecorded",
]
