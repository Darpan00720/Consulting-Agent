"""Telemetry analytics — pure aggregation over event streams (v1.0 Observability).

Computes the engagement and quality analytics the observability spec requires.
Operational metrics (durations, retries, validation failures) come straight from
the event stream. Content metrics (issue-tree size, assumption/finding counts,
verdicts) are read from well-known ``metadata`` keys that emitters populate —
documented in ``docs/observability/API-Contracts.md``. All functions are pure and
tolerate missing keys.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from telemetry.events import EventStatus, Phase, TelemetryEvent, ValidationStatus

# Well-known metadata keys emitters may populate (see API-Contracts.md).
_META_VERDICT = "verdict"
_META_HITS = "hits"
_META_ISSUE_TREE_SIZE = "issue_tree_size"
_META_RECOMMENDATION_COUNT = "recommendation_count"
_META_ASSUMPTION_COUNT = "assumption_count"
_META_EVIDENCE_COUNT = "evidence_count"
_META_UNSUPPORTED_FINDINGS = "unsupported_finding_count"


@dataclass(frozen=True)
class ConfidenceSummary:
    """Distribution summary for a set of confidence values."""

    n: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    # coarse buckets for a histogram
    buckets: dict[str, int]


def summarize_confidence(values: Iterable[float]) -> ConfidenceSummary:
    vals = [v for v in values if v is not None]
    if not vals:
        return ConfidenceSummary(0, None, None, None, None, {})
    buckets = {"0.0-0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, "0.9-1.0": 0}
    for v in vals:
        if v < 0.5:
            buckets["0.0-0.5"] += 1
        elif v < 0.7:
            buckets["0.5-0.7"] += 1
        elif v < 0.9:
            buckets["0.7-0.9"] += 1
        else:
            buckets["0.9-1.0"] += 1
    return ConfidenceSummary(
        n=len(vals),
        mean=statistics.fmean(vals),
        median=statistics.median(vals),
        minimum=min(vals),
        maximum=max(vals),
        buckets=buckets,
    )


@dataclass(frozen=True)
class EngagementAnalytics:
    """Per-engagement operational + content metrics."""

    engagement_id: str
    event_count: int
    total_wall_ms: float  # first→last event timestamp span
    active_ms: float  # sum of FINISHED durations
    duration_by_phase_ms: dict[str, float]
    rework_count: int
    validation_failures: int
    knowledge_retrieval_hits: int
    frameworks_used: tuple[str, ...]
    confidence: ConfidenceSummary
    issue_tree_size: int | None
    recommendation_count: int | None


def engagement_analytics(events: Iterable[TelemetryEvent]) -> EngagementAnalytics:
    """Aggregate one engagement's events. Assumes all share an engagement_id."""
    evs = list(events)
    if not evs:
        return EngagementAnalytics(
            "", 0, 0.0, 0.0, {}, 0, 0, 0, (), summarize_confidence([]), None, None
        )
    eid = evs[0].engagement_id
    ts = [e.timestamp for e in evs]
    wall = (max(ts) - min(ts)).total_seconds() * 1000.0

    by_phase: dict[str, float] = {}
    active = 0.0
    for e in evs:
        if e.status is EventStatus.FINISHED and e.duration_ms is not None:
            by_phase[e.phase.value] = by_phase.get(e.phase.value, 0.0) + e.duration_ms
            active += e.duration_ms

    rework = sum(1 for e in evs if e.status is EventStatus.REWORKED)
    val_fail = sum(1 for e in evs if e.validation_status is ValidationStatus.BLOCKED)
    hits = sum(
        int(e.metadata.get(_META_HITS, 0)) for e in evs if e.phase is Phase.KNOWLEDGE
    )
    frameworks = sorted({fw for e in evs for fw in e.frameworks_used})

    return EngagementAnalytics(
        engagement_id=eid,
        event_count=len(evs),
        total_wall_ms=wall,
        active_ms=active,
        duration_by_phase_ms=by_phase,
        rework_count=rework,
        validation_failures=val_fail,
        knowledge_retrieval_hits=hits,
        frameworks_used=tuple(frameworks),
        confidence=summarize_confidence(
            e.confidence for e in evs if e.confidence is not None
        ),
        issue_tree_size=_last_meta_int(evs, _META_ISSUE_TREE_SIZE),
        recommendation_count=_last_meta_int(evs, _META_RECOMMENDATION_COUNT),
    )


@dataclass(frozen=True)
class QualityAnalytics:
    """Cross-engagement quality/governance metrics."""

    engagements: int
    reviewer_pass_rate: float | None
    challenger_intervention_rate: float | None
    needs_rework_frequency: float | None
    validation_block_rate: float | None
    framework_selection_frequency: dict[str, int]
    knowledge_retrieval_effectiveness: float | None
    assumption_count_total: int
    unsupported_finding_count_total: int
    evidence_count_total: int
    confidence: ConfidenceSummary


def quality_analytics(events: Iterable[TelemetryEvent]) -> QualityAnalytics:
    """Aggregate governance/quality metrics across many engagements."""
    evs = list(events)
    engagements = {e.engagement_id for e in evs}

    review = [e for e in evs if e.phase is Phase.REVIEW and _is_terminal(e)]
    challenge = [e for e in evs if e.phase is Phase.CHALLENGE and _is_terminal(e)]
    gates = [e for e in evs if e.validation_status is not None]

    reviewer_pass = _rate(review, lambda e: e.metadata.get(_META_VERDICT) == "approved")
    challenger_intervene = _rate(
        challenge,
        lambda e: e.metadata.get(_META_VERDICT)
        in {"stands_with_caveats", "needs_rework"},
    )
    needs_rework = _rate(
        review + challenge,
        lambda e: e.metadata.get(_META_VERDICT) == "needs_rework"
        or e.status is EventStatus.REWORKED,
    )
    block_rate = _rate(gates, lambda e: e.validation_status is ValidationStatus.BLOCKED)

    fw_freq: Counter[str] = Counter()
    for e in evs:
        fw_freq.update(e.frameworks_used)

    knowledge = [e for e in evs if e.phase is Phase.KNOWLEDGE and _is_terminal(e)]
    know_eff = _rate(knowledge, lambda e: int(e.metadata.get(_META_HITS, 0)) > 0)

    return QualityAnalytics(
        engagements=len(engagements),
        reviewer_pass_rate=reviewer_pass,
        challenger_intervention_rate=challenger_intervene,
        needs_rework_frequency=needs_rework,
        validation_block_rate=block_rate,
        framework_selection_frequency=dict(fw_freq),
        knowledge_retrieval_effectiveness=know_eff,
        assumption_count_total=_sum_meta(evs, _META_ASSUMPTION_COUNT),
        unsupported_finding_count_total=_sum_meta(evs, _META_UNSUPPORTED_FINDINGS),
        evidence_count_total=_sum_meta(evs, _META_EVIDENCE_COUNT),
        confidence=summarize_confidence(
            e.confidence for e in evs if e.confidence is not None
        ),
    )


# --- helpers ----------------------------------------------------------------


def _is_terminal(e: TelemetryEvent) -> bool:
    return e.status in (
        EventStatus.FINISHED,
        EventStatus.FAILED,
        EventStatus.REWORKED,
    )


def _rate(
    events: list[TelemetryEvent], pred: Callable[[TelemetryEvent], bool]
) -> float | None:
    if not events:
        return None
    return sum(1 for e in events if pred(e)) / len(events)


def _last_meta_int(events: list[TelemetryEvent], key: str) -> int | None:
    for e in reversed(events):
        if key in e.metadata:
            try:
                return int(e.metadata[key])
            except (TypeError, ValueError):
                return None
    return None


def _sum_meta(events: Iterable[TelemetryEvent], key: str) -> int:
    total = 0
    seen: set[str] = set()
    for e in events:
        # count once per engagement (content counts are per-engagement snapshots)
        if key in e.metadata and e.engagement_id not in seen:
            try:
                total += int(e.metadata[key])
                seen.add(e.engagement_id)
            except (TypeError, ValueError):
                continue
    return total
