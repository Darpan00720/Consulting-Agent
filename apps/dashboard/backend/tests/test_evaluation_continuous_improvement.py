"""Tests for the Continuous Improvement engine's frequency-based surfacing."""

from __future__ import annotations

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.continuous_improvement import generate_improvement_recommendations
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.hallucination import detect_hallucinations
from app.evaluation.replay import replay_case


def test_no_recommendations_from_a_single_clean_replay():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    evaluation = evaluate_replay(case, replay)
    recs = generate_improvement_recommendations((evaluation,), (replay,), (case,))
    # a single occurrence never clears _MIN_FREQUENCY except structural
    # gaps that fire on every replay (e.g. approval_quality)
    categories = {r.category for r in recs}
    assert "weak_framework" not in categories
    assert "weak_deliverable" not in categories


def test_repeated_weak_signal_surfaces_with_correct_frequency():
    cases = all_benchmark_cases()
    replays = [replay_case(c) for c in cases] * 2  # replay everything twice
    doubled_cases = list(cases) * 2
    evals = [evaluate_replay(c, r) for c, r in zip(doubled_cases, replays, strict=True)]
    hallucinations = tuple(
        detect_hallucinations(c, r) for c, r in zip(doubled_cases, replays, strict=True)
    )

    recs = generate_improvement_recommendations(
        tuple(evals),
        tuple(replays),
        tuple(doubled_cases),
        hallucination_findings_by_replay=hallucinations,
    )
    assert recs, "expected at least one recurring pattern across 2x replays"
    # approval_quality is structurally 0 on every deterministic replay
    training_recs = [r for r in recs if r.category == "training_opportunity"]
    assert training_recs
    assert training_recs[0].frequency == len(doubled_cases)


def test_recommendations_sorted_by_priority_descending():
    cases = all_benchmark_cases()
    replays = [replay_case(c) for c in cases] * 2
    doubled_cases = list(cases) * 2
    evals = [evaluate_replay(c, r) for c, r in zip(doubled_cases, replays, strict=True)]
    recs = generate_improvement_recommendations(
        tuple(evals), tuple(replays), tuple(doubled_cases)
    )
    priorities = [r.priority for r in recs]
    assert priorities == sorted(priorities, reverse=True)


def test_frequent_review_comments_are_counted():
    from app.evaluation.models import HumanReview

    reviews = (
        HumanReview(
            id="r1",
            reviewer="a",
            expertise="x",
            scores={},
            comments=("thin risk",),
            confidence=0.6,
            approval=True,
        ),
        HumanReview(
            id="r2",
            reviewer="b",
            expertise="x",
            scores={},
            comments=("thin risk",),
            confidence=0.6,
            approval=True,
        ),
    )
    recs = generate_improvement_recommendations((), (), (), human_reviews=reviews)
    comment_recs = [r for r in recs if r.category == "frequent_review_comment"]
    assert comment_recs and comment_recs[0].frequency == 2
