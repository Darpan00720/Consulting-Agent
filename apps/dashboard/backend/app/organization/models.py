"""Core data types for the Consulting Organization Layer.

Sits BESIDE ``app.consulting`` (methodology) and ``app.knowledge``
(frameworks) as a third peer library: this package answers WHO does the
work, never HOW (that's the Workflow Engine) or WITH WHAT (that's the
Knowledge Library). Plain, frozen dataclasses/enums, no behavior — the same
split every layer in this codebase already uses.

Reuses ``app.consulting.models.EngagementCategory``/``ConsultingStage``/
``ArtifactType`` and ``app.knowledge.models.CompanySize`` rather than
inventing parallel taxonomies — "do not duplicate" applied a third time.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.consulting.models import ArtifactType, ConsultingStage, EngagementCategory
from app.knowledge.models import CompanySize


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---- Organizational taxonomy ------------------------------------------------


class Practice(StrEnum):
    STRATEGY = "strategy"
    OPERATIONS = "operations"
    DIGITAL_AI = "digital_ai"
    FINANCE = "finance"
    MARKET_RESEARCH = "market_research"
    RISK = "risk"
    IMPLEMENTATION = "implementation"
    KNOWLEDGE_MANAGEMENT = "knowledge_management"
    QUALITY_EDITORIAL = "quality_editorial"
    DATA_ANALYTICS = "data_analytics"


class ExperienceLevel(StrEnum):
    ANALYST = "analyst"
    SPECIALIST = "specialist"
    CONSULTANT = "consultant"
    SENIOR_CONSULTANT = "senior_consultant"
    MANAGER = "manager"
    PRINCIPAL = "principal"
    PARTNER = "partner"
    MANAGING_PARTNER = "managing_partner"


# Seniority order for escalation/reporting-chain logic — a rank, not a
# duplicate taxonomy (the enum values themselves stay the source of truth).
EXPERIENCE_RANK: dict[ExperienceLevel, int] = {
    ExperienceLevel.ANALYST: 0,
    ExperienceLevel.SPECIALIST: 1,
    ExperienceLevel.CONSULTANT: 2,
    ExperienceLevel.SENIOR_CONSULTANT: 3,
    ExperienceLevel.MANAGER: 4,
    ExperienceLevel.PRINCIPAL: 5,
    ExperienceLevel.PARTNER: 6,
    ExperienceLevel.MANAGING_PARTNER: 7,
}


class DecisionType(StrEnum):
    """The requester's "Decision Governance" section, verbatim."""

    APPROVE_HYPOTHESES = "approve_hypotheses"
    APPROVE_ASSUMPTIONS = "approve_assumptions"
    APPROVE_FINDINGS = "approve_findings"
    APPROVE_RECOMMENDATIONS = "approve_recommendations"
    APPROVE_IMPLEMENTATION_PLANS = "approve_implementation_plans"
    APPROVE_EXECUTIVE_SUMMARIES = "approve_executive_summaries"


class ReviewStage(StrEnum):
    PEER = "peer"
    MANAGER = "manager"
    PARTNER = "partner"
    EXECUTIVE = "executive"


# ---- Role model (requester's "Role Model" section) --------------------------


@dataclass(frozen=True)
class RoleDefinition:
    """Every field the requester named. Immutable — a catalog entry, never
    mutated after registration (a content change is a new version, the same
    convention ``app.knowledge.FrameworkDefinition`` established)."""

    id: str
    name: str
    description: str
    practice: Practice
    experience_level: ExperienceLevel
    primary_responsibilities: tuple[str, ...]
    secondary_responsibilities: tuple[str, ...]
    decision_authority: tuple[DecisionType, ...]
    approval_authority: tuple[ArtifactType, ...]
    required_capabilities: tuple[str, ...]
    supported_engagement_types: tuple[EngagementCategory, ...]
    supported_frameworks: tuple[
        str, ...
    ]  # framework ids, cross-referenced into app.knowledge
    quality_checklist: tuple[str, ...]
    handoff_criteria: tuple[str, ...]
    escalation_rules: tuple[str, ...]
    deliverables_owned: tuple[ArtifactType, ...]
    inputs_required: tuple[str, ...]
    outputs_produced: tuple[str, ...]
    kpis: tuple[str, ...]
    review_authority: tuple[ReviewStage, ...] = ()
    reporting_line: str | None = (
        None  # role id of this role's manager; None = top of firm
    )
    version: str = "1.0.0"
    owner: str = "StratAgent Organization Layer"


# ---- RACI model (requester's "Responsibility Matrix" section) --------------


class RACIRole(StrEnum):
    RESPONSIBLE = "responsible"
    ACCOUNTABLE = "accountable"
    CONSULTED = "consulted"
    INFORMED = "informed"


@dataclass(frozen=True)
class RACIAssignment:
    activity: str
    role_id: str
    raci: RACIRole


@dataclass
class RACIMatrix:
    assignments: list[RACIAssignment] = field(default_factory=list)

    def for_activity(self, activity: str) -> tuple[RACIAssignment, ...]:
        return tuple(a for a in self.assignments if a.activity == activity)


@dataclass(frozen=True)
class ResponsibilityConflict:
    activity: str
    reason: str
    role_ids: tuple[str, ...]


# ---- Work allocation (requester's "Work Allocation" section) --------------


@dataclass(frozen=True)
class AllocationContext:
    engagement_type: EngagementCategory
    workflow_stage: ConsultingStage
    frameworks_selected: tuple[str, ...] = ()
    industry: str = "all"
    company_size: CompanySize = CompanySize.MIDMARKET
    required_expertise: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True)
class RoleAssignment:
    role_id: str
    reasoning: tuple[str, ...]
    workload_share: float


@dataclass(frozen=True)
class AllocationResult:
    recommended_team: tuple[RoleAssignment, ...]
    confidence: float


# ---- Collaboration model (requester's "Collaboration Model" section) ------


class RequestKind(StrEnum):
    TASK = "task"
    ANALYSIS = "analysis"
    CLARIFICATION = "clarification"
    REVIEW = "review"
    APPROVAL = "approval"
    INFORMATION = "information"


class RequestStatus(StrEnum):
    OPEN = "open"
    RESPONDED = "responded"
    CLOSED = "closed"


@dataclass(frozen=True)
class CollaborationRequest:
    id: str
    kind: RequestKind
    from_role: str
    to_role: str
    subject: str
    content: str
    status: RequestStatus = RequestStatus.OPEN
    response: str | None = None
    created_at: float = field(default_factory=time.time)
    responded_at: float | None = None


def new_request_id() -> str:
    return _new_id("req")


# ---- Review workflow (requester's "Review Process" section) ---------------


class ReviewOutcome(StrEnum):
    APPROVED = "approved"
    APPROVED_WITH_COMMENTS = "approved_with_comments"
    REWORK_REQUIRED = "rework_required"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ReviewChecklistInput:
    """What a reviewer supplies — this package validates STRUCTURE (does the
    reviewer hold the right authority, has every named check been reported)
    never the judgment itself, the same "generic, not per-domain" split
    ``app.knowledge.quality`` established for framework quality gates."""

    logic_sound: bool = True
    evidence_traceable: bool = True
    calculations_verified: bool = True
    framework_application_correct: bool = True
    recommendations_supported: bool = True
    clarity: bool = True
    client_ready: bool = True
    comments: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewChecklistResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ReviewResult:
    id: str
    artifact_ref: str
    stage: ReviewStage
    reviewer_role_id: str
    outcome: ReviewOutcome
    checklist: tuple[ReviewChecklistResult, ...]
    comments: tuple[str, ...] = ()
    reviewed_at: float = field(default_factory=time.time)


def new_review_id() -> str:
    return _new_id("rev")


# ---- Decision governance (requester's "Decision Governance" section) ------


@dataclass(frozen=True)
class ApprovalOutcome:
    decision: DecisionType
    requested_by_role_id: str
    approved_by_role_id: str | None
    escalated: bool
    escalation_chain: tuple[str, ...]
    reason: str = ""


@dataclass(frozen=True)
class DelegationRecord:
    decision: DecisionType
    from_role_id: str
    to_role_id: str
    reason: str
    created_at: float = field(default_factory=time.time)


# ---- Organizational metrics (requester's "Organizational Metrics" section) -


@dataclass(frozen=True)
class OrgMetrics:
    utilization_by_role: dict
    handoff_count: int
    review_iterations_by_artifact: dict
    average_approval_latency_s: float
    quality_pass_rate: float
    role_workload: dict
    escalation_frequency: float
    average_decision_turnaround_s: float
