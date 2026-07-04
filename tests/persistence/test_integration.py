"""M1.8-S5 integration: end-to-end persistence behaviour across full cycles.

Exercises the store as a client would — full save/load/append/save loops,
repeated cycles, and a simulated process restart — and pins the canonical
projection invariant at the integration level. No behaviour is added here;
these tests compose the S4 store to prove the milestone-level contract
(PER-001, PER-006, PER-007, PER-011 and the S4 projection decision).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from persistence import EngagementStore
from persistence.format import load_log, load_snapshot
from persistence.paths import (
    EVENTS_LOG_FILENAME,
    MANIFEST_FILENAME,
    SNAPSHOT_FILENAME,
)
from state import Engagement, Evidence, EvidenceType
from state.append import verify_log, verify_pair
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.projection import PROJECTION_VERSION, project

_TRIPLE = (EVENTS_LOG_FILENAME, SNAPSHOT_FILENAME, MANIFEST_FILENAME)


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _evidence(claim: str) -> EvidenceAdded:
    return EvidenceAdded(
        metadata=_meta(),
        evidence=Evidence(claim=claim, type=EvidenceType.CLIENT_FACT, confidence=0.5),
    )


def _engagement(slug: str = "demo") -> Engagement:
    e = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug=slug)
    events: list[Event] = [
        EngagementCreated(metadata=_meta(), slug=slug, tenant_id="t_1"),
        _evidence("c"),
    ]
    e.append_events(events, expected_version=0)
    return e


def _read_triple(directory: Path) -> tuple[bytes, bytes, bytes]:
    return tuple((directory / name).read_bytes() for name in _TRIPLE)  # type: ignore[return-value]


# --- save -> load -> append -> save ------------------------------------------


def test_save_load_append_save_round_trip(tmp_path: Path) -> None:
    store = EngagementStore(tmp_path)
    original = _engagement()
    store.save(original)

    loaded = store.load("demo")
    base_version = loaded.current_version()
    base_len = len(loaded._pipeline.committed().log)

    result = loaded.append_event(
        _evidence("second-session"), expected_version=base_version
    )
    assert result.version == base_version + 1
    store.save(loaded)

    reloaded = store.load("demo")
    assert reloaded.current_version() == base_version + 1
    assert len(reloaded._pipeline.committed().log) == base_len + 1
    # the newly appended fact survives the persistence round-trip
    claims = {
        ev.evidence.claim
        for ev in reloaded._pipeline.committed().log
        if isinstance(ev, EvidenceAdded)
    }
    assert {"c", "second-session"} <= claims


# --- multiple save cycles remain deterministic (PER-011, N cycles) -----------


def test_multiple_save_cycles_are_byte_identical(tmp_path: Path) -> None:
    roots = [tmp_path / f"cycle{i}" for i in range(3)]
    EngagementStore(roots[0]).save(_engagement())
    for prev, nxt in zip(roots, roots[1:], strict=False):
        reloaded = EngagementStore(prev).load("demo")
        EngagementStore(nxt).save(reloaded)

    triples = [_read_triple(r / "demo") for r in roots]
    assert triples[0] == triples[1] == triples[2]


# --- persistence survives a process-restart simulation -----------------------


def test_persistence_survives_process_restart(tmp_path: Path) -> None:
    # "first process": save, then drop every reference to the writing store
    writer = EngagementStore(tmp_path)
    writer.save(_engagement())
    del writer

    # "second process": a brand-new store on the same root, no shared memory
    reader = EngagementStore(tmp_path)
    loaded = reader.load("demo")
    assert loaded.current_version() == 2

    # the reconstructed engagement is genuinely append-capable after "restart"
    result = loaded.append_event(_evidence("post-restart"), expected_version=2)
    assert result.version == 3


# --- canonical projection invariant (documented + asserted) ------------------


def test_persisted_snapshot_is_canonical_projection(tmp_path: Path) -> None:
    """The persisted snapshot is the canonical projection of the log, so a
    persisted (log, snapshot) pair *always* satisfies verify_pair — no replay,
    no repair (M1.8-S4 projection decision; documented in docs/api/Persistence.md).
    """
    EngagementStore(tmp_path).save(_engagement())
    directory = tmp_path / "demo"

    log = load_log((directory / EVENTS_LOG_FILENAME).read_bytes().decode("utf-8"))
    snapshot = load_snapshot(
        (directory / SNAPSHOT_FILENAME).read_bytes().decode("utf-8")
    )

    assert snapshot.projection_version == PROJECTION_VERSION
    assert snapshot == project(log)
    verify_log(log)
    verify_pair(log, snapshot)  # canonical pair — must not raise
