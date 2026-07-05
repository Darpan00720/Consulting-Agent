"""StratAgent replay — rebuild engagements from event logs (M1.9).

Replay is **pure orchestration over frozen seams**: it verifies a log, folds it
through the projection engine, verifies the ``(log, snapshot)`` pair, and
reconstructs an append-capable engagement — never re-implementing any of those
steps and never mutating inputs, writing persistence, or touching global state
(RP-016). It is a **sibling** of ``state`` and ``persistence`` and depends on
both; neither depends on it.

Phase 2 (skeleton) exposes the public surface — :class:`ReplayEngine`, the
:class:`ReplayContract` protocol, the ``replay`` convenience function, and the
replay error taxonomy (:class:`ReplayError` + the re-exported frozen
:class:`ReplayIntegrityError`). Reconstruction logic arrives in a later,
separately approved phase.
"""

from replay.contracts import ReplayContract
from replay.engine import ReplayEngine, replay
from replay.errors import ReplayError, ReplayIntegrityError

__all__ = [
    "ReplayContract",
    "ReplayEngine",
    "ReplayError",
    "ReplayIntegrityError",
    "replay",
]
