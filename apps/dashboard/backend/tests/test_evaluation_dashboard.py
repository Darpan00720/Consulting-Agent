"""Tests for the longitudinal Quality Dashboard model."""

from __future__ import annotations

import dataclasses

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.dashboard import build_dashboard_snapshot
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.hallucination import detect_hallucinations
from app.evaluation.replay import replay_case


def test_empty_history_produces_an_empty_but_valid_snapshot():
    snapshot = build_dashboard_snapshot((), ())
    assert snapshot.consulting_score_trend == ()
    assert snapshot.benchmark_trend["evaluation_count"] == 0
    assert snapshot.hallucination_rate == 0.0
    assert snapshot.approval_latency_avg_s == 0.0


def test_snapshot_builds_real_trends_from_real_evaluations():
    cases = all_benchmark_cases()
    replays = [replay_case(c) for c in cases]
    evals = [evaluate_replay(c, r) for c, r in zip(cases, replays, strict=True)]
    hallucinations = tuple(
        detect_hallucinations(c, r) for c, r in zip(cases, replays, strict=True)
    )

    snapshot = build_dashboard_snapshot(
        tuple(evals),
        tuple(replays),
        hallucination_findings_by_replay=hallucinations,
        customer_acceptance_rate=0.9,
    )
    assert len(snapshot.consulting_score_trend) == len(cases)
    assert len(snapshot.framework_accuracy_trend) == len(cases)
    assert snapshot.execution_duration_avg_s >= 0.0
    assert snapshot.hallucination_rate == 0.0  # clean replays -> no hallucinations
    assert snapshot.customer_acceptance_rate == 0.9
    assert snapshot.benchmark_trend["evaluation_count"] == len(cases)


def test_snapshot_sorts_evaluations_chronologically_before_trending():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    e1 = evaluate_replay(case, replay)
    e2 = dataclasses.replace(
        e1, id="e2", overall_score=0.1, evaluated_at=e1.evaluated_at - 1000
    )
    # e2 is "earlier" chronologically despite being appended second
    snapshot = build_dashboard_snapshot((e1, e2), (replay,))
    assert snapshot.benchmark_trend["first_overall_score"] == 0.1
    assert snapshot.benchmark_trend["last_overall_score"] == e1.overall_score


def test_hallucination_rate_reflects_fraction_of_hallucinating_replays():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    evaluation = evaluate_replay(case, replay)
    from app.evaluation.models import HallucinationFinding, HallucinationType

    dirty = (
        HallucinationFinding(
            hallucination_type=HallucinationType.INVENTED_METRIC,
            ref_ids=("x",),
            detail="d",
        ),
    )
    snapshot = build_dashboard_snapshot(
        (evaluation, evaluation),
        (replay, replay),
        hallucination_findings_by_replay=(dirty, ()),
    )
    assert snapshot.hallucination_rate == 0.5
