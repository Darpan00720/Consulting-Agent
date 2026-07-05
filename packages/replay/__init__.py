"""StratAgent replay — rebuild engagements from event logs (M1.9).

Replay is **pure orchestration over frozen seams**: it verifies a log, folds it
through the projection engine, verifies the ``(log, snapshot)`` pair, and
reconstructs an append-capable engagement — never re-implementing any of those
steps and never mutating inputs, writing persistence, or touching global state
(RP-016). It is a **sibling** of ``state`` and ``persistence`` and depends on
both; neither depends on it.

Public surface — :class:`ReplayEngine` (with ``replay`` for a bare log and
``recover`` for a persisted ``(log, snapshot)`` pair), the
:class:`ReplayContract` protocol, the ``replay`` and ``recover`` convenience
functions, and the replay error taxonomy (:class:`ReplayError` + the re-exported
frozen :class:`ReplayIntegrityError`). ``recover`` upgrades a
``PROJECTION_STALE`` snapshot by whole-log re-projection and returns an
append-capable engagement; persisting the upgraded snapshot is the caller's
responsibility via ``EngagementStore.save``.
"""

from replay.contracts import ReplayContract
from replay.engine import ReplayEngine, recover, replay
from replay.errors import ReplayError, ReplayIntegrityError

__all__ = [
    "ReplayContract",
    "ReplayEngine",
    "ReplayError",
    "ReplayIntegrityError",
    "recover",
    "replay",
]
