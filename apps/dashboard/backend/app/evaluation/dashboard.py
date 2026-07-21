"""Quality Dashboard (requester's "Quality Dashboards" section):
longitudinal aggregation over evaluation/replay history. Every trend below
is a real reduction over caller-supplied ``EvaluationResult``/
``CaseReplayResult`` history — this module computes no new judgment, only
summarizes judgments the evaluation/regression/hallucination engines
already produced.

Evaluations are sorted by ``evaluated_at`` before building trends, so the
resulting sequences are genuinely longitudinal regardless of the order the
caller happened to pass them in.

**One honest gap, stated rather than papered over:** ``approval_latency_avg_s``
is always ``0.0`` today — no model in this platform yet threads a governance
approval timestamp through a ``CaseReplayResult`` (the deterministic replay
engine doesn't invoke ``app.organization.governance`` at all, the same known
scope gap ``app.evaluation.evaluation.APPROVAL_QUALITY`` already documents).
This field is reserved for when that data exists, not silently omitted.
"""

from __future__ import annotations

from .models import (
    CaseReplayResult,
    DashboardSnapshot,
    EvaluationMetric,
    EvaluationResult,
    HallucinationFinding,
    RegressionFinding,
    new_dashboard_id,
)

_TREND_METRICS = (
    ("consulting_score_trend", EvaluationMetric.OVERALL_CONSULTING_SCORE),
    ("framework_accuracy_trend", EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY),
    ("recommendation_quality_trend", EvaluationMetric.RECOMMENDATION_QUALITY),
    ("deliverable_quality_trend", EvaluationMetric.DELIVERABLE_QUALITY),
    ("review_quality_trend", EvaluationMetric.REVIEW_QUALITY),
)


def _trend_for(
    sorted_evaluations: tuple[EvaluationResult, ...], metric: EvaluationMetric
) -> tuple[float, ...]:
    values = []
    for evaluation in sorted_evaluations:
        score = evaluation.score_for(metric)
        if score is not None:
            values.append(score.score)
    return tuple(values)


def build_dashboard_snapshot(
    evaluations: tuple[EvaluationResult, ...],
    replays: tuple[CaseReplayResult, ...],
    *,
    regression_findings: tuple[RegressionFinding, ...] = (),
    hallucination_findings_by_replay: tuple[tuple[HallucinationFinding, ...], ...] = (),
    customer_acceptance_rate: float | None = None,
) -> DashboardSnapshot:
    """Never raises: an empty history produces a snapshot of all-empty
    trends, a reportable (if uninteresting) state, not an error."""
    sorted_evaluations = tuple(sorted(evaluations, key=lambda e: e.evaluated_at))
    trends = {
        field_name: _trend_for(sorted_evaluations, metric)
        for field_name, metric in _TREND_METRICS
    }

    execution_times = [r.execution_time_s for r in replays]
    execution_duration_avg_s = (
        sum(execution_times) / len(execution_times) if execution_times else 0.0
    )

    hallucinating_replays = sum(1 for f in hallucination_findings_by_replay if f)
    hallucination_rate = (
        hallucinating_replays / len(hallucination_findings_by_replay)
        if hallucination_findings_by_replay
        else 0.0
    )

    benchmark_trend = {
        "evaluation_count": len(sorted_evaluations),
        "first_overall_score": (
            sorted_evaluations[0].overall_score if sorted_evaluations else None
        ),
        "last_overall_score": (
            sorted_evaluations[-1].overall_score if sorted_evaluations else None
        ),
        "delta": (
            sorted_evaluations[-1].overall_score - sorted_evaluations[0].overall_score
            if len(sorted_evaluations) >= 2
            else 0.0
        ),
    }

    return DashboardSnapshot(
        id=new_dashboard_id(),
        consulting_score_trend=trends["consulting_score_trend"],
        framework_accuracy_trend=trends["framework_accuracy_trend"],
        recommendation_quality_trend=trends["recommendation_quality_trend"],
        deliverable_quality_trend=trends["deliverable_quality_trend"],
        review_quality_trend=trends["review_quality_trend"],
        approval_latency_avg_s=0.0,
        execution_duration_avg_s=execution_duration_avg_s,
        regression_count=len(regression_findings),
        hallucination_rate=hallucination_rate,
        benchmark_trend=benchmark_trend,
        customer_acceptance_rate=customer_acceptance_rate,
    )
