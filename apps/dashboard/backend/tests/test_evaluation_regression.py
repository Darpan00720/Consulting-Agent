"""Tests for the 8-type Regression Detection engine."""

from __future__ import annotations

import dataclasses

from app.evaluation.benchmarking import compare
from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.models import ComparisonType, EvaluationMetric, RegressionType
from app.evaluation.regression import detect_regressions
from app.evaluation.replay import replay_case


def _current_and_baseline(case):
    replay = replay_case(case)
    current = evaluate_replay(case, replay)
    baseline = dataclasses.replace(current, id="eval-baseline")
    return replay, current, baseline


def test_no_regressions_between_identical_evaluations():
    case = all_benchmark_cases()[0]
    _replay, current, baseline = _current_and_baseline(case)
    comparison = compare(
        ComparisonType.CURRENT_VS_PREVIOUS_EXECUTION, current, baseline
    )
    assert detect_regressions(comparison) == ()


def test_metric_regressions_detected_for_each_mapped_type():
    case = all_benchmark_cases()[0]
    _replay, current, baseline = _current_and_baseline(case)
    degraded = {
        EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY: RegressionType.FRAMEWORK,
        EvaluationMetric.WORKFLOW_QUALITY: RegressionType.WORKFLOW,
        EvaluationMetric.RECOMMENDATION_QUALITY: RegressionType.RECOMMENDATION,
        EvaluationMetric.DELIVERABLE_QUALITY: RegressionType.DELIVERABLE,
        EvaluationMetric.TRACEABILITY: RegressionType.TRACEABILITY,
        EvaluationMetric.OVERALL_CONSULTING_SCORE: RegressionType.QUALITY,
    }
    strong_baseline_scores = tuple(
        dataclasses.replace(m, score=1.0) if m.metric in degraded else m
        for m in current.metric_scores
    )
    strong_baseline = dataclasses.replace(
        baseline, metric_scores=strong_baseline_scores
    )
    degraded_current_scores = tuple(
        dataclasses.replace(m, score=0.1) if m.metric in degraded else m
        for m in current.metric_scores
    )
    degraded_current = dataclasses.replace(
        current, metric_scores=degraded_current_scores
    )
    comparison = compare(
        ComparisonType.CURRENT_VS_PREVIOUS_EXECUTION, degraded_current, strong_baseline
    )
    findings = detect_regressions(comparison)
    found_types = {f.regression_type for f in findings}
    assert set(degraded.values()) <= found_types


def test_quality_gate_regression_flips_from_passing_to_failing():
    case = all_benchmark_cases()[0]
    _replay, current, baseline = _current_and_baseline(case)
    strong_scores = tuple(
        dataclasses.replace(m, score=1.0)
        if m.metric == EvaluationMetric.EVIDENCE_COVERAGE
        else m
        for m in current.metric_scores
    )
    strong_baseline = dataclasses.replace(baseline, metric_scores=strong_scores)
    weak_scores = tuple(
        dataclasses.replace(m, score=0.2)
        if m.metric == EvaluationMetric.EVIDENCE_COVERAGE
        else m
        for m in current.metric_scores
    )
    weak_current = dataclasses.replace(current, metric_scores=weak_scores)
    comparison = compare(
        ComparisonType.CURRENT_VS_PREVIOUS_RELEASE, weak_current, strong_baseline
    )
    findings = detect_regressions(comparison)
    assert any(f.regression_type == RegressionType.QUALITY_GATE for f in findings)


def test_performance_regression_only_reported_when_replays_supplied():
    case = all_benchmark_cases()[0]
    replay, current, baseline = _current_and_baseline(case)
    comparison = compare(
        ComparisonType.CURRENT_VS_PREVIOUS_EXECUTION, current, baseline
    )

    assert detect_regressions(comparison) == ()

    slow_replay = dataclasses.replace(
        replay, execution_time_s=replay.execution_time_s * 10 + 0.1
    )
    findings = detect_regressions(
        comparison, current_replay=slow_replay, baseline_replay=replay
    )
    assert any(f.regression_type == RegressionType.PERFORMANCE for f in findings)
