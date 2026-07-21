"""Core data types for the Consulting Evaluation, Benchmarking & Continuous
Improvement Platform.

Sits ABOVE ``app.consulting``/``app.knowledge``/``app.organization``/
``app.synthesis``/``app.deliverables`` as a sixth peer library: this package
answers HOW WELL StratAgent's consulting work performs. It performs no
consulting reasoning and never mutates a consulting artifact — every model
here is either an immutable benchmark fixture or a read-only measurement of
something the other five layers already produced.

Reuses ``app.consulting.models.EngagementCategory``, ``app.knowledge.
models.CompanySize``, and ``app.deliverables.models.DeliverableType`` rather
than inventing parallel taxonomies — "do not duplicate" applied a fifth
time.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.consulting.models import EngagementCategory
from app.deliverables.models import DeliverableType
from app.knowledge.models import CompanySize


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---- Case Library model (requester's "Case Library" section) --------------


class CaseDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass(frozen=True)
class BenchmarkCase:
    """Every field the requester named. Immutable — a content change is a
    new ``version``, never a mutation (the same convention every prior
    layer's catalog already established for its own entries)."""

    case_id: str
    title: str
    industry: str
    company_size: CompanySize
    region: str
    engagement_type: EngagementCategory
    difficulty: CaseDifficulty
    problem_statement: str
    background: str
    available_data: tuple[str, ...]
    ground_truth: str
    expected_frameworks: tuple[str, ...]
    expected_findings: tuple[str, ...]
    expected_recommendations: tuple[str, ...]
    expected_deliverables: tuple[DeliverableType, ...]
    reference_sources: tuple[str, ...]
    evaluation_version: str = "1.0.0"
    version: str = "1.0.0"
    owner: str = "StratAgent Evaluation Platform"
    tags: tuple[str, ...] = ()


# ---- Case Replay model (requester's "Case Replay Engine" section) --------


@dataclass(frozen=True)
class CaseReplayResult:
    """What one replay of a ``BenchmarkCase`` captured — the requester's
    named list, verbatim."""

    id: str
    case_id: str
    case_version: str
    engagement_id: str
    execution_time_s: float
    selected_frameworks: tuple[str, ...]
    role_assignments: tuple[str, ...]
    review_iterations: int
    findings: tuple[str, ...]
    recommendations: tuple[str, ...]
    deliverables_generated: tuple[DeliverableType, ...]
    quality_metrics: dict
    deterministic: bool
    deliverable_ids: tuple[str, ...] = ()
    replayed_at: float = field(default_factory=time.time)


def new_replay_id() -> str:
    return _new_id("replay")


# ---- Evaluation model (requester's "Evaluation Model" section) -----------


class EvaluationMetric(StrEnum):
    FRAMEWORK_SELECTION_ACCURACY = "framework_selection_accuracy"
    WORKFLOW_QUALITY = "workflow_quality"
    EVIDENCE_COVERAGE = "evidence_coverage"
    FINDING_QUALITY = "finding_quality"
    INSIGHT_QUALITY = "insight_quality"
    RECOMMENDATION_QUALITY = "recommendation_quality"
    BUSINESS_LOGIC = "business_logic"
    TRACEABILITY = "traceability"
    RISK_ASSESSMENT = "risk_assessment"
    TRADE_OFF_ANALYSIS = "trade_off_analysis"
    BUSINESS_IMPACT = "business_impact"
    DELIVERABLE_QUALITY = "deliverable_quality"
    EXECUTIVE_COMMUNICATION = "executive_communication"
    REVIEW_QUALITY = "review_quality"
    APPROVAL_QUALITY = "approval_quality"
    OVERALL_CONSULTING_SCORE = "overall_consulting_score"


@dataclass(frozen=True)
class MetricScore:
    metric: EvaluationMetric
    score: float
    confidence: float
    weight: float
    reason: str
    supporting_artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationResult:
    id: str
    case_id: str
    replay_id: str
    metric_scores: tuple[MetricScore, ...]
    overall_score: float
    evaluation_version: str
    evaluated_at: float = field(default_factory=time.time)

    def score_for(self, metric: EvaluationMetric) -> MetricScore | None:
        return next((m for m in self.metric_scores if m.metric is metric), None)


def new_evaluation_id() -> str:
    return _new_id("eval")


# ---- Benchmarking model (requester's "Benchmarking" section) --------------


class ComparisonType(StrEnum):
    CURRENT_VS_PREVIOUS_RELEASE = "current_vs_previous_release"
    CURRENT_VS_GOLD_STANDARD = "current_vs_gold_standard"
    CURRENT_VS_HUMAN_REFERENCE = "current_vs_human_reference"
    CURRENT_VS_ALTERNATE_CONFIGURATION = "current_vs_alternate_configuration"
    CURRENT_VS_PREVIOUS_EXECUTION = "current_vs_previous_execution"


@dataclass(frozen=True)
class MetricDelta:
    metric: EvaluationMetric
    current_score: float
    baseline_score: float
    delta: float
    improved: bool


@dataclass(frozen=True)
class BenchmarkComparison:
    id: str
    comparison_type: ComparisonType
    current_evaluation_id: str
    baseline_evaluation_id: str
    deltas: tuple[MetricDelta, ...]
    improvements: tuple[EvaluationMetric, ...]
    regressions: tuple[EvaluationMetric, ...]
    compared_at: float = field(default_factory=time.time)


def new_comparison_id() -> str:
    return _new_id("cmp")


# ---- Regression detection model --------------------------------------------


class RegressionType(StrEnum):
    QUALITY = "quality"
    FRAMEWORK = "framework"
    WORKFLOW = "workflow"
    RECOMMENDATION = "recommendation"
    DELIVERABLE = "deliverable"
    PERFORMANCE = "performance"
    TRACEABILITY = "traceability"
    QUALITY_GATE = "quality_gate"


class RegressionSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RegressionFinding:
    regression_type: RegressionType
    severity: RegressionSeverity
    detail: str
    current_value: float
    baseline_value: float
    metric: EvaluationMetric | None = None


# ---- Hallucination detection model ------------------------------------------


class HallucinationType(StrEnum):
    UNSUPPORTED_FINDING = "unsupported_finding"
    UNSUPPORTED_RECOMMENDATION = "unsupported_recommendation"
    INVENTED_EVIDENCE = "invented_evidence"
    INVENTED_METRIC = "invented_metric"
    CONTRADICTORY_REASONING = "contradictory_reasoning"
    BROKEN_TRACEABILITY = "broken_traceability"
    MISSING_ASSUMPTIONS = "missing_assumptions"
    UNSUPPORTED_CONCLUSION = "unsupported_conclusion"


@dataclass(frozen=True)
class HallucinationFinding:
    hallucination_type: HallucinationType
    ref_ids: tuple[str, ...]
    detail: str


# ---- Human evaluation model -------------------------------------------------


@dataclass(frozen=True)
class HumanReview:
    id: str
    reviewer: str
    expertise: str
    scores: dict
    comments: tuple[str, ...]
    confidence: float
    approval: bool
    recommendations: tuple[str, ...] = ()
    disagreements: tuple[str, ...] = ()
    reviewed_at: float = field(default_factory=time.time)


def new_review_id() -> str:
    return _new_id("hrev")


@dataclass
class ReviewPanel:
    reviews: list[HumanReview] = field(default_factory=list)


# ---- AI evaluation model ----------------------------------------------------


@dataclass(frozen=True)
class AIEvaluation:
    id: str
    provider: str
    scores: dict
    comments: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    improvement_suggestions: tuple[str, ...]
    confidence: float
    evaluated_at: float = field(default_factory=time.time)


def new_ai_evaluation_id() -> str:
    return _new_id("aieval")


# ---- Quality dashboard model -------------------------------------------------


@dataclass(frozen=True)
class DashboardSnapshot:
    id: str
    consulting_score_trend: tuple[float, ...]
    framework_accuracy_trend: tuple[float, ...]
    recommendation_quality_trend: tuple[float, ...]
    deliverable_quality_trend: tuple[float, ...]
    review_quality_trend: tuple[float, ...]
    approval_latency_avg_s: float
    execution_duration_avg_s: float
    regression_count: int
    hallucination_rate: float
    benchmark_trend: dict
    customer_acceptance_rate: float | None = None
    generated_at: float = field(default_factory=time.time)


def new_dashboard_id() -> str:
    return _new_id("dash")


# ---- Continuous improvement model -------------------------------------------


@dataclass(frozen=True)
class ImprovementRecommendation:
    id: str
    category: str
    description: str
    frequency: int
    priority: int
    supporting_evidence: tuple[str, ...] = ()


def new_improvement_id() -> str:
    return _new_id("improve")


# ---- Versioning model --------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkVersionInfo:
    case_id: str
    version: str
    deprecated: bool
    replaced_by: str | None
    reason: str = ""
    created_at: float = field(default_factory=time.time)
