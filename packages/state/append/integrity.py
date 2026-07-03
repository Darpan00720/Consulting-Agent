"""Replay integrity — the at-rest gate before any log may be folded (M1.7.4).

Module contract (architectural boundary): this module is the **at-rest
counterpart of the write-time guard**. The S3 guard + S4 pipeline guarantee
the invariants below for logs they build; nothing guarantees them for a log
arriving from persistence (M1.8), replay (M1.9), recovery, or any external
source. ``verify_log``/``verify_pair`` are that missing gate: pure,
deterministic, IO-free, single-pass, first-failure-with-index. They verify
and never repair — no renumbering, no dropped events, no synthesized history
(the S5 no-fabrication rule applies at rest exactly as at append).

Failure taxonomy (M1.7.4 adjustment 5):

- **Fatal** — replay must not begin. Every code except ``PROJECTION_STALE``:
  the artifact is corrupt or incomplete; recover from the persistence layer
  (earlier snapshot + longer log, backups) or human intervention.
- **Recoverable** — replay possible after operator action. Only
  ``PROJECTION_STALE``: the paired snapshot was produced by an older
  projection implementation — discard the snapshot and re-project the
  (already verified) log under the current implementation.

Known limitation (R13): truncation is **undetectable from a log alone** —
every prefix of a valid log is itself a valid log. It surfaces only through
``verify_pair`` (the snapshot claims a version beyond the log's end →
``STATE_VERSION_MISMATCH``).

Deferred to M1.8 (by approval): schema evolution, migrations, upcasting.
``ReplayErrorCode`` is an additive-frozen namespace so M1.8 can extend it.

Internal module: not part of the public API; consumers are M1.8 load and
M1.9 replay.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from common.errors import StratAgentError
from state.append.versioning import current_version
from state.events import EngagementCreated, Event
from state.models import EngagementState
from state.projection import PROJECTION_VERSION


class ReplayErrorCode(StrEnum):
    """Stable machine-readable replay-integrity codes (additive-frozen)."""

    SEQUENCE_ORIGIN = "sequence_origin"
    SEQUENCE_GAP = "sequence_gap"
    SEQUENCE_DUPLICATE = "sequence_duplicate"
    SEQUENCE_DISORDER = "sequence_disorder"
    UNASSIGNED_EVENT = "unassigned_event"
    EVENT_ID_DUPLICATE = "event_id_duplicate"
    ENGAGEMENT_MISMATCH = "engagement_mismatch"
    ENGAGEMENT_EMPTY = "engagement_empty"
    GENESIS_MISSING = "genesis_missing"
    GENESIS_DUPLICATE = "genesis_duplicate"
    STATE_VERSION_MISMATCH = "state_version_mismatch"
    PROJECTION_FUTURE = "projection_future"
    PROJECTION_STALE = "projection_stale"


#: Codes after which replay remains possible via documented operator action.
RECOVERABLE_CODES = frozenset({ReplayErrorCode.PROJECTION_STALE})


class ReplayIntegrityError(StratAgentError):
    """Base for replay-integrity failures (not appends: not an AppendError)."""

    def __init__(
        self,
        message: str,
        *,
        error_code: ReplayErrorCode,
        index: int | None = None,
        event_id: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.index = index
        self.event_id = event_id
        super().__init__(message)

    @property
    def recoverable(self) -> bool:
        """False = fatal, replay must not begin; True = operator action exists."""
        return self.error_code in RECOVERABLE_CODES


class SequenceIntegrityError(ReplayIntegrityError):
    """Sequence-number defects: origin, gap, duplicate, disorder, unassigned."""


class LogIdentityError(ReplayIntegrityError):
    """Log identity defects: event ids, engagement ids, genesis rules."""


class SnapshotMismatchError(ReplayIntegrityError):
    """Paired log/snapshot defects: identity, version, projection provenance."""

    def __init__(
        self,
        message: str,
        *,
        error_code: ReplayErrorCode,
        expected: int | None = None,
        actual: int | None = None,
    ) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(message, error_code=error_code)


def verify_log(log: Sequence[Event]) -> None:
    """Verify a log is replayable (R1-R8, R18). Raises on the first defect.

    The check order is deterministic (a given corrupt log always raises the
    same code): genesis -> engagement identity -> sequence sentinel ->
    duplicate -> disorder -> gap -> event-id uniqueness. An empty log is
    valid (it replays to the empty state at version 0).
    """
    if not log:
        return
    first = log[0].metadata
    if not isinstance(log[0], EngagementCreated):
        raise LogIdentityError(
            "non-empty log must begin with EngagementCreated (R8)",
            error_code=ReplayErrorCode.GENESIS_MISSING,
            index=0,
            event_id=first.event_id,
        )
    engagement = first.engagement_id
    if engagement == "":
        raise LogIdentityError(
            "genesis event carries an empty engagement_id (R18)",
            error_code=ReplayErrorCode.ENGAGEMENT_EMPTY,
            index=0,
            event_id=first.event_id,
        )
    if first.seq == 0:
        raise SequenceIntegrityError(
            "committed event is unassigned (seq 0)",
            error_code=ReplayErrorCode.UNASSIGNED_EVENT,
            index=0,
            event_id=first.event_id,
        )
    if first.seq != 1:
        raise SequenceIntegrityError(
            f"log must start at seq 1, found {first.seq}",
            error_code=ReplayErrorCode.SEQUENCE_ORIGIN,
            index=0,
            event_id=first.event_id,
        )
    seen_ids = {first.event_id}
    previous_seq = first.seq
    for index in range(1, len(log)):
        event = log[index]
        meta = event.metadata
        if isinstance(event, EngagementCreated):
            raise LogIdentityError(
                "EngagementCreated may appear only once, at index 0 (R8)",
                error_code=ReplayErrorCode.GENESIS_DUPLICATE,
                index=index,
                event_id=meta.event_id,
            )
        if meta.engagement_id != engagement:
            raise LogIdentityError(
                f"event belongs to {meta.engagement_id!r}, log is "
                f"{engagement!r} (R18)",
                error_code=ReplayErrorCode.ENGAGEMENT_MISMATCH,
                index=index,
                event_id=meta.event_id,
            )
        if meta.seq == 0:
            raise SequenceIntegrityError(
                "committed event is unassigned (seq 0)",
                error_code=ReplayErrorCode.UNASSIGNED_EVENT,
                index=index,
                event_id=meta.event_id,
            )
        if meta.seq == previous_seq:
            raise SequenceIntegrityError(
                f"duplicate seq {meta.seq}",
                error_code=ReplayErrorCode.SEQUENCE_DUPLICATE,
                index=index,
                event_id=meta.event_id,
            )
        if meta.seq < previous_seq:
            raise SequenceIntegrityError(
                f"seq {meta.seq} after {previous_seq}: log order must equal "
                "seq order",
                error_code=ReplayErrorCode.SEQUENCE_DISORDER,
                index=index,
                event_id=meta.event_id,
            )
        if meta.seq > previous_seq + 1:
            raise SequenceIntegrityError(
                f"gap: seq jumps {previous_seq} -> {meta.seq}",
                error_code=ReplayErrorCode.SEQUENCE_GAP,
                index=index,
                event_id=meta.event_id,
            )
        if meta.event_id in seen_ids:
            raise LogIdentityError(
                "event_id committed twice",
                error_code=ReplayErrorCode.EVENT_ID_DUPLICATE,
                index=index,
                event_id=meta.event_id,
            )
        seen_ids.add(meta.event_id)
        previous_seq = meta.seq


def verify_pair(log: Sequence[Event], state: EngagementState) -> None:
    """Verify a (log, snapshot) pair (R11, R12, R14 — after ``verify_log``).

    Fatal checks run before the one recoverable check, so a corrupt pair is
    always reported as fatal even when the snapshot is also stale.
    """
    verify_log(log)
    if state.projection_version > PROJECTION_VERSION:
        raise SnapshotMismatchError(
            f"snapshot projection_version {state.projection_version} was "
            f"produced by a future implementation (current "
            f"{PROJECTION_VERSION})",
            error_code=ReplayErrorCode.PROJECTION_FUTURE,
            expected=PROJECTION_VERSION,
            actual=state.projection_version,
        )
    if log and state.metadata.engagement_id != log[0].metadata.engagement_id:
        raise SnapshotMismatchError(
            f"snapshot belongs to {state.metadata.engagement_id!r}, log is "
            f"{log[0].metadata.engagement_id!r}",
            error_code=ReplayErrorCode.ENGAGEMENT_MISMATCH,
        )
    expected = current_version(log)
    if state.metadata.state_version != expected:
        raise SnapshotMismatchError(
            f"snapshot state_version {state.metadata.state_version} != last "
            f"committed seq {expected} (truncated or foreign artifact)",
            error_code=ReplayErrorCode.STATE_VERSION_MISMATCH,
            expected=expected,
            actual=state.metadata.state_version,
        )
    if state.projection_version < PROJECTION_VERSION:
        raise SnapshotMismatchError(
            f"snapshot projection_version {state.projection_version} is "
            f"stale (current {PROJECTION_VERSION}): discard the snapshot and "
            "re-project the verified log",
            error_code=ReplayErrorCode.PROJECTION_STALE,
            expected=PROJECTION_VERSION,
            actual=state.projection_version,
        )
