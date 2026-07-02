"""Sequence stamping — pure arithmetic (M1.7.3-S2, design D2).

Module contract (architectural boundary): this module performs **arithmetic
only** — it stamps contiguous sequence numbers onto copies of events. It
establishes **no correctness** by itself: which events may be appended is
decided by admission (S3); atomicity and no-reuse are established by the
append pipeline (S4); log integrity is verified at the replay boundary
(M1.7.4).

Precondition violations raise ``ValueError`` — they are programmer errors that
a correct pipeline can never surface to callers. The ``AppendError`` family is
reserved exclusively for failures that legitimately propagate through the
public append API (later slices).
"""

from __future__ import annotations

from collections.abc import Sequence

from state.events import Event


def stamp(events: Sequence[Event], *, first_seq: int) -> list[Event]:
    """Return frozen copies of ``events`` stamped with contiguous seqs.

    ``stamped[i]`` differs from ``events[i]`` only in ``metadata.seq``
    (``first_seq + i``); order and payloads are preserved and inputs are never
    mutated. Only unassigned events (``metadata.seq == 0``) are legal input
    (invariant A7); a previously stamped event or collection is rejected.
    """
    if first_seq < 1:
        raise ValueError(f"first_seq must be >= 1, got {first_seq}")
    if not events:
        raise ValueError("cannot stamp an empty batch")
    stamped: list[Event] = []
    for offset, event in enumerate(events):
        if event.metadata.seq != 0:
            raise ValueError(
                f"event {event.metadata.event_id!r} already has seq "
                f"{event.metadata.seq}; only unassigned (seq == 0) events may "
                "be stamped"
            )
        metadata = event.metadata.model_copy(update={"seq": first_seq + offset})
        stamped.append(event.model_copy(update={"metadata": metadata}))
    return stamped
