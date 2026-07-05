"""Replay contract (M1.9 Phase 2 — skeleton).

Declares the interface every replay implementation must satisfy, independent of
any concrete engine. The contract is deliberately minimal: a replay takes a
committed event **log** (the authoritative source of truth) and returns an
append-capable :class:`~state.Engagement`.

The reconstruction it must perform is the frozen pipeline — a fixed order, never
an alternate path::

    verify_log(log) -> project(log) -> verify_pair(log, state)
                    -> AppendPipeline(state, log=log, append_supported=True)

``make_committed`` is invoked *transitively* by ``AppendPipeline`` construction
(invariant P23) — never called separately. No implementation lives here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from state import Engagement, Event


@runtime_checkable
class ReplayContract(Protocol):
    """The replay capability: a verified event log in, an ``Engagement`` out.

    Implementations must be observationally pure (RP-016): they mutate no
    input, write no persistence, change no global state, and allocate only new
    immutable structures.
    """

    def replay(self, log: Sequence[Event]) -> Engagement: ...
