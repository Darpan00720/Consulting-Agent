"""Append admission + optimistic-concurrency decisions (M1.7.3-S3, D3/D6).

Module contract (architectural boundary): this module **decides and never
acts**. It is completely stateless and pure — it receives committed facts
(engagement id, committed version, committed event ids), the writer's
``expected_version``, and the candidate events, and returns a
:class:`GuardDecision`. It never mutates state, allocates sequence numbers,
validates business rules, retries, logs, or performs IO. Acting on decisions
is the append pipeline's job (S4); log integrity at rest is M1.7.4's.

**Decision precedence is contractual and must never change:**
admission → version → success.

Complexity: the version comparison is O(1); the overall guard is O(k) over the
candidate batch (never over the log).

Error boundary: ``ValueError`` = internal programmer misuse only (a corrupt
committed version handed in by the pipeline); ``EventAdmissionError`` =
candidate defects; ``VersionConflictError`` = optimistic-concurrency failures.
No other error types.
"""

from __future__ import annotations

from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from state.append.errors import EventAdmissionError, VersionConflictError
from state.events import Event
from state.identifiers import EngagementId, EventId


@dataclass(frozen=True)
class GuardDecision:
    """The guard's verdict: admitted, XOR a fully constructed rejection error.

    Rejections carry a ready-to-raise S1 error (payload and ``error_code``
    populated); the pipeline's boundary is exactly ``raise decision.error``.
    Decision objects never cross the facade — the public contract is errors.
    """

    admitted: bool
    error: VersionConflictError | EventAdmissionError | None = None


def check_append(
    candidates: Sequence[Event],
    *,
    engagement_id: EngagementId,
    committed_version: int,
    committed_event_ids: AbstractSet[EventId],
    expected_version: int,
) -> GuardDecision:
    """Decide whether ``candidates`` may be appended (admission → version)."""
    if committed_version < 0:
        raise ValueError(f"committed_version must be >= 0, got {committed_version}")
    admission = _admission_error(candidates, engagement_id, committed_event_ids)
    if admission is not None:
        return GuardDecision(admitted=False, error=admission)
    version = _version_error(expected_version, committed_version)
    if version is not None:
        return GuardDecision(admitted=False, error=version)
    return GuardDecision(admitted=True)


def _admission_error(
    candidates: Sequence[Event],
    engagement_id: EngagementId,
    committed_event_ids: AbstractSet[EventId],
) -> EventAdmissionError | None:
    """First candidate defect in batch order, or None (pure)."""
    if not candidates:
        return EventAdmissionError("empty batch")
    seen: set[EventId] = set()
    for event in candidates:
        meta = event.metadata
        if meta.engagement_id != engagement_id:
            return EventAdmissionError(
                f"event belongs to engagement {meta.engagement_id!r}, "
                f"not {engagement_id!r}",
                event_id=meta.event_id,
            )
        if meta.seq != 0:
            return EventAdmissionError(
                f"sequence already assigned (seq {meta.seq})",
                event_id=meta.event_id,
            )
        if meta.event_id in committed_event_ids:
            return EventAdmissionError(
                "event already committed", event_id=meta.event_id
            )
        if meta.event_id in seen:
            return EventAdmissionError(
                "duplicate event_id within batch", event_id=meta.event_id
            )
        seen.add(meta.event_id)
    return None


def _version_error(expected: int, committed: int) -> VersionConflictError | None:
    """O(1) optimistic-concurrency comparison (both directions reject)."""
    if expected != committed:
        return VersionConflictError(expected=expected, actual=committed)
    return None
