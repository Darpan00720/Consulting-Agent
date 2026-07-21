"""Continuous Improvement (requester's "Continuous Improvement" section):
"Automatically identify: weak frameworks, weak workflows, weak
deliverables, high-failure stages, frequent review comments, repeated
recommendation failures, knowledge gaps, training opportunities. Generate
prioritized improvement recommendations."

**Frequency-based surfacing only, never invented consulting content** — the
same "structure/measure, never invent" boundary every quality/evaluation
module in this codebase already draws. Every ``ImprovementRecommendation``
below is backed by a real count over caller-supplied history (evaluations,
replays, hallucination findings, human review comments); a pattern that
occurs once is noise, not a signal, so ``_MIN_FREQUENCY`` filters it out.
``priority`` is simply the observed frequency — higher means "surfaced by
more independent replays/reviews," the most defensible ordering available
without inventing a severity model.
"""

from __future__ import annotations

from collections import Counter

from .models import (
    BenchmarkCase,
    CaseReplayResult,
    EvaluationMetric,
    EvaluationResult,
    HallucinationFinding,
    HumanReview,
    ImprovementRecommendation,
    new_improvement_id,
)

_WEAK_THRESHOLD = 0.6
_MIN_FREQUENCY = 2


def _weak_occurrences(
    evaluations: tuple[EvaluationResult, ...],
    replays: tuple[CaseReplayResult, ...],
    metric: EvaluationMetric,
    key_fn,
) -> Counter:
    """Count, per key (a framework id / engagement type / deliverable
    type), how many replays scored below ``_WEAK_THRESHOLD`` on ``metric``."""
    counts: Counter = Counter()
    for evaluation, replay in zip(evaluations, replays, strict=False):
        score = evaluation.score_for(metric)
        if score is None or score.score >= _WEAK_THRESHOLD:
            continue
        for key in key_fn(replay):
            counts[key] += 1
    return counts


def _recommendations_from_counter(
    counts: Counter, category: str, describe
) -> list[ImprovementRecommendation]:
    return [
        ImprovementRecommendation(
            id=new_improvement_id(),
            category=category,
            description=describe(key),
            frequency=frequency,
            priority=frequency,
            supporting_evidence=(str(key),),
        )
        for key, frequency in counts.items()
        if frequency >= _MIN_FREQUENCY
    ]


def _weak_frameworks(
    evaluations: tuple[EvaluationResult, ...], replays: tuple[CaseReplayResult, ...]
) -> list[ImprovementRecommendation]:
    counts = _weak_occurrences(
        evaluations,
        replays,
        EvaluationMetric.FRAMEWORK_SELECTION_ACCURACY,
        lambda r: r.selected_frameworks,
    )
    return _recommendations_from_counter(
        counts,
        "weak_framework",
        lambda fid: (
            f"framework {fid!r} repeatedly correlates with low "
            "framework_selection_accuracy"
        ),
    )


def _weak_workflows(
    evaluations: tuple[EvaluationResult, ...],
    replays: tuple[CaseReplayResult, ...],
    cases: tuple[BenchmarkCase, ...],
) -> list[ImprovementRecommendation]:
    case_by_id = {c.case_id: c for c in cases}
    counts = _weak_occurrences(
        evaluations,
        replays,
        EvaluationMetric.WORKFLOW_QUALITY,
        lambda r: (
            (case_by_id[r.case_id].engagement_type.value,)
            if r.case_id in case_by_id
            else ()
        ),
    )
    return _recommendations_from_counter(
        counts,
        "weak_workflow",
        lambda engagement_type: (
            f"{engagement_type!r} engagements repeatedly score low on workflow_quality"
        ),
    )


def _weak_deliverables(
    evaluations: tuple[EvaluationResult, ...], replays: tuple[CaseReplayResult, ...]
) -> list[ImprovementRecommendation]:
    counts = _weak_occurrences(
        evaluations,
        replays,
        EvaluationMetric.DELIVERABLE_QUALITY,
        lambda r: tuple(d.value for d in r.deliverables_generated),
    )
    return _recommendations_from_counter(
        counts,
        "weak_deliverable",
        lambda dtype: (
            f"deliverable type {dtype!r} repeatedly correlates with "
            "low deliverable_quality"
        ),
    )


def _high_failure_stages(
    evaluations: tuple[EvaluationResult, ...],
) -> list[ImprovementRecommendation]:
    """Proxy for "stage": this platform's replay engine doesn't yet emit
    per-ConsultingStage telemetry (a known gap, see workflow_quality's own
    documented limitation), so the closest real signal is which named
    metric most often falls below threshold across evaluations."""
    counts: Counter = Counter()
    for evaluation in evaluations:
        for score in evaluation.metric_scores:
            if score.score < _WEAK_THRESHOLD:
                counts[score.metric.value] += 1
    return _recommendations_from_counter(
        counts,
        "high_failure_stage",
        lambda metric_name: (
            f"{metric_name!r} falls below threshold most often across evaluations"
        ),
    )


def _frequent_review_comments(
    human_reviews: tuple[HumanReview, ...],
) -> list[ImprovementRecommendation]:
    counts: Counter = Counter()
    for review in human_reviews:
        for comment in review.comments:
            counts[comment] += 1
    return _recommendations_from_counter(
        counts,
        "frequent_review_comment",
        lambda comment: f"reviewers repeatedly note: {comment!r}",
    )


def _repeated_recommendation_failures(
    evaluations: tuple[EvaluationResult, ...], replays: tuple[CaseReplayResult, ...]
) -> list[ImprovementRecommendation]:
    counts = _weak_occurrences(
        evaluations,
        replays,
        EvaluationMetric.RECOMMENDATION_QUALITY,
        lambda r: r.recommendations,
    )
    return _recommendations_from_counter(
        counts,
        "repeated_recommendation_failure",
        lambda statement: (
            f"recommendation repeatedly scores low on "
            f"recommendation_quality: {statement!r}"
        ),
    )


def _knowledge_gaps(
    hallucination_findings_by_replay: tuple[tuple[HallucinationFinding, ...], ...],
) -> list[ImprovementRecommendation]:
    counts: Counter = Counter()
    for findings in hallucination_findings_by_replay:
        seen_types = {f.hallucination_type.value for f in findings}
        for hallucination_type in seen_types:
            counts[hallucination_type] += 1
    return _recommendations_from_counter(
        counts,
        "knowledge_gap",
        lambda htype: f"{htype!r} hallucination findings recur across replays",
    )


def _training_opportunities(
    evaluations: tuple[EvaluationResult, ...],
) -> list[ImprovementRecommendation]:
    """A proxy: metrics that measure human/process participation
    (REVIEW_QUALITY, APPROVAL_QUALITY) scoring low across many evaluations
    suggests a process/training gap rather than a content gap."""
    counts: Counter = Counter()
    process_metrics = (
        EvaluationMetric.REVIEW_QUALITY,
        EvaluationMetric.APPROVAL_QUALITY,
    )
    for evaluation in evaluations:
        for metric in process_metrics:
            score = evaluation.score_for(metric)
            if score is not None and score.score < _WEAK_THRESHOLD:
                counts[metric.value] += 1
    return _recommendations_from_counter(
        counts,
        "training_opportunity",
        lambda metric_name: (
            f"{metric_name!r} suggests a review/governance "
            "process gap, not a content gap"
        ),
    )


def generate_improvement_recommendations(
    evaluations: tuple[EvaluationResult, ...],
    replays: tuple[CaseReplayResult, ...],
    cases: tuple[BenchmarkCase, ...],
    *,
    hallucination_findings_by_replay: tuple[tuple[HallucinationFinding, ...], ...] = (),
    human_reviews: tuple[HumanReview, ...] = (),
) -> tuple[ImprovementRecommendation, ...]:
    """Never raises: sparse or empty history simply produces fewer (or no)
    recommendations, a normal outcome for a young or small evaluation
    corpus. Results are sorted by priority (frequency) descending."""
    recommendations: list[ImprovementRecommendation] = []
    recommendations.extend(_weak_frameworks(evaluations, replays))
    recommendations.extend(_weak_workflows(evaluations, replays, cases))
    recommendations.extend(_weak_deliverables(evaluations, replays))
    recommendations.extend(_high_failure_stages(evaluations))
    recommendations.extend(_frequent_review_comments(human_reviews))
    recommendations.extend(_repeated_recommendation_failures(evaluations, replays))
    recommendations.extend(_knowledge_gaps(hallucination_findings_by_replay))
    recommendations.extend(_training_opportunities(evaluations))
    return tuple(sorted(recommendations, key=lambda r: r.priority, reverse=True))
