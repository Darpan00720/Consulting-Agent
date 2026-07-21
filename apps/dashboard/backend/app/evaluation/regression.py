"""Regression Detection (requester's "Regression Detection" section, 8
named types). Every check below reads directly from a ``BenchmarkComparison``
that ``app.evaluation.benchmarking.compare`` already produced — this module
never recomputes scores, it only classifies a comparison's own deltas into
the 8 named regression categories the requester asked for, plus (only when
the two raw ``CaseReplayResult``s are supplied) a performance check that has
no corresponding ``EvaluationMetric`` to read a delta from.
"""

from __future__ import annotations

from .models import (
    BenchmarkComparison,
    CaseReplayResult,
    EvaluationMetric,
    MetricDelta,
    RegressionFinding,
    RegressionSeverity,
    RegressionType,
)

_QUALITY_GATE_THRESHOLD = 0.7
_PERFORMANCE_SLOWDOWN_RATIO = 1.2  # >20% slower counts as a regression

_REGRESSION_METRIC = {
    RegressionType.QUALITY: EvaluationMetric.OVERALL_CONSULTING_SCORE,
    RegressionType.FRAMEWORK: EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY,
    RegressionType.WORKFLOW: EvaluationMetric.WORKFLOW_QUALITY,
    RegressionType.RECOMMENDATION: EvaluationMetric.RECOMMENDATION_QUALITY,
    RegressionType.DELIVERABLE: EvaluationMetric.DELIVERABLE_QUALITY,
    RegressionType.TRACEABILITY: EvaluationMetric.TRACEABILITY,
}


def _severity_for(delta: float) -> RegressionSeverity:
    magnitude = abs(delta)
    if magnitude >= 0.3:
        return RegressionSeverity.CRITICAL
    if magnitude >= 0.15:
        return RegressionSeverity.HIGH
    if magnitude >= 0.05:
        return RegressionSeverity.MEDIUM
    return RegressionSeverity.LOW


def _delta_for(
    comparison: BenchmarkComparison, metric: EvaluationMetric
) -> MetricDelta | None:
    return next((d for d in comparison.deltas if d.metric is metric), None)


def _metric_regression(
    comparison: BenchmarkComparison, regression_type: RegressionType
) -> RegressionFinding | None:
    metric = _REGRESSION_METRIC[regression_type]
    if metric not in comparison.regressions:
        return None
    delta = _delta_for(comparison, metric)
    if delta is None:
        return None
    return RegressionFinding(
        regression_type=regression_type,
        severity=_severity_for(delta.delta),
        detail=(
            f"{metric.value} dropped from {delta.baseline_score:.3f} "
            f"to {delta.current_score:.3f}"
        ),
        current_value=delta.current_score,
        baseline_value=delta.baseline_score,
        metric=metric,
    )


def _quality_gate_regression(
    comparison: BenchmarkComparison,
) -> RegressionFinding | None:
    """A metric that PASSED a nominal quality gate in the baseline
    (score >= threshold) but FAILS it now — a flip, not just a decline, and
    reportable even if the raw delta is too small to appear in
    ``comparison.regressions``."""
    for delta in comparison.deltas:
        was_passing = delta.baseline_score >= _QUALITY_GATE_THRESHOLD
        now_failing = delta.current_score < _QUALITY_GATE_THRESHOLD
        if was_passing and now_failing:
            return RegressionFinding(
                regression_type=RegressionType.QUALITY_GATE,
                severity=_severity_for(delta.delta),
                detail=(
                    f"{delta.metric.value} fell below the "
                    f"{_QUALITY_GATE_THRESHOLD} quality gate threshold "
                    f"({delta.baseline_score:.3f} -> {delta.current_score:.3f})"
                ),
                current_value=delta.current_score,
                baseline_value=delta.baseline_score,
                metric=delta.metric,
            )
    return None


def _performance_regression(
    current_replay: CaseReplayResult | None, baseline_replay: CaseReplayResult | None
) -> RegressionFinding | None:
    if current_replay is None or baseline_replay is None:
        return None
    if baseline_replay.execution_time_s <= 0:
        return None
    ratio = current_replay.execution_time_s / baseline_replay.execution_time_s
    if ratio < _PERFORMANCE_SLOWDOWN_RATIO:
        return None
    return RegressionFinding(
        regression_type=RegressionType.PERFORMANCE,
        severity=_severity_for(ratio - 1.0),
        detail=(
            f"replay execution time increased {ratio:.2f}x "
            f"({baseline_replay.execution_time_s:.4f}s -> "
            f"{current_replay.execution_time_s:.4f}s)"
        ),
        current_value=current_replay.execution_time_s,
        baseline_value=baseline_replay.execution_time_s,
    )


def detect_regressions(
    comparison: BenchmarkComparison,
    *,
    current_replay: CaseReplayResult | None = None,
    baseline_replay: CaseReplayResult | None = None,
) -> tuple[RegressionFinding, ...]:
    """Never raises: an absence of regressions is a normal, good outcome
    (empty tuple), not an error. The performance check is skipped (not
    reported as "no regression") when the raw replay pair isn't supplied,
    since execution time has no corresponding ``EvaluationMetric`` to read
    a delta from."""
    findings = [
        _metric_regression(comparison, regression_type)
        for regression_type in _REGRESSION_METRIC
    ]
    findings.append(_quality_gate_regression(comparison))
    findings.append(_performance_regression(current_replay, baseline_replay))
    return tuple(f for f in findings if f is not None)
