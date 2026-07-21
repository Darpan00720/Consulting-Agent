"""Tests for the Human Evaluation model: structure validation and
inter-reviewer agreement."""

from __future__ import annotations

import pytest

from app.evaluation.errors import EvaluationError, InsufficientDataError
from app.evaluation.human_evaluation import (
    approval_agreement,
    metric_agreement,
    overall_agreement,
    submit_human_review,
)
from app.evaluation.models import EvaluationMetric, ReviewPanel


def test_submit_human_review_records_onto_panel():
    panel = ReviewPanel()
    review = submit_human_review(
        panel,
        "alice",
        "senior partner",
        {"traceability": 0.9},
        confidence=0.8,
        approval=True,
    )
    assert panel.reviews == [review]
    assert review.reviewer == "alice"


def test_submit_human_review_rejects_unknown_metric():
    panel = ReviewPanel()
    with pytest.raises(EvaluationError):
        submit_human_review(panel, "alice", "x", {"not_a_real_metric": 0.5})


def test_submit_human_review_rejects_out_of_range_score():
    panel = ReviewPanel()
    with pytest.raises(EvaluationError):
        submit_human_review(panel, "alice", "x", {"traceability": 1.5})


def test_submit_human_review_rejects_out_of_range_confidence():
    panel = ReviewPanel()
    with pytest.raises(EvaluationError):
        submit_human_review(panel, "alice", "x", {}, confidence=2.0)


def test_metric_agreement_reflects_score_spread():
    panel = ReviewPanel()
    submit_human_review(panel, "alice", "x", {"traceability": 0.9})
    submit_human_review(panel, "bob", "x", {"traceability": 0.8})
    agreement = metric_agreement(panel, EvaluationMetric.TRACEABILITY)
    assert agreement == pytest.approx(0.9)


def test_metric_agreement_requires_2_reviewers():
    panel = ReviewPanel()
    submit_human_review(panel, "alice", "x", {"traceability": 0.9})
    with pytest.raises(InsufficientDataError):
        metric_agreement(panel, EvaluationMetric.TRACEABILITY)


def test_approval_agreement_is_majority_fraction():
    panel = ReviewPanel()
    submit_human_review(panel, "alice", "x", {}, approval=True)
    submit_human_review(panel, "bob", "x", {}, approval=True)
    submit_human_review(panel, "carol", "x", {}, approval=False)
    assert approval_agreement(panel) == pytest.approx(2 / 3)


def test_overall_agreement_requires_shared_metric_across_2_reviewers():
    panel = ReviewPanel()
    submit_human_review(panel, "alice", "x", {"traceability": 0.9})
    with pytest.raises(InsufficientDataError):
        overall_agreement(panel)
    submit_human_review(panel, "bob", "x", {"traceability": 0.7})
    assert 0.0 <= overall_agreement(panel) <= 1.0
