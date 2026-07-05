"""Replay engine (M1.9 Phase 3 replay + Phase 4 recovery).

:class:`ReplayEngine` is the entry point. :meth:`~ReplayEngine.replay` rebuilds
an engagement from a committed event log; :meth:`~ReplayEngine.recover` rebuilds
from a persisted ``(log, snapshot)`` pair, upgrading a ``PROJECTION_STALE``
snapshot by whole-log re-projection. Both own **orchestration only** — every
substantive step is delegated to a frozen seam and none is re-implemented:

    verify_log(log)                       # at-rest integrity gate (M1.7.4)
        -> project(log)                   # canonical fold (M1.5/M1.7.2)
        -> verify_pair(log, state)        # (log, snapshot) agreement gate (M1.7.4)
        -> AppendPipeline(state, log=log, # rebuild; make_committed runs *inside*
                          append_supported=True)          # construction (P23)
        -> Engagement(pipeline)

The engine is a **frozen, stateless value** (RP-016): it holds no mutable
state, mutates no input, writes no persistence, and changes no global state — a
replay allocates only new immutable structures. It computes no versions or
sequences (those flow through the frozen seams), fabricates no events, repairs
no logs, and never bypasses the two verification gates (RP-017).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from state import Engagement, EngagementState, Event
from state.append import (
    AppendPipeline,
    ReplayErrorCode,
    SnapshotMismatchError,
    verify_log,
    verify_pair,
)
from state.projection import project


@dataclass(frozen=True)
class ReplayEngine:
    """Stateless orchestrator that rebuilds an engagement from an event log.

    Frozen and field-less: instances carry no mutable state, so a replay cannot
    change engine or global state (RP-016). The reconstruction pipeline is fixed
    — see :class:`~replay.contracts.ReplayContract`.
    """

    def replay(self, log: Sequence[Event]) -> Engagement:
        """Rebuild an append-capable engagement from ``log``.

        Runs the fixed pipeline with no alternate path: ``verify_log`` (fatal on
        any log defect) -> ``project`` (canonical fold) -> ``verify_pair``
        (confirms the pair) -> ``AppendPipeline`` (reconstruction;
        ``make_committed`` runs inside construction, P23). Integrity is never
        bypassed (RP-017); nothing is mutated, fabricated, repaired, or persisted.
        """
        verify_log(log)
        state = project(log)
        verify_pair(log, state)
        pipeline = AppendPipeline(state, log=log, append_supported=True)
        return Engagement(pipeline)

    def recover(self, log: Sequence[Event], snapshot: EngagementState) -> Engagement:
        """Reconstruct from a persisted ``(log, snapshot)`` pair, upgrading a
        stale snapshot by whole-log re-projection.

        ``verify_log`` -> ``verify_pair``; if the pair is valid, rebuild
        directly from the persisted snapshot. If ``verify_pair`` raises
        ``PROJECTION_STALE`` — **and only then** (RP-018) — discard the snapshot,
        re-project the log **exactly once** (RP-021), re-verify the upgraded
        pair, and rebuild. Every non-recoverable ``ReplayIntegrityError``
        propagates unchanged (RP-022).

        Recovery never modifies the snapshot, rewrites files, calls
        ``EngagementStore.save``, fabricates metadata, repairs logs, or
        suppresses integrity failures (RP-020). Persisting an upgraded snapshot
        is the caller's responsibility via ``EngagementStore.save``.
        """
        verify_log(log)
        try:
            verify_pair(log, snapshot)
        except SnapshotMismatchError as exc:
            if exc.error_code is not ReplayErrorCode.PROJECTION_STALE:
                raise  # non-recoverable → propagate unchanged (RP-022)
            projected = project(log)  # discard stale snapshot; one re-projection
            verify_pair(log, projected)
            return Engagement(AppendPipeline(projected, log=log, append_supported=True))
        return Engagement(AppendPipeline(snapshot, log=log, append_supported=True))


def replay(log: Sequence[Event]) -> Engagement:
    """Convenience contract entry point: replay ``log`` via a default engine."""
    return ReplayEngine().replay(log)


def recover(log: Sequence[Event], snapshot: EngagementState) -> Engagement:
    """Convenience: recover a ``(log, snapshot)`` pair via a default engine."""
    return ReplayEngine().recover(log, snapshot)
