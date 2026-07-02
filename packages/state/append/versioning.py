"""Version derivation — pure arithmetic (M1.7.3-S2, design D2/D4).

Module contract (architectural boundary): this module performs **arithmetic
only** — it derives version numbers exclusively from ``event.metadata.seq``
of a committed log; it never inspects payloads or domain objects. It
establishes **no correctness** by itself: the log's contiguity is established
by the append pipeline (S4) after admission (S3) and verified at the replay
boundary (M1.7.4); this module simply reads what they maintain.
"""

from __future__ import annotations

from collections.abc import Sequence

from state.events import Event


def current_version(events: Sequence[Event]) -> int:
    """The committed version: the last event's seq (``0`` for an empty log)."""
    if not events:
        return 0
    return events[-1].metadata.seq


def current_sequence(events: Sequence[Event]) -> int:
    """The next sequence number to allocate: ``current_version + 1``."""
    return current_version(events) + 1


def next_state_version(events: Sequence[Event]) -> int:
    """The ``state_version`` the next applied event will produce.

    Identical to ``current_sequence`` by construction: since projection v2
    (design D4) a state's version is the seq of the last applied event. This
    function exists to make the D2↔D4 identity explicit (invariant V3).
    """
    return current_sequence(events)
