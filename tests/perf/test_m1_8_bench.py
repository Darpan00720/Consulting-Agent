"""M1.8-S5 persistence baselines: save, load, and checksum verification.

Regression references only — recorded, never optimization targets, never
latency assertions (the standing policy since M1.5). Single measured cold run
per scale (`pedantic`, rounds=1, iterations=1), consistent with the append,
projection, and validation baselines. Fixtures build a realistic engagement by
appending an `EngagementCreated`-led log through the real pipeline, so the
persisted object is genuine and the save path is exercised end to end
(serialize → SHA-256 → atomic writes incl. fsync).

The plain (non-benchmark) tests at the end verify the *fixture infrastructure*
— they assert shape/validity, never timing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import persistence.store as store_module
from persistence import EngagementStore
from persistence.format import dump_log, dump_snapshot
from state import Engagement, Evidence, EvidenceType
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.projection import project

_SCALES = [10, 100, 1000, 10000]


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _engagement_of_size(n: int) -> Engagement:
    """An append-capable engagement whose committed log has ``n`` events."""
    engagement = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    events: list[Event] = [
        EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")
    ]
    events += [
        EvidenceAdded(
            metadata=_meta(),
            evidence=Evidence(
                claim=f"c{i}", type=EvidenceType.CLIENT_FACT, confidence=0.5
            ),
        )
        for i in range(1, n)
    ]
    engagement.append_events(events, expected_version=0)
    return engagement


def _canonical_bytes(engagement: Engagement) -> tuple[bytes, bytes]:
    """The exact bytes the store checksums on save/load: (log, project(log))."""
    committed = engagement._pipeline.committed()
    return (
        dump_log(committed.log).encode("utf-8"),
        dump_snapshot(project(committed.log)).encode("utf-8"),
    )


# --- benchmarks --------------------------------------------------------------


@pytest.mark.parametrize("size", _SCALES)
def test_save_baseline(benchmark: Any, tmp_path: Path, size: int) -> None:
    engagement = _engagement_of_size(size)
    store = EngagementStore(tmp_path)
    benchmark.pedantic(store.save, args=(engagement,), rounds=1, iterations=1)
    assert (tmp_path / "demo").exists()


@pytest.mark.parametrize("size", _SCALES)
def test_load_baseline(benchmark: Any, tmp_path: Path, size: int) -> None:
    store = EngagementStore(tmp_path)
    store.save(_engagement_of_size(size))
    loaded = benchmark.pedantic(store.load, args=("demo",), rounds=1, iterations=1)
    assert loaded.current_version() == size


@pytest.mark.parametrize("size", _SCALES)
def test_checksum_verification_baseline(benchmark: Any, size: int) -> None:
    log_bytes, snapshot_bytes = _canonical_bytes(_engagement_of_size(size))

    def _verify() -> tuple[str, str]:
        # exactly what load recomputes to compare against the manifest
        return store_module._sha256(log_bytes), store_module._sha256(snapshot_bytes)

    benchmark.pedantic(_verify, rounds=1, iterations=1)


# --- fixture-infrastructure tests (shape/validity only, never timing) --------


def test_fixture_builder_is_valid_and_sized() -> None:
    engagement = _engagement_of_size(10)
    assert engagement.current_version() == 10
    log_bytes, snapshot_bytes = _canonical_bytes(engagement)
    assert log_bytes.count(b"\n") == 10  # one NDJSON line per event
    assert snapshot_bytes  # non-empty canonical snapshot


def test_save_load_fixture_round_trips(tmp_path: Path) -> None:
    store = EngagementStore(tmp_path)
    store.save(_engagement_of_size(10))
    assert store.load("demo").current_version() == 10
