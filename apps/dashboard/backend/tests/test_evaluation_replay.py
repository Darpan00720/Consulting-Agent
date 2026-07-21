"""Tests for the Case Replay Engine — chains real W7-W11 layers end to end."""

from __future__ import annotations

import dataclasses

import pytest

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.errors import ReplayFailedError
from app.evaluation.models import CaseReplayResult
from app.evaluation.replay import replay_case, replay_case_with_state
from app.synthesis.state import SynthesisState


@pytest.mark.parametrize("case", all_benchmark_cases(), ids=lambda c: c.case_id)
def test_every_benchmark_case_replays_successfully(case):
    result = replay_case(case)
    assert isinstance(result, CaseReplayResult)
    assert result.case_id == case.case_id
    assert set(case.expected_frameworks) <= set(result.selected_frameworks)
    assert result.role_assignments
    assert result.review_iterations >= 1
    assert set(result.deliverables_generated) == set(case.expected_deliverables)
    assert result.quality_metrics["synthesis_overall_score"] > 0.9


def test_replay_is_deterministic_across_runs():
    case = all_benchmark_cases()[0]
    r1 = replay_case(case)
    r2 = replay_case(case)
    assert r1.selected_frameworks == r2.selected_frameworks
    assert r1.role_assignments == r2.role_assignments
    assert r1.quality_metrics == r2.quality_metrics


def test_replay_rejects_non_deterministic_mode():
    case = all_benchmark_cases()[0]
    with pytest.raises(ReplayFailedError):
        replay_case(case, deterministic=False)


def test_replay_rejects_case_with_no_expected_findings():
    case = dataclasses.replace(all_benchmark_cases()[0], expected_findings=())
    with pytest.raises(ReplayFailedError):
        replay_case(case)


def test_replay_rejects_case_with_no_expected_recommendations():
    case = dataclasses.replace(all_benchmark_cases()[0], expected_recommendations=())
    with pytest.raises(ReplayFailedError):
        replay_case(case)


def test_replay_rejects_framework_missing_unmet_dependency():
    case = dataclasses.replace(
        all_benchmark_cases()[0], expected_frameworks=("swot",)
    )  # swot depends on five_forces/pestle, neither present
    with pytest.raises(ReplayFailedError):
        replay_case(case)


def test_replay_case_with_state_exposes_live_synthesis_state():
    case = all_benchmark_cases()[0]
    result, state = replay_case_with_state(case)
    assert isinstance(state, SynthesisState)
    assert result.case_id == case.case_id
    assert len(state.findings) == len(case.expected_findings)
    assert len(state.recommendations) == len(case.expected_recommendations)
    assert len(state.trade_off_results) == 1
    assert len(state.implementation_themes) == 1
