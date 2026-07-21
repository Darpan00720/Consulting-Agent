"""Tests for the generic ``compare()`` benchmarking engine."""

from __future__ import annotations

import dataclasses

import pytest

from app.evaluation.benchmarking import compare
from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.errors import InsufficientDataError
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.models import ComparisonType, EvaluationMetric
from app.evaluation.replay import replay_case


def _evaluation_for(case):
    return evaluate_replay(case, replay_case(case))


def test_compare_reports_no_regressions_between_identical_evaluations():
    case = all_benchmark_cases()[0]
    current = _evaluation_for(case)
    baseline = dataclasses.replace(current, id="eval-baseline")
    comparison = compare(
        ComparisonType.CURRENT_VS_PREVIOUS_EXECUTION, current, baseline
    )
    assert comparison.regressions == ()
    assert comparison.improvements == ()
    assert len(comparison.deltas) == 16


def test_compare_detects_a_regression_when_current_is_worse():
    case = all_benchmark_cases()[0]
    baseline = _evaluation_for(case)
    degraded_scores = tuple(
        dataclasses.replace(m, score=0.1)
        if m.metric == EvaluationMetric.TRACEABILITY
        else m
        for m in baseline.metric_scores
    )
    current = dataclasses.replace(
        baseline, id="eval-current", metric_scores=degraded_scores
    )
    comparison = compare(ComparisonType.CURRENT_VS_PREVIOUS_RELEASE, current, baseline)
    assert EvaluationMetric.TRACEABILITY in comparison.regressions


def test_compare_detects_an_improvement_when_current_is_better():
    case = all_benchmark_cases()[0]
    current = _evaluation_for(case)
    worse_scores = tuple(
        dataclasses.replace(m, score=max(0.0, m.score - 0.5))
        if m.metric == EvaluationMetric.RECOMMENDATION_QUALITY
        else m
        for m in current.metric_scores
    )
    baseline = dataclasses.replace(
        current, id="eval-baseline", metric_scores=worse_scores
    )
    comparison = compare(ComparisonType.CURRENT_VS_GOLD_STANDARD, current, baseline)
    assert EvaluationMetric.RECOMMENDATION_QUALITY in comparison.improvements


def test_compare_rejects_mismatched_cases():
    case_a, case_b = all_benchmark_cases()[0], all_benchmark_cases()[1]
    eval_a = _evaluation_for(case_a)
    eval_b = _evaluation_for(case_b)
    with pytest.raises(InsufficientDataError):
        compare(ComparisonType.CURRENT_VS_ALTERNATE_CONFIGURATION, eval_a, eval_b)


@pytest.mark.parametrize("comparison_type", list(ComparisonType))
def test_every_comparison_type_is_accepted_by_compare(comparison_type):
    case = all_benchmark_cases()[0]
    current = _evaluation_for(case)
    baseline = dataclasses.replace(current, id="eval-baseline")
    comparison = compare(comparison_type, current, baseline)
    assert comparison.comparison_type is comparison_type
