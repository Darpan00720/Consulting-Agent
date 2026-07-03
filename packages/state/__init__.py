"""Public API of the Engagement State package.

This module curates the **entire** public surface of ``state`` — the facade, the
protocol, the domain models, the enums, and the shared value objects. Anything not
re-exported here is internal and must not be imported directly. See
``docs/api/EngagementState.md`` for the reference and stability guarantees.
"""

from __future__ import annotations

from common.models import DomainObject
from common.values import ConfidenceScore, Identifier, Reference, new_id
from state.append import (
    AppendError,
    AppendErrorCode,
    AppendResult,
    AppendUnsupportedError,
    EventAdmissionError,
    VersionConflictError,
)
from state.enums import LifecycleStatus
from state.events import (
    EVENT_CATEGORIES,
    Event,
    EventCategory,
    EventMetadata,
    EventSource,
    EventType,
)
from state.facade import Engagement, EngagementProtocol
from state.identifiers import (
    AssumptionId,
    DeliverableId,
    EngagementId,
    EventId,
    EvidenceId,
    FrameworkId,
    GapId,
    IssueNodeId,
    RecommendationId,
)
from state.ledgers import Assumption, AssumptionStatus, Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding, SensitivityCase
from state.sections.enums import (
    AnalysisStatus,
    CaseArchetype,
    ChallengeVerdict,
    CheckResult,
    ConstraintType,
    DeliverableKind,
    DeliverableStatus,
    GapCriticality,
    GapStatus,
    GateResult,
    IssueNodeStatus,
    KnowledgeRefKind,
    ObjectiveSource,
    PendingKind,
    PlanStepStatus,
    RecommendationStatus,
    ReviewCheckName,
    ReviewVerdict,
    StakeholderRelationship,
)
from state.sections.governance import ChallengeNotes, ReviewCheck, ReviewerNotes
from state.sections.lifecycle import PendingRequirement, PhaseRecord, QualityGate
from state.sections.output import (
    ConfidenceReport,
    Deliverable,
    KnowledgeLink,
    NextStep,
    Recommendations,
    RejectedAlternative,
)
from state.sections.planning import (
    EngagementPlan,
    FrameworkSelection,
    IssueNode,
    KnowledgeReference,
    PlanStep,
)
from state.sections.scoping import (
    CaseClassification,
    Constraint,
    Document,
    Gap,
    Objective,
    ProblemDefinition,
    Stakeholder,
)
from state.validation import (
    StateValidationError,
    ValidationGroup,
    ValidationReport,
    Violation,
    ViolationSeverity,
)

__all__ = [
    # Facade
    "Engagement",
    "EngagementProtocol",
    # Append API (M1.7.3-S5)
    "AppendError",
    "AppendErrorCode",
    "AppendResult",
    "AppendUnsupportedError",
    "EventAdmissionError",
    "VersionConflictError",
    # Validation surface (M1.7.3-S5)
    "StateValidationError",
    "ValidationGroup",
    "ValidationReport",
    "Violation",
    "ViolationSeverity",
    # Root
    "EngagementState",
    "EngagementMetadata",
    "LifecycleStatus",
    # Ledgers
    "Evidence",
    "Assumption",
    "EvidenceType",
    "AssumptionStatus",
    # Scoping
    "Document",
    "ProblemDefinition",
    "Objective",
    "Constraint",
    "Stakeholder",
    "CaseClassification",
    "Gap",
    "CaseArchetype",
    "ObjectiveSource",
    "ConstraintType",
    "StakeholderRelationship",
    "GapCriticality",
    "GapStatus",
    # Planning
    "PlanStep",
    "EngagementPlan",
    "FrameworkSelection",
    "IssueNode",
    "KnowledgeReference",
    "PlanStepStatus",
    "IssueNodeStatus",
    "KnowledgeRefKind",
    # Analysis
    "Finding",
    "SensitivityCase",
    "AnalysisBlock",
    "AnalysisStatus",
    # Governance
    "ReviewCheck",
    "ReviewerNotes",
    "ChallengeNotes",
    "ReviewCheckName",
    "CheckResult",
    "ReviewVerdict",
    "ChallengeVerdict",
    # Output
    "NextStep",
    "RejectedAlternative",
    "Recommendations",
    "ConfidenceReport",
    "Deliverable",
    "KnowledgeLink",
    "RecommendationStatus",
    "DeliverableKind",
    "DeliverableStatus",
    # Lifecycle audit
    "PhaseRecord",
    "QualityGate",
    "PendingRequirement",
    "GateResult",
    "PendingKind",
    # Value objects
    "ConfidenceScore",
    "Identifier",
    "Reference",
    "DomainObject",
    "new_id",
    # Strongly-typed identifiers
    "EventId",
    "EngagementId",
    "AssumptionId",
    "EvidenceId",
    "GapId",
    "IssueNodeId",
    "FrameworkId",
    "DeliverableId",
    "RecommendationId",
    # Events
    "Event",
    "EventMetadata",
    "EventType",
    "EventCategory",
    "EventSource",
    "EVENT_CATEGORIES",
]
