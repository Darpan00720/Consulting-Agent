"""Replay engine (M1.9 Phase 3 — implementation).

:class:`ReplayEngine` is the entry point: it accepts a committed event log,
orchestrates the frozen reconstruction pipeline, and returns an append-capable
:class:`~state.Engagement`. It owns **orchestration only** — every substantive
step is delegated to a frozen seam and none is re-implemented:

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

from state import Engagement, Event
from state.append import AppendPipeline, verify_log, verify_pair
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


def replay(log: Sequence[Event]) -> Engagement:
    """Convenience contract entry point: replay ``log`` via a default engine."""
    return ReplayEngine().replay(log)
