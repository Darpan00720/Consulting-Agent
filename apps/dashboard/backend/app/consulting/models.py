"""Core data types for the Consulting Workflow Engine.

Sits ON TOP of the platform (Workflow Router, Dispatcher, Agent Runtime,
Memory Platform, Tool Platform) — this package owns consulting METHODOLOGY
(engagement lifecycle, quality gates, evidence discipline), never
infrastructure. Plain, frozen dataclasses/enums here, no behavior — the same
"models are data, behavior lives in the owning module" split every platform
layer already uses (``app.agents.models``, ``app.memory.models``,
``app.tools.models``).

Dependency-free of ``app.workflow``/``app.agents``/``app.memory``/
``app.tools`` at runtime — the Consulting Workflow Engine is a CONSUMER of
those layers (via ``engine.py``), never imported by them.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

# ---- Engagement taxonomy ---------------------------------------------------


class EngagementFamily(StrEnum):
    STRATEGY = "strategy"
    OPERATIONS = "operations"
    DIGITAL = "digital"
    ORGANIZATION = "organization"
    FINANCE = "finance"
    INNOVATION = "innovation"
    RISK = "risk"


class EngagementCategory(StrEnum):
    """At least the categories the requester enumerated, across 7 families
    (28 total). New categories register via ``registry.default_workflow_registry``
    without touching this enum's owning module logic — see ``workflow.py``'s
    ``standard_workflow`` builder, which is what makes a 29th category a
    one-line registration rather than a new hand-written class."""

    # Strategy
    CORPORATE_STRATEGY = "corporate_strategy"
    BUSINESS_STRATEGY = "business_strategy"
    GROWTH_STRATEGY = "growth_strategy"
    MARKET_ENTRY = "market_entry"
    GO_TO_MARKET = "go_to_market"
    PRICING_STRATEGY = "pricing_strategy"
    PORTFOLIO_STRATEGY = "portfolio_strategy"
    # Operations
    COST_REDUCTION = "cost_reduction"
    OPERATIONAL_EXCELLENCE = "operational_excellence"
    PROCESS_OPTIMIZATION = "process_optimization"
    SUPPLY_CHAIN = "supply_chain"
    # Digital
    DIGITAL_TRANSFORMATION = "digital_transformation"
    AI_TRANSFORMATION = "ai_transformation"
    AUTOMATION_STRATEGY = "automation_strategy"
    TECHNOLOGY_MODERNIZATION = "technology_modernization"
    # Organization
    ORGANIZATIONAL_DESIGN = "organizational_design"
    WORKFORCE_STRATEGY = "workforce_strategy"
    CHANGE_MANAGEMENT = "change_management"
    # Finance
    INVESTMENT_EVALUATION = "investment_evaluation"
    BUSINESS_CASE = "business_case"
    DUE_DILIGENCE = "due_diligence"
    FINANCIAL_PERFORMANCE = "financial_performance"
    # Innovation
    PRODUCT_STRATEGY = "product_strategy"
    INNOVATION_STRATEGY = "innovation_strategy"
    VENTURE_VALIDATION = "venture_validation"
    # Risk
    RISK_ASSESSMENT = "risk_assessment"
    SCENARIO_PLANNING = "scenario_planning"
    BUSINESS_CONTINUITY = "business_continuity"


CATEGORY_FAMILY: dict[EngagementCategory, EngagementFamily] = {
    EngagementCategory.CORPORATE_STRATEGY: EngagementFamily.STRATEGY,
    EngagementCategory.BUSINESS_STRATEGY: EngagementFamily.STRATEGY,
    EngagementCategory.GROWTH_STRATEGY: EngagementFamily.STRATEGY,
    EngagementCategory.MARKET_ENTRY: EngagementFamily.STRATEGY,
    EngagementCategory.GO_TO_MARKET: EngagementFamily.STRATEGY,
    EngagementCategory.PRICING_STRATEGY: EngagementFamily.STRATEGY,
    EngagementCategory.PORTFOLIO_STRATEGY: EngagementFamily.STRATEGY,
    EngagementCategory.COST_REDUCTION: EngagementFamily.OPERATIONS,
    EngagementCategory.OPERATIONAL_EXCELLENCE: EngagementFamily.OPERATIONS,
    EngagementCategory.PROCESS_OPTIMIZATION: EngagementFamily.OPERATIONS,
    EngagementCategory.SUPPLY_CHAIN: EngagementFamily.OPERATIONS,
    EngagementCategory.DIGITAL_TRANSFORMATION: EngagementFamily.DIGITAL,
    EngagementCategory.AI_TRANSFORMATION: EngagementFamily.DIGITAL,
    EngagementCategory.AUTOMATION_STRATEGY: EngagementFamily.DIGITAL,
    EngagementCategory.TECHNOLOGY_MODERNIZATION: EngagementFamily.DIGITAL,
    EngagementCategory.ORGANIZATIONAL_DESIGN: EngagementFamily.ORGANIZATION,
    EngagementCategory.WORKFORCE_STRATEGY: EngagementFamily.ORGANIZATION,
    EngagementCategory.CHANGE_MANAGEMENT: EngagementFamily.ORGANIZATION,
    EngagementCategory.INVESTMENT_EVALUATION: EngagementFamily.FINANCE,
    EngagementCategory.BUSINESS_CASE: EngagementFamily.FINANCE,
    EngagementCategory.DUE_DILIGENCE: EngagementFamily.FINANCE,
    EngagementCategory.FINANCIAL_PERFORMANCE: EngagementFamily.FINANCE,
    EngagementCategory.PRODUCT_STRATEGY: EngagementFamily.INNOVATION,
    EngagementCategory.INNOVATION_STRATEGY: EngagementFamily.INNOVATION,
    EngagementCategory.VENTURE_VALIDATION: EngagementFamily.INNOVATION,
    EngagementCategory.RISK_ASSESSMENT: EngagementFamily.RISK,
    EngagementCategory.SCENARIO_PLANNING: EngagementFamily.RISK,
    EngagementCategory.BUSINESS_CONTINUITY: EngagementFamily.RISK,
}


class ConsultingStage(StrEnum):
    """The 10-stage consulting lifecycle (requester's "Consulting Lifecycle"
    section), in canonical order — see ``STAGE_ORDER``."""

    PROBLEM_DEFINITION = "problem_definition"
    HYPOTHESIS_DEVELOPMENT = "hypothesis_development"
    ISSUE_TREE_CONSTRUCTION = "issue_tree_construction"
    ANALYSIS_PLANNING = "analysis_planning"
    EVIDENCE_COLLECTION = "evidence_collection"
    ANALYSIS_EXECUTION = "analysis_execution"
    SYNTHESIS = "synthesis"
    RECOMMENDATIONS = "recommendations"
    IMPLEMENTATION_ROADMAP = "implementation_roadmap"
    EXECUTIVE_DELIVERABLE = "executive_deliverable"


STAGE_ORDER: tuple[ConsultingStage, ...] = (
    ConsultingStage.PROBLEM_DEFINITION,
    ConsultingStage.HYPOTHESIS_DEVELOPMENT,
    ConsultingStage.ISSUE_TREE_CONSTRUCTION,
    ConsultingStage.ANALYSIS_PLANNING,
    ConsultingStage.EVIDENCE_COLLECTION,
    ConsultingStage.ANALYSIS_EXECUTION,
    ConsultingStage.SYNTHESIS,
    ConsultingStage.RECOMMENDATIONS,
    ConsultingStage.IMPLEMENTATION_ROADMAP,
    ConsultingStage.EXECUTIVE_DELIVERABLE,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---- Hypothesis management --------------------------------------------------


class HypothesisStatus(StrEnum):
    OPEN = "open"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REVISED = "revised"


@dataclass(frozen=True)
class HypothesisRevision:
    """One prior version of a hypothesis, kept so every hypothesis remains
    traceable across revisions (requester's "Hypothesis Management" section)."""

    statement: str
    confidence: float
    note: str
    revised_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class Hypothesis:
    id: str
    statement: str
    confidence: float
    rationale: str
    status: HypothesisStatus = HypothesisStatus.OPEN
    evidence_ids: tuple[str, ...] = ()
    revisions: tuple[HypothesisRevision, ...] = ()
    created_at: float = field(default_factory=time.time)


def new_hypothesis_id() -> str:
    return _new_id("hyp")


# ---- Assumption registry ----------------------------------------------------


class AssumptionStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class Assumption:
    id: str
    description: str
    owner: str
    source: str
    confidence: float
    validation_status: AssumptionStatus = AssumptionStatus.UNVALIDATED
    date_created: float = field(default_factory=time.time)
    date_validated: float | None = None
    related_analyses: tuple[str, ...] = ()


def new_assumption_id() -> str:
    return _new_id("asm")


# ---- Evidence model ----------------------------------------------------------


class EvidenceSourceType(StrEnum):
    INTERNAL_MEMORY = "internal_memory"
    KNOWLEDGE_LIBRARY = "knowledge_library"
    EXTERNAL_RESEARCH = "external_research"
    UPLOADED_DOCUMENT = "uploaded_document"
    CALCULATION = "calculation"
    STRUCTURED_DATA = "structured_data"


class EvidenceQuality(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Evidence:
    id: str
    source: str
    source_type: EvidenceSourceType
    quality: EvidenceQuality
    confidence: float
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    related_hypothesis_ids: tuple[str, ...] = ()
    related_recommendation_ids: tuple[str, ...] = ()


def new_evidence_id() -> str:
    return _new_id("ev")


# ---- Recommendations, decisions ---------------------------------------------


@dataclass(frozen=True)
class Recommendation:
    """Every field the requester mandated: evidence, impact, risks, tradeoffs,
    effort, confidence. Construction is gated by ``tracking.create_recommendation``
    (never built directly), which enforces non-empty ``supporting_evidence_ids``
    against real evidence in the engagement — "No recommendation should be
    generated without supporting evidence" as a hard invariant, not a lint."""

    id: str
    statement: str
    supporting_evidence_ids: tuple[str, ...]
    expected_impact: str
    risks: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    implementation_effort: str
    confidence: float
    created_at: float = field(default_factory=time.time)


def new_recommendation_id() -> str:
    return _new_id("rec")


@dataclass(frozen=True)
class Decision:
    id: str
    decision: str
    reasoning: str
    alternatives_considered: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    decision_owner: str
    confidence: float
    timestamp: float = field(default_factory=time.time)


def new_decision_id() -> str:
    return _new_id("dec")


# ---- Consulting artifacts -----------------------------------------------------


class ArtifactType(StrEnum):
    PROBLEM_STATEMENT = "problem_statement"
    PROJECT_CHARTER = "project_charter"
    ISSUE_TREE = "issue_tree"
    HYPOTHESIS_LOG = "hypothesis_log"
    ASSUMPTION_REGISTER = "assumption_register"
    ANALYSIS_PLAN = "analysis_plan"
    INTERVIEW_GUIDE = "interview_guide"
    RESEARCH_SUMMARY = "research_summary"
    FINDINGS_REPORT = "findings_report"
    RECOMMENDATION_MATRIX = "recommendation_matrix"
    IMPLEMENTATION_ROADMAP = "implementation_roadmap"
    RISK_REGISTER = "risk_register"
    EXECUTIVE_SUMMARY = "executive_summary"


ARTIFACT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class Artifact:
    id: str
    type: ArtifactType
    stage: ConsultingStage
    content: dict
    schema_version: str = ARTIFACT_SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)


def new_artifact_id() -> str:
    return _new_id("art")


# ---- Quality gates -------------------------------------------------------------


@dataclass(frozen=True)
class QualityGateCheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class QualityGateResult:
    gate_id: str
    stage: ConsultingStage
    mandatory: bool
    passed: bool
    checks: tuple[QualityGateCheckResult, ...]


# ---- Metrics ---------------------------------------------------------------


@dataclass(frozen=True)
class EngagementMetrics:
    workflow_completion: float
    stage_durations_s: dict
    quality_gate_pass_rate: float
    hypothesis_accuracy: float
    assumption_validation_rate: float
    evidence_coverage: float
    recommendation_confidence: float
    engagement_completeness: float
