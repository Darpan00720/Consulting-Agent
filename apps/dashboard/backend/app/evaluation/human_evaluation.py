"""Human Evaluation (requester's "Human Evaluation" section): a reviewer's
own judgment call is always caller-supplied — this module validates
STRUCTURE (every score in range, every reviewer accounted for) and computes
inter-reviewer agreement; it never derives or overrides a human's score,
the same "structure real content, never invent it" split every quality
model in this codebase already draws.

**Hard invariant, raises rather than reports** (the same deliberate
exception to "never raise" used for traceability elsewhere in this
platform): a score or confidence outside ``[0, 1]`` is a malformed review,
not a normal low-quality outcome — a 1.4-star review out of a 0-1 scale is a
caller bug, not a bad evaluation.
"""

from __future__ import annotations

from app.evaluation.models import EvaluationMetric

from .errors import EvaluationError, InsufficientDataError
from .models import HumanReview, ReviewPanel, new_review_id


def _validate_unit_interval(value: float, label: str) -> None:
    if not (0.0 <= value <= 1.0):
        raise EvaluationError(f"{label} must be in [0, 1], got {value!r}")


def submit_human_review(
    panel: ReviewPanel,
    reviewer: str,
    expertise: str,
    scores: dict,
    *,
    comments: tuple[str, ...] = (),
    confidence: float = 0.5,
    approval: bool = False,
    recommendations: tuple[str, ...] = (),
    disagreements: tuple[str, ...] = (),
) -> HumanReview:
    """Records one reviewer's structured judgment onto ``panel``. Every key
    in ``scores`` must name a real ``EvaluationMetric`` value and every
    score/confidence must fall in ``[0, 1]``."""
    valid_metrics = {m.value for m in EvaluationMetric}
    unknown = set(scores) - valid_metrics
    if unknown:
        raise EvaluationError(f"scores reference unknown metric(s): {sorted(unknown)}")
    for metric_name, value in scores.items():
        _validate_unit_interval(value, f"score for {metric_name!r}")
    _validate_unit_interval(confidence, "confidence")

    review = HumanReview(
        id=new_review_id(),
        reviewer=reviewer,
        expertise=expertise,
        scores=dict(scores),
        comments=comments,
        confidence=confidence,
        approval=approval,
        recommendations=recommendations,
        disagreements=disagreements,
    )
    panel.reviews.append(review)
    return review


def _spread_agreement(values: list[float]) -> float:
    return max(0.0, 1.0 - (max(values) - min(values)))


def metric_agreement(panel: ReviewPanel, metric: EvaluationMetric) -> float:
    """Agreement on one metric across every reviewer who scored it — 1.0
    means every reviewer gave the identical score, 0.0 means maximally
    apart (a 1.0 spread on a [0, 1] scale)."""
    values = [
        review.scores[metric.value]
        for review in panel.reviews
        if metric.value in review.scores
    ]
    if len(values) < 2:
        raise InsufficientDataError(
            f"fewer than 2 reviewers scored {metric.value!r}; cannot measure agreement"
        )
    return _spread_agreement(values)


def approval_agreement(panel: ReviewPanel) -> float:
    """Fraction of reviewers agreeing with the majority approve/reject call."""
    if len(panel.reviews) < 2:
        raise InsufficientDataError(
            "fewer than 2 reviews in panel; cannot measure approval agreement"
        )
    approvals = [review.approval for review in panel.reviews]
    majority_count = max(sum(approvals), len(approvals) - sum(approvals))
    return majority_count / len(approvals)


def overall_agreement(panel: ReviewPanel) -> float:
    """Average per-metric agreement across every metric at least 2
    reviewers scored in common. Raises ``InsufficientDataError`` only if no
    metric was scored by 2+ reviewers at all."""
    scored_metrics = {
        metric_name for review in panel.reviews for metric_name in review.scores
    }
    per_metric_scores = []
    for metric_name in scored_metrics:
        values = [
            review.scores[metric_name]
            for review in panel.reviews
            if metric_name in review.scores
        ]
        if len(values) >= 2:
            per_metric_scores.append(_spread_agreement(values))
    if not per_metric_scores:
        raise InsufficientDataError(
            "no metric was scored by 2 or more reviewers in this panel"
        )
    return sum(per_metric_scores) / len(per_metric_scores)
