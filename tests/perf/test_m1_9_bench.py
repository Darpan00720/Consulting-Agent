"""M1.9 Phase 6 replay baselines: replay, recovery, and the frozen seams.

Regression references only — recorded, never optimization targets, never latency
assertions (the standing policy since M1.5). Single measured cold run per scale
(``pedantic``, rounds=1, iterations=1), consistent with the M1.7.7 and M1.8-S5
baselines. Fixtures are built by a **deterministic** generator (explicit ids +
seqs + a fixed timestamp), so the measured logs are reproducible (RP-031).

Measurement only (RP-032/033/034): the benchmark functions call the unchanged
``replay``/``recover`` and the frozen seams, and contain **no** behavioural
assertions. The single plain test at the end validates benchmark *setup* only
(shape/reproducibility), never timing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from replay import recover, replay
from state import EngagementState, Evidence, EvidenceType
from state.append import verify_log, verify_pair
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.projection import PROJECTION_VERSION, project

_TS = datetime(2020, 1, 1, tzinfo=UTC)  # fixed origin — never a clock read
_SIZES = [0, 1, 10, 100, 1000, 10000]


def _meta(seq: int) -> EventMetadata:
    return EventMetadata(
        engagement_id="eng_1",
        actor="system",
        source=EventSource.SYSTEM,
        event_id=f"ev_{seq}",
        seq=seq,
        occurred_at=_TS,
        recorded_at=_TS,
    )


def _log(size: int) -> tuple[Event, ...]:
    """Genesis-led, contiguous deterministic log of ``size`` events."""
    if size == 0:
        return ()
    events: list[Event] = [
        EngagementCreated(metadata=_meta(1), slug="demo", tenant_id="t_1")
    ]
    events += [
        EvidenceAdded(
            metadata=_meta(seq),
            evidence=Evidence(
                id=f"evid_{seq}",
                claim=f"c{seq}",
                type=EvidenceType.CLIENT_FACT,
                confidence=0.5,
            ),
        )
        for seq in range(2, size + 1)
    ]
    return tuple(events)


def _valid_pair(size: int) -> tuple[tuple[Event, ...], EngagementState]:
    log = _log(size)
    return log, project(list(log))  # canonical: verify_pair passes, no re-projection


def _stale_pair(size: int) -> tuple[tuple[Event, ...], EngagementState]:
    log = _log(size)
    stale = project(list(log)).model_copy(update={"projection_version": 0})
    return log, stale  # PROJECTION_STALE → recovery re-projects


# --- benchmarks (measurement only; no behavioural assertions) ----------------


@pytest.mark.parametrize("size", _SIZES)
def test_replay_baseline(benchmark: Any, size: int) -> None:
    log = _log(size)
    benchmark.pedantic(replay, args=(log,), rounds=1, iterations=1)


@pytest.mark.parametrize("size", _SIZES)
def test_recover_valid_baseline(benchmark: Any, size: int) -> None:
    log, snapshot = _valid_pair(size)
    benchmark.pedantic(recover, args=(log, snapshot), rounds=1, iterations=1)


@pytest.mark.parametrize("size", _SIZES)
def test_recover_stale_baseline(benchmark: Any, size: int) -> None:
    log, snapshot = _stale_pair(size)
    benchmark.pedantic(recover, args=(log, snapshot), rounds=1, iterations=1)


@pytest.mark.parametrize("size", _SIZES)
def test_verify_log_baseline(benchmark: Any, size: int) -> None:
    log = _log(size)
    benchmark.pedantic(verify_log, args=(log,), rounds=1, iterations=1)


@pytest.mark.parametrize("size", _SIZES)
def test_verify_pair_baseline(benchmark: Any, size: int) -> None:
    log, snapshot = _valid_pair(size)
    benchmark.pedantic(verify_pair, args=(log, snapshot), rounds=1, iterations=1)


@pytest.mark.parametrize("size", _SIZES)
def test_project_baseline(benchmark: Any, size: int) -> None:
    log = _log(size)
    benchmark.pedantic(project, args=(list(log),), rounds=1, iterations=1)


# --- benchmark setup validation (shape/reproducibility only, never timing) ---


def test_benchmark_fixtures_are_deterministic_and_shaped() -> None:
    # RP-031: generators are reproducible (byte-identical logs across calls)
    assert _log(10) == _log(10)
    # shapes the benchmarks rely on
    assert _log(0) == ()
    assert len(_log(100)) == 100
    valid_log, valid_snap = _valid_pair(10)
    stale_log, stale_snap = _stale_pair(10)
    assert valid_snap.projection_version == PROJECTION_VERSION  # verify_pair passes
    assert stale_snap.projection_version == 0  # triggers recovery re-projection
    assert valid_log == stale_log
