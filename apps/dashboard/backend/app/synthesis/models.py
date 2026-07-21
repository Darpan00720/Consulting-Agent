"""Core data types for the Consulting Synthesis & Recommendation Engine.

Sits BESIDE ``app.consulting`` (methodology), ``app.knowledge`` (frameworks),
and ``app.organization`` (roles) as a fourth peer library: this package
answers HOW dozens of analyses become one coherent recommendation. Plain,
frozen dataclasses/enums, no behavior — the same split every layer in this
codebase already uses.

**The traceability chain reuses ``app.consulting.models.Evidence`` as its
base** rather than duplicating it — Evidence already has a real, enforced
home (``app.consulting.tracking.add_evidence``). Everything here builds
strictly upward from real evidence ids: Finding -> Insight -> Opportunity ->
Recommendation -> ImplementationTheme -> StrategicNarrative.

**``app.synthesis.models.Recommendation`` is a distinct concept from
``app.consulting.models.Recommendation``, not a duplicate of it** — the
consulting-layer ``Recommendation`` is the engagement's lightweight tracked
record (used by ``app.consulting``'s own quality gates); this one is the
rich, multi-dimensional synthesis-chain node (business rationale, trade-offs,
KPIs, approval status). Two distinct models the same word describes at two
different altitudes, the same relationship ADR-013 drew between the
Workflow Router's "routing categories" and the Provider Router's "capability
categories."
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.consulting.models import ConsultingStage


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---- Finding model (requester's "Finding Model" section) -------------------


class FindingStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    CHALLENGED = "challenged"
    RETIRED = "retired"


@dataclass(frozen=True)
class Finding:
    """Every field the requester named. Must originate from evidence —
    ``supporting_evidence_ids`` is enforced non-empty by
    ``tracking.create_finding``, never by this dataclass itself (which stays
    pure data, per the platform-wide "models are data" split)."""

    id: str
    statement: str
    supporting_evidence_ids: tuple[str, ...]
    confidence: float
    business_impact: str
    affected_stakeholders: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    related_frameworks: tuple[
        str, ...
    ] = ()  # framework ids, cross-referenced into app.knowledge
    related_workflow_stages: tuple[ConsultingStage, ...] = ()
    owner: str = ""  # role id, cross-referenced into app.organization
    status: FindingStatus = FindingStatus.DRAFT
    timestamp: float = field(default_factory=time.time)


def new_finding_id() -> str:
    return _new_id("find")


# ---- Insight model (requester's "Insight Model" section) ------------------


@dataclass(frozen=True)
class Insight:
    """Combines multiple findings into a theme."""

    id: str
    theme: str
    supporting_finding_ids: tuple[str, ...]
    drivers: tuple[str, ...] = ()
    root_causes: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()  # other insight ids
    strategic_implications: tuple[str, ...] = ()
    confidence: float = 0.5
    alternative_interpretations: tuple[str, ...] = ()
    contradictory_evidence_ids: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


def new_insight_id() -> str:
    return _new_id("ins")


# ---- Opportunity model (requester's "Opportunity Model" section) ----------


class TimeHorizon(StrEnum):
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


@dataclass(frozen=True)
class Opportunity:
    """Descriptive fields carry the narrative; the ``*_score`` fields
    (0.0-1.0) are the same content expressed numerically so
    ``prioritization.py`` has real inputs to compute against, without asking
    a caller to re-supply the same judgment twice."""

    id: str
    description: str
    supporting_insight_ids: tuple[str, ...]
    expected_value: str
    strategic_importance: str
    complexity: str
    investment: str
    risk: str
    dependencies: tuple[str, ...] = ()  # other opportunity ids
    priority: int = 0
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM_TERM
    confidence: float = 0.5
    expected_value_score: float = 0.5
    complexity_score: float = 0.5
    investment_score: float = 0.5
    risk_score: float = 0.5
    created_at: float = field(default_factory=time.time)


def new_opportunity_id() -> str:
    return _new_id("opp")


# ---- Recommendation model (requester's "Recommendation Model" section) ----


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class Recommendation:
    """Every field the requester named. ``contradicts`` is a DECLARED
    relationship (other recommendation ids this one conflicts with) rather
    than something ``consistency.py`` infers via text analysis — the same
    honest scope limit ``app.knowledge.composition``'s output/input
    alignment check already drew for itself."""

    id: str
    statement: str
    business_rationale: str
    supporting_opportunity_ids: tuple[str, ...]
    supporting_insight_ids: tuple[str, ...]
    supporting_finding_ids: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    expected_benefits: tuple[str, ...] = ()
    cost: str = ""
    risk: str = ""
    trade_offs: tuple[str, ...] = ()
    implementation_complexity: str = ""
    kpis: tuple[str, ...] = ()
    confidence: float = 0.5
    owner: str = ""  # role id, cross-referenced into app.organization
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    contradicts: tuple[str, ...] = ()  # other recommendation ids, declared
    created_at: float = field(default_factory=time.time)


def new_recommendation_id() -> str:
    return _new_id("srec")


# ---- Implementation Theme + Strategic Narrative ----------------------------


@dataclass(frozen=True)
class ImplementationTheme:
    id: str
    name: str
    description: str
    supporting_recommendation_ids: tuple[str, ...]
    workstreams: tuple[str, ...] = ()
    timeline: str = ""
    owner: str = ""
    created_at: float = field(default_factory=time.time)


def new_implementation_theme_id() -> str:
    return _new_id("theme")


@dataclass(frozen=True)
class StrategicNarrative:
    """References supporting recommendations/themes/findings/insights by id
    — assembled by ``narrative.py`` from real synthesis-state content, never
    free-standing prose disconnected from the chain."""

    id: str
    current_situation: str
    key_finding_ids: tuple[str, ...]
    core_insight_ids: tuple[str, ...]
    strategic_choices: tuple[str, ...]
    recommendation_ids: tuple[str, ...]
    implementation_theme_ids: tuple[str, ...]
    expected_outcomes: tuple[str, ...]
    risks: tuple[str, ...]
    executive_summary: str
    created_at: float = field(default_factory=time.time)


def new_narrative_id() -> str:
    return _new_id("narr")


# ---- Trade-off analysis (requester's "Trade-off Analysis" section) --------

TRADE_OFF_DIMENSIONS: tuple[str, ...] = (
    "financial",
    "operational",
    "customer",
    "technology",
    "risk",
    "implementation",
    "organizational",
    "strategic_alignment",
)


@dataclass(frozen=True)
class TradeOffOption:
    id: str
    name: str
    dimension_scores: dict  # dict[str, float], one of TRADE_OFF_DIMENSIONS per key
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TradeOffResult:
    options: tuple[TradeOffOption, ...]
    dimension_weights: dict  # dict[str, float]
    scores: dict  # dict[option_id, float]
    ranked_option_ids: tuple[str, ...]
    reasoning: tuple[str, ...]


# ---- Root cause analysis (requester's "Root Cause Analysis" section) ------


class RootCauseMethod(StrEnum):
    FIVE_WHYS = "five_whys"
    FISHBONE = "fishbone"
    FAULT_TREE = "fault_tree"
    CAUSE_MAPPING = "cause_mapping"


@dataclass(frozen=True)
class RootCauseNode:
    id: str
    statement: str
    parent_id: str | None
    category: str = ""  # e.g. fishbone's "people"/"process"/"technology"/"environment"


@dataclass(frozen=True)
class RootCauseAnalysis:
    id: str
    method: RootCauseMethod
    problem_statement: str
    nodes: tuple[RootCauseNode, ...]
    root_cause_ids: tuple[str, ...]  # multiple root causes supported
    created_at: float = field(default_factory=time.time)


def new_root_cause_analysis_id() -> str:
    return _new_id("rca")


# ---- Prioritization (requester's "Prioritization" section) -----------------


class PrioritizationMethod(StrEnum):
    IMPACT_VS_EFFORT = "impact_vs_effort"
    ICE = "ice"
    RICE = "rice"
    WEIGHTED_SCORING = "weighted_scoring"
    STRATEGIC_ALIGNMENT = "strategic_alignment"
    RISK_ADJUSTED = "risk_adjusted"


@dataclass(frozen=True)
class PrioritizationInput:
    item_id: str
    impact: float = 0.0
    effort: float = 0.0
    confidence: float = 0.0
    reach: float = 0.0
    ease: float = 0.0
    strategic_alignment: float = 0.0
    risk: float = 0.0
    weights: dict = field(
        default_factory=dict
    )  # dict[str, float], for WEIGHTED_SCORING


@dataclass(frozen=True)
class PrioritizationScore:
    item_id: str
    method: PrioritizationMethod
    score: float
    rank: int
    explanation: str


@dataclass(frozen=True)
class PrioritizationResult:
    method: PrioritizationMethod
    scores: tuple[PrioritizationScore, ...]


# ---- Business impact (requester's "Business Impact" section) --------------


class BusinessImpactDimension(StrEnum):
    REVENUE = "revenue"
    COST = "cost"
    PROFIT = "profit"
    CUSTOMER = "customer"
    OPERATIONAL = "operational"
    TECHNOLOGY = "technology"
    STRATEGIC = "strategic"
    ORGANIZATIONAL = "organizational"


@dataclass(frozen=True)
class BusinessImpactEstimate:
    dimension: BusinessImpactDimension
    estimate: str
    confidence: float
    estimated_value: float | None = None
    rationale: str = ""


@dataclass(frozen=True)
class BusinessImpactAssessment:
    id: str
    target_ref: str  # a Recommendation or Opportunity id
    estimates: tuple[BusinessImpactEstimate, ...]
    overall_confidence: float
    created_at: float = field(default_factory=time.time)


def new_business_impact_id() -> str:
    return _new_id("bia")


# ---- Consistency validation (requester's "Consistency Validation" section) -


class ConsistencyIssueType(StrEnum):
    UNSUPPORTED_RECOMMENDATION = "unsupported_recommendation"
    DUPLICATE_FINDING = "duplicate_finding"
    CONTRADICTORY_RECOMMENDATIONS = "contradictory_recommendations"
    MISSING_EVIDENCE = "missing_evidence"
    CONFLICTING_ASSUMPTIONS = "conflicting_assumptions"
    ORPHAN_INSIGHT = "orphan_insight"
    CIRCULAR_REASONING = "circular_reasoning"
    LOW_CONFIDENCE_CONCLUSION = "low_confidence_conclusion"


@dataclass(frozen=True)
class ConsistencyIssue:
    issue_type: ConsistencyIssueType
    ref_ids: tuple[str, ...]
    detail: str


# ---- Quality model (requester's "Quality Model" section) ------------------


class QualityDimension(StrEnum):
    TRACEABILITY = "traceability"
    LOGICAL_CONSISTENCY = "logical_consistency"
    EVIDENCE_COVERAGE = "evidence_coverage"
    CONFIDENCE = "confidence"
    RECOMMENDATION_COMPLETENESS = "recommendation_completeness"
    TRADE_OFF_ANALYSIS = "trade_off_analysis"
    BUSINESS_IMPACT = "business_impact"
    IMPLEMENTATION_FEASIBILITY = "implementation_feasibility"


@dataclass(frozen=True)
class QualityCheckResult:
    dimension: QualityDimension
    passed: bool
    score: float
    detail: str = ""


@dataclass(frozen=True)
class QualityReport:
    checks: tuple[QualityCheckResult, ...]
    overall_score: float
