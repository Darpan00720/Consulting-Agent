"""M1.7.3-S2 invariant tests A1-A8: sequence stamping (one test per invariant)."""

from __future__ import annotations

from typing import Any

import pytest

from state.append import stamp
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.ledgers import Evidence, EvidenceType


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _unassigned(n: int) -> list[Event]:
    """n unassigned events (seq == 0, the default)."""
    events: list[Event] = [
        EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")
    ]
    for i in range(1, n):
        ev = Evidence(claim=f"c{i}", type=EvidenceType.CLIENT_FACT, confidence=0.5)
        events.append(EvidenceAdded(metadata=_meta(), evidence=ev))
    return events


def test_a1_stamp_is_contiguous() -> None:
    assert [e.metadata.seq for e in stamp(_unassigned(1), first_seq=1)] == [1]
    stamped = stamp(_unassigned(5), first_seq=4)
    assert [e.metadata.seq for e in stamped] == [4, 5, 6, 7, 8]


def test_a2_first_seq_honored() -> None:
    assert stamp(_unassigned(3), first_seq=7)[0].metadata.seq == 7


def test_a3_payload_and_order_preserved() -> None:
    events = _unassigned(3)
    stamped = stamp(events, first_seq=1)
    for original, copy in zip(events, stamped, strict=True):
        assert type(copy) is type(original)
        assert copy.metadata.event_id == original.metadata.event_id
        original_dump = original.model_dump(exclude={"metadata": {"seq"}})
        copy_dump = copy.model_dump(exclude={"metadata": {"seq"}})
        assert copy_dump == original_dump


def test_a4_originals_untouched() -> None:
    events = _unassigned(3)
    snapshots = [e.model_copy(deep=True) for e in events]
    stamp(events, first_seq=1)
    for original, snapshot in zip(events, snapshots, strict=True):
        assert original == snapshot
        assert original.metadata.seq == 0


def test_a5_stamp_deterministic() -> None:
    events = _unassigned(4)
    assert stamp(events, first_seq=2) == stamp(events, first_seq=2)


def test_a6_preconditions() -> None:
    with pytest.raises(ValueError, match="first_seq"):
        stamp(_unassigned(1), first_seq=0)
    with pytest.raises(ValueError, match="empty"):
        stamp([], first_seq=1)


def test_a7_already_stamped_event_rejected() -> None:
    pre_stamped = EngagementCreated(metadata=_meta(seq=3), slug="demo", tenant_id="t_1")
    with pytest.raises(ValueError, match="already has seq 3"):
        stamp([pre_stamped], first_seq=4)


def test_a8_restamping_a_stamped_collection_always_fails() -> None:
    stamped = stamp(_unassigned(3), first_seq=1)
    with pytest.raises(ValueError, match="already has seq"):
        stamp(stamped, first_seq=4)
