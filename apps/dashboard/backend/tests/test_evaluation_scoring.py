"""Tests for the 16-metric Evaluation Model."""

from __future__ import annotations

import dataclasses

import pytest

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.models import EvaluationMetric
from app.evaluation.replay import replay_case


@pytest.mark.parametrize("case", all_benchmark_cases(), ids=lambda c: c.case_id)
def test_every_case_scores_all_16_metrics_in_range(case):
    replay = replay_case(case)
    result = evaluate_replay(case, replay)
    assert len(result.metric_scores) == 16
    metrics_seen = {m.metric for m in result.metric_scores}
    assert metrics_seen == set(EvaluationMetric)
    for score in result.metric_scores:
        assert 0.0 <= score.score <= 1.0, score
        assert 0.0 <= score.confidence <= 1.0, score
        assert score.reason


def test_overall_consulting_score_matches_weighted_sum():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    result = evaluate_replay(case, replay)
    overall = result.score_for(EvaluationMetric.OVERALL_CONSULTING_SCORE)
    assert overall.score == pytest.approx(result.overall_score)
    non_overall = [
        m
        for m in result.metric_scores
        if m.metric != EvaluationMetric.OVERALL_CONSULTING_SCORE
    ]
    expected = sum(m.score * m.weight for m in non_overall)
    assert overall.score == pytest.approx(expected)


def test_framework_selection_accuracy_is_zero_when_nothing_matches():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    bad_replay = dataclasses.replace(replay, selected_frameworks=("totally_unrelated",))
    result = evaluate_replay(case, bad_replay)
    score = result.score_for(EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY)
    assert score.score == 0.0


def test_approval_quality_is_always_zero_and_low_confidence():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    result = evaluate_replay(case, replay)
    score = result.score_for(EvaluationMetric.APPROVAL_QUALITY)
    assert score.score == 0.0
    assert score.confidence < 0.5


def test_insight_quality_uses_low_confidence_proxy():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    result = evaluate_replay(case, replay)
    score = result.score_for(EvaluationMetric.INSIGHT_QUALITY)
    assert score.confidence <= 0.4
