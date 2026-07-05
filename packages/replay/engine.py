"""Replay engine (M1.9 Phase 2 — skeleton).

:class:`ReplayEngine` is the entry point: it accepts a persisted artifact (a
committed event log), orchestrates the frozen reconstruction pipeline, and
returns an append-capable :class:`~state.Engagement`. Everything substantive is
delegated to frozen seams (``verify_log`` / ``project`` / ``verify_pair`` /
``AppendPipeline``); the engine owns orchestration only.

The engine is a **frozen, stateless value** (RP-016): it holds no mutable
state, mutates no input, writes no persistence, and changes no global state — a
replay allocates only new immutable structures.

Phase 2 is skeleton only: :meth:`ReplayEngine.replay` (and the ``replay``
convenience function) are declared and raise :class:`NotImplementedError`. The
reconstruction logic lands in a later, separately approved phase.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from state import Engagement, Event

_NOT_IMPLEMENTED = "replay is not implemented until M1.9 Phase 3 (implementation)"


@dataclass(frozen=True)
class ReplayEngine:
    """Stateless orchestrator that rebuilds an engagement from an event log.

    Frozen and field-less: instances carry no mutable state, so a replay cannot
    change engine or global state (RP-016). The reconstruction pipeline is fixed
    — see :class:`~replay.contracts.ReplayContract`.
    """

    def replay(self, log: Sequence[Event]) -> Engagement:
        """Rebuild an append-capable engagement from ``log``.

        Skeleton (M1.9 Phase 2): not yet implemented. The approved
        implementation will run, with no alternate path::

            verify_log(log) -> project(log) -> verify_pair(log, state)
                            -> AppendPipeline(state, log=log,
                                              append_supported=True)
        """
        raise NotImplementedError(_NOT_IMPLEMENTED)


def replay(log: Sequence[Event]) -> Engagement:
    """Convenience contract entry point: replay ``log`` via a default engine."""
    return ReplayEngine().replay(log)
