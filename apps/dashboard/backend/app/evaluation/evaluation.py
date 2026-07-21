"""The 16-metric Evaluation Model (requester's "Evaluation Model" section).

Scores a ``CaseReplayResult`` against the ``BenchmarkCase`` it replayed.
**Generic scoring formulas, never consulting judgment** — the same
"structure/measure, never invent" boundary every prior layer's quality.py
already drew: every metric here compares real replay output to real case
ground truth (set overlap, ratio, or a synthesis-quality score the replay
already computed), never a subjective read of content quality.

**Honest, not padded, where the signal is thin.** ``CaseReplayResult`` (by
design) doesn't carry Insight/Opportunity nodes (``BenchmarkCase`` has no
``expected_insights`` field in the requester's own 17-field schema) and the
deterministic replay never invokes governance approval. Rather than fabricate
a strong score from data that doesn't exist, ``INSIGHT_QUALITY`` and
``APPROVAL_QUALITY`` are scored with an explicitly LOW ``confidence`` and a
``reason`` that says so — the same honesty this platform's design principles
already demand of a human reviewer.
"""

from __future__ import annotations

from .models import (
    BenchmarkCase,
    CaseReplayResult,
    EvaluationMetric,
    EvaluationResult,
    MetricScore,
    new_evaluation_id,
)

_RISK_FRAMEWORKS = frozenset(
    {
        "risk_matrix",
        "failure_mode_analysis",
        "scenario_planning",
        "business_continuity",
        "dependency_mapping",
        "risk_heatmap",
        "mitigation_planning",
    }
)

_WEIGHTS: dict[EvaluationMetric, float] = {
    EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY: 0.10,
    EvaluationMetric.WORKFLOW_QUALITY: 0.05,
    EvaluationMetric.EVIDENCE_COVERAGE: 0.08,
    EvaluationMetric.FINDING_QUALITY: 0.07,
    EvaluationMetric.INSIGHT_QUALITY: 0.03,
    EvaluationMetric.RECOMMENDATION_QUALITY: 0.10,
    EvaluationMetric.BUSINESS_LOGIC: 0.08,
    EvaluationMetric.TRACEABILITY: 0.10,
    EvaluationMetric.RISK_ASSESSMENT: 0.05,
    EvaluationMetric.TRADE_OFF_ANALYSIS: 0.07,
    EvaluationMetric.BUSINESS_IMPACT: 0.07,
    EvaluationMetric.DELIVERABLE_QUALITY: 0.08,
    EvaluationMetric.EXECUTIVE_COMMUNICATION: 0.05,
    EvaluationMetric.REVIEW_QUALITY: 0.04,
    EvaluationMetric.APPROVAL_QUALITY: 0.03,
}


def _f1(expected: frozenset, actual: frozenset) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    overlap = expected & actual
    precision = len(overlap) / len(actual)
    recall = len(overlap) / len(expected)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _framework_selection_accuracy(
    case: BenchmarkCase, replay: CaseReplayResult
) -> MetricScore:
    expected = frozenset(case.expected_frameworks)
    actual = frozenset(replay.selected_frameworks)
    score = _f1(expected, actual)
    return MetricScore(
        metric=EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY,
        score=score,
        confidence=0.9,
        weight=_WEIGHTS[EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY],
        reason=(
            f"F1 over expected ({len(expected)}) vs selected ({len(actual)}) "
            "framework ids"
        ),
        supporting_artifacts=tuple(sorted(expected | actual)),
    )


def _workflow_quality(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    stages_fired = (
        bool(replay.selected_frameworks),
        bool(replay.role_assignments),
        replay.review_iterations > 0,
        bool(replay.deliverables_generated),
    )
    score = sum(stages_fired) / len(stages_fired)
    return MetricScore(
        metric=EvaluationMetric.WORKFLOW_QUALITY,
        score=score,
        confidence=0.5,
        weight=_WEIGHTS[EvaluationMetric.WORKFLOW_QUALITY],
        reason=(
            f"{sum(stages_fired)}/{len(stages_fired)} lifecycle stages "
            "(knowledge, organization, review, deliverables) produced output; "
            "this proxy does not yet track full 10-stage ConsultingStage "
            "progression"
        ),
        supporting_artifacts=(replay.engagement_id,),
    )


def _evidence_coverage(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = replay.quality_metrics.get("evidence_coverage", 0.0)
    return MetricScore(
        metric=EvaluationMetric.EVIDENCE_COVERAGE,
        score=score,
        confidence=0.9,
        weight=_WEIGHTS[EvaluationMetric.EVIDENCE_COVERAGE],
        reason="taken directly from app.synthesis.quality's evidence_coverage check",
        supporting_artifacts=replay.findings,
    )


def _finding_quality(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    expected = frozenset(case.expected_findings)
    actual = frozenset(replay.findings)
    score = _f1(expected, actual)
    return MetricScore(
        metric=EvaluationMetric.FINDING_QUALITY,
        score=score,
        confidence=0.6,
        weight=_WEIGHTS[EvaluationMetric.FINDING_QUALITY],
        reason=(
            "F1 of replayed finding statements against the case's recorded "
            "expected_findings — a content-string match, not a judgment of "
            "analytical depth"
        ),
        supporting_artifacts=tuple(sorted(expected | actual)),
    )


def _insight_quality(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = replay.quality_metrics.get("logical_consistency", 0.0)
    return MetricScore(
        metric=EvaluationMetric.INSIGHT_QUALITY,
        score=score,
        confidence=0.3,
        weight=_WEIGHTS[EvaluationMetric.INSIGHT_QUALITY],
        reason=(
            "BenchmarkCase has no expected_insights field, so there is no "
            "ground truth for this dimension; approximated via the "
            "synthesis chain's logical_consistency score — LOW confidence, "
            "deliberately"
        ),
    )


def _recommendation_quality(
    case: BenchmarkCase, replay: CaseReplayResult
) -> MetricScore:
    expected = frozenset(case.expected_recommendations)
    actual = frozenset(replay.recommendations)
    overlap_score = _f1(expected, actual)
    completeness = replay.quality_metrics.get("recommendation_completeness", 0.0)
    score = (overlap_score + completeness) / 2
    return MetricScore(
        metric=EvaluationMetric.RECOMMENDATION_QUALITY,
        score=score,
        confidence=0.7,
        weight=_WEIGHTS[EvaluationMetric.RECOMMENDATION_QUALITY],
        reason="average of recommendation-statement F1 and structural completeness",
        supporting_artifacts=tuple(sorted(expected | actual)),
    )


def _business_logic(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = replay.quality_metrics.get("logical_consistency", 0.0)
    return MetricScore(
        metric=EvaluationMetric.BUSINESS_LOGIC,
        score=score,
        confidence=0.8,
        weight=_WEIGHTS[EvaluationMetric.BUSINESS_LOGIC],
        reason="taken directly from app.synthesis.quality's logical_consistency check",
    )


def _traceability(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = replay.quality_metrics.get("traceability", 0.0)
    return MetricScore(
        metric=EvaluationMetric.TRACEABILITY,
        score=score,
        confidence=0.9,
        weight=_WEIGHTS[EvaluationMetric.TRACEABILITY],
        reason="taken directly from app.synthesis.quality's traceability check",
    )


def _risk_assessment(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    used_risk_framework = bool(set(replay.selected_frameworks) & _RISK_FRAMEWORKS)
    score = 1.0 if used_risk_framework else 0.4
    return MetricScore(
        metric=EvaluationMetric.RISK_ASSESSMENT,
        score=score,
        confidence=0.5,
        weight=_WEIGHTS[EvaluationMetric.RISK_ASSESSMENT],
        reason=(
            "a dedicated risk framework was selected"
            if used_risk_framework
            else "no dedicated risk framework was selected; risk may still be "
            "captured in recommendation-level fields not independently "
            "verifiable from a CaseReplayResult"
        ),
    )


def _trade_off_analysis(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = replay.quality_metrics.get("trade_off_analysis", 0.0)
    return MetricScore(
        metric=EvaluationMetric.TRADE_OFF_ANALYSIS,
        score=score,
        confidence=0.9,
        weight=_WEIGHTS[EvaluationMetric.TRADE_OFF_ANALYSIS],
        reason="taken directly from app.synthesis.quality's trade_off_analysis check",
    )


def _business_impact(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = replay.quality_metrics.get("business_impact", 0.0)
    return MetricScore(
        metric=EvaluationMetric.BUSINESS_IMPACT,
        score=score,
        confidence=0.9,
        weight=_WEIGHTS[EvaluationMetric.BUSINESS_IMPACT],
        reason="taken directly from app.synthesis.quality's business_impact check",
    )


def _deliverable_coverage(case: BenchmarkCase, replay: CaseReplayResult) -> float:
    expected = frozenset(case.expected_deliverables)
    actual = frozenset(replay.deliverables_generated)
    return _f1(expected, actual)


def _deliverable_quality(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = _deliverable_coverage(case, replay)
    return MetricScore(
        metric=EvaluationMetric.DELIVERABLE_QUALITY,
        score=score,
        confidence=0.7,
        weight=_WEIGHTS[EvaluationMetric.DELIVERABLE_QUALITY],
        reason="F1 of generated vs expected deliverable types",
        supporting_artifacts=tuple(d.value for d in replay.deliverables_generated),
    )


def _executive_communication(
    case: BenchmarkCase, replay: CaseReplayResult
) -> MetricScore:
    coverage = _deliverable_coverage(case, replay)
    complete = len(replay.deliverable_ids) == len(case.expected_deliverables)
    score = coverage if complete else coverage * 0.5
    return MetricScore(
        metric=EvaluationMetric.EXECUTIVE_COMMUNICATION,
        score=score,
        confidence=0.5,
        weight=_WEIGHTS[EvaluationMetric.EXECUTIVE_COMMUNICATION],
        reason=(
            "deliverable-type coverage, penalized if not every expected "
            "deliverable actually produced a generated artifact id; does not "
            "assess audience-specific tone"
        ),
    )


def _review_quality(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    score = 1.0 if replay.review_iterations > 0 else 0.0
    return MetricScore(
        metric=EvaluationMetric.REVIEW_QUALITY,
        score=score,
        confidence=0.5,
        weight=_WEIGHTS[EvaluationMetric.REVIEW_QUALITY],
        reason=(
            f"{replay.review_iterations} review iteration(s) recorded; "
            "replay only exercises a single PEER-stage pass, not the full "
            "Peer -> Manager -> Partner -> Executive chain"
        ),
    )


def _approval_quality(case: BenchmarkCase, replay: CaseReplayResult) -> MetricScore:
    return MetricScore(
        metric=EvaluationMetric.APPROVAL_QUALITY,
        score=0.0,
        confidence=0.4,
        weight=_WEIGHTS[EvaluationMetric.APPROVAL_QUALITY],
        reason=(
            "deterministic replay does not invoke app.organization.governance "
            "approval; every recommendation remains PENDING — a known scope "
            "gap, not a quality failure of the replayed content"
        ),
    )


_SCORERS = (
    _framework_selection_accuracy,
    _workflow_quality,
    _evidence_coverage,
    _finding_quality,
    _insight_quality,
    _recommendation_quality,
    _business_logic,
    _traceability,
    _risk_assessment,
    _trade_off_analysis,
    _business_impact,
    _deliverable_quality,
    _executive_communication,
    _review_quality,
    _approval_quality,
)


def evaluate_replay(case: BenchmarkCase, replay: CaseReplayResult) -> EvaluationResult:
    """Score a completed replay against the case it replayed. Never raises:
    every metric above degrades to a low score with a stated reason rather
    than an exception, since a poor evaluation is a normal, expected
    outcome — this platform's entire purpose is to be able to report one."""
    metric_scores = [scorer(case, replay) for scorer in _SCORERS]
    weighted_sum = sum(m.score * m.weight for m in metric_scores)
    overall = MetricScore(
        metric=EvaluationMetric.OVERALL_CONSULTING_SCORE,
        score=weighted_sum,
        confidence=sum(m.confidence * m.weight for m in metric_scores),
        weight=1.0,
        reason="weighted average of the 15 named metrics above",
        supporting_artifacts=tuple(m.metric.value for m in metric_scores),
    )
    metric_scores.append(overall)
    return EvaluationResult(
        id=new_evaluation_id(),
        case_id=case.case_id,
        replay_id=replay.id,
        metric_scores=tuple(metric_scores),
        overall_score=weighted_sum,
        evaluation_version=case.evaluation_version,
    )
