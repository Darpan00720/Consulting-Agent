"""Tests for app/evaluation/models.py — every dataclass/enum constructs
with real values from the layers it reuses."""

from __future__ import annotations

from app.consulting.models import EngagementCategory
from app.deliverables.models import DeliverableType
from app.evaluation.models import (
    AIEvaluation,
    BenchmarkCase,
    BenchmarkComparison,
    BenchmarkVersionInfo,
    CaseDifficulty,
    CaseReplayResult,
    ComparisonType,
    DashboardSnapshot,
    EvaluationMetric,
    EvaluationResult,
    HallucinationFinding,
    HallucinationType,
    HumanReview,
    ImprovementRecommendation,
    MetricDelta,
    MetricScore,
    RegressionFinding,
    RegressionSeverity,
    RegressionType,
    ReviewPanel,
)
from app.knowledge.models import CompanySize


def _case() -> BenchmarkCase:
    return BenchmarkCase(
        case_id="c1",
        title="t",
        industry="software",
        company_size=CompanySize.MIDMARKET,
        region="NA",
        engagement_type=EngagementCategory.MARKET_ENTRY,
        difficulty=CaseDifficulty.MEDIUM,
        problem_statement="p",
        background="b",
        available_data=("d1",),
        ground_truth="g",
        expected_frameworks=("five_forces",),
        expected_findings=("f1",),
        expected_recommendations=("r1",),
        expected_deliverables=(DeliverableType.EXECUTIVE_SUMMARY,),
        reference_sources=("s1",),
    )


def test_benchmark_case_constructs_with_real_enums():
    case = _case()
    assert case.version == "1.0.0"
    assert case.evaluation_version == "1.0.0"
    assert case.company_size is CompanySize.MIDMARKET


def test_all_16_evaluation_metrics_are_named():
    assert len(list(EvaluationMetric)) == 16


def test_all_5_comparison_types_are_named():
    assert len(list(ComparisonType)) == 5


def test_all_8_regression_types_are_named():
    assert len(list(RegressionType)) == 8


def test_all_8_hallucination_types_are_named():
    assert len(list(HallucinationType)) == 8


def test_metric_score_and_evaluation_result_roundtrip():
    score = MetricScore(
        metric=EvaluationMetric.TRACEABILITY,
        score=0.9,
        confidence=0.8,
        weight=0.1,
        reason="r",
    )
    result = EvaluationResult(
        id="eval-1",
        case_id="c1",
        replay_id="replay-1",
        metric_scores=(score,),
        overall_score=0.9,
        evaluation_version="1.0.0",
    )
    assert result.score_for(EvaluationMetric.TRACEABILITY) is score
    assert result.score_for(EvaluationMetric.BUSINESS_LOGIC) is None


def test_benchmark_comparison_and_metric_delta_construct():
    delta = MetricDelta(
        metric=EvaluationMetric.OVERALL_CONSULTING_SCORE,
        current_score=0.5,
        baseline_score=0.7,
        delta=-0.2,
        improved=False,
    )
    comparison = BenchmarkComparison(
        id="cmp-1",
        comparison_type=ComparisonType.CURRENT_VS_PREVIOUS_RELEASE,
        current_evaluation_id="eval-1",
        baseline_evaluation_id="eval-0",
        deltas=(delta,),
        improvements=(),
        regressions=(EvaluationMetric.OVERALL_CONSULTING_SCORE,),
    )
    assert comparison.regressions == (EvaluationMetric.OVERALL_CONSULTING_SCORE,)


def test_regression_and_hallucination_findings_construct():
    reg = RegressionFinding(
        regression_type=RegressionType.QUALITY,
        severity=RegressionSeverity.HIGH,
        detail="dropped",
        current_value=0.5,
        baseline_value=0.8,
    )
    assert reg.metric is None
    hall = HallucinationFinding(
        hallucination_type=HallucinationType.INVENTED_EVIDENCE,
        ref_ids=("x",),
        detail="d",
    )
    assert hall.ref_ids == ("x",)


def test_human_review_and_review_panel():
    panel = ReviewPanel()
    review = HumanReview(
        id="hrev-1",
        reviewer="alice",
        expertise="partner",
        scores={"traceability": 0.9},
        comments=("good",),
        confidence=0.8,
        approval=True,
    )
    panel.reviews.append(review)
    assert panel.reviews[0].approval is True


def test_ai_evaluation_dashboard_improvement_version_construct():
    ai = AIEvaluation(
        id="ai-1",
        provider="claude",
        scores={"traceability": 0.9},
        comments=(),
        strengths=(),
        weaknesses=(),
        improvement_suggestions=(),
        confidence=0.7,
    )
    assert ai.provider == "claude"

    snapshot = DashboardSnapshot(
        id="dash-1",
        consulting_score_trend=(0.9,),
        framework_accuracy_trend=(1.0,),
        recommendation_quality_trend=(0.8,),
        deliverable_quality_trend=(0.7,),
        review_quality_trend=(1.0,),
        approval_latency_avg_s=0.0,
        execution_duration_avg_s=0.01,
        regression_count=0,
        hallucination_rate=0.0,
        benchmark_trend={},
    )
    assert snapshot.regression_count == 0

    improvement = ImprovementRecommendation(
        id="improve-1",
        category="weak_framework",
        description="d",
        frequency=3,
        priority=3,
    )
    assert improvement.priority == 3

    version_info = BenchmarkVersionInfo(
        case_id="c1", version="1.0.0", deprecated=False, replaced_by=None
    )
    assert version_info.deprecated is False


def test_case_replay_result_constructs():
    result = CaseReplayResult(
        id="replay-1",
        case_id="c1",
        case_version="1.0.0",
        engagement_id="e1",
        execution_time_s=0.01,
        selected_frameworks=("five_forces",),
        role_assignments=("engagement_manager",),
        review_iterations=1,
        findings=("f1",),
        recommendations=("r1",),
        deliverables_generated=(DeliverableType.EXECUTIVE_SUMMARY,),
        quality_metrics={"traceability": 1.0},
        deterministic=True,
    )
    assert result.deterministic is True
    assert result.deliverable_ids == ()
