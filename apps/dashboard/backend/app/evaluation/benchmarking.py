"""Benchmarking engine (requester's "Benchmarking" section).

**One generic ``compare()`` for all 5 named comparison types.** Every one of
Current-vs-Previous-Release, -Gold-Standard, -Human-Reference, -Alternate-
Configuration, and -Previous-Execution reduces to the same mechanical
operation: diff two ``EvaluationResult``s metric by metric. What differs
between the 5 types is only WHICH evaluation the caller supplies as
``baseline`` — a labeling choice, not a different algorithm. This mirrors
``app.knowledge.quality``'s "generic check functions keyed by a taxonomy
string, never one function per named case" principle, applied to
comparisons instead of quality gates.
"""

from __future__ import annotations

from .errors import InsufficientDataError
from .models import (
    BenchmarkComparison,
    ComparisonType,
    EvaluationResult,
    MetricDelta,
    new_comparison_id,
)

_NOISE_EPSILON = 0.01


def compare(
    comparison_type: ComparisonType,
    current: EvaluationResult,
    baseline: EvaluationResult,
) -> BenchmarkComparison:
    """Diff ``current`` against ``baseline`` metric by metric. Raises
    ``InsufficientDataError`` only when the two evaluations scored different
    benchmark cases — comparing across cases is meaningless regardless of
    ``comparison_type``, since a lower score could simply mean a harder
    case, not a regression."""
    if current.case_id != baseline.case_id:
        raise InsufficientDataError(
            f"cannot compare evaluations of different cases: "
            f"{current.case_id!r} vs {baseline.case_id!r}"
        )

    baseline_by_metric = {m.metric: m for m in baseline.metric_scores}
    deltas: list[MetricDelta] = []
    improvements: list = []
    regressions: list = []

    for current_metric in current.metric_scores:
        baseline_metric = baseline_by_metric.get(current_metric.metric)
        if baseline_metric is None:
            continue
        delta = current_metric.score - baseline_metric.score
        improved = delta > _NOISE_EPSILON
        regressed = delta < -_NOISE_EPSILON
        if improved:
            improvements.append(current_metric.metric)
        elif regressed:
            regressions.append(current_metric.metric)
        deltas.append(
            MetricDelta(
                metric=current_metric.metric,
                current_score=current_metric.score,
                baseline_score=baseline_metric.score,
                delta=delta,
                improved=improved,
            )
        )

    return BenchmarkComparison(
        id=new_comparison_id(),
        comparison_type=comparison_type,
        current_evaluation_id=current.id,
        baseline_evaluation_id=baseline.id,
        deltas=tuple(deltas),
        improvements=tuple(improvements),
        regressions=tuple(regressions),
    )
