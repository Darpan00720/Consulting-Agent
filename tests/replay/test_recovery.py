"""M1.9 Phase 4 recovery-orchestration invariant tests (RP-018…RP-023).

Recovery operates on a decoded persisted ``(log, snapshot)`` pair (never via
``EngagementStore.load``, which would itself reject a stale snapshot). The
natural stale fixture is a live engagement's ``committed.state`` —
``projection_version == 0`` against the current ``PROJECTION_VERSION`` — which is
exactly the M1.8 canonical-persistence scenario a future version bump produces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import replay as replay_pkg
import replay.engine as replay_engine
from replay import recover
from state import Engagement, EngagementState, Evidence, EvidenceType
from state.append import ReplayErrorCode, ReplayIntegrityError, SnapshotMismatchError
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.projection import PROJECTION_VERSION, project


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


def _committed() -> tuple[tuple[Event, ...], EngagementState]:
    """A valid committed (log, runtime-state) pair. The runtime state carries
    projection_version == 0 (built incrementally), so it is naturally stale."""
    e = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    events: list[Event] = [
        EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1"),
        _evidence("c0"),
        _evidence("c1"),
    ]
    e.append_events(events, expected_version=0)
    committed = e._pipeline.committed()
    return committed.log, committed.state


def _stale_pair() -> tuple[tuple[Event, ...], EngagementState]:
    log, runtime_state = _committed()
    assert runtime_state.projection_version == 0  # stale by construction
    return log, runtime_state


def _current_pair() -> tuple[tuple[Event, ...], EngagementState]:
    log, _ = _committed()
    return log, project(list(log))  # projection_version == PROJECTION_VERSION


def _future_pair() -> tuple[tuple[Event, ...], EngagementState]:
    log, _ = _committed()
    future = project(list(log)).model_copy(
        update={"projection_version": PROJECTION_VERSION + 1}
    )
    return log, future


def _corrupt_log() -> list[Event]:
    return [_evidence("orphan")]  # non-genesis first event → GENESIS_MISSING


def _spy_project(monkeypatch: pytest.MonkeyPatch, counter: dict[str, int]) -> None:
    real = replay_engine.project

    def spy(events: Any) -> EngagementState:
        counter["n"] += 1
        return real(events)

    monkeypatch.setattr(replay_engine, "project", spy)


# --- RP-018: recovery attempted only for PROJECTION_STALE --------------------


def test_rp018_recovery_only_for_projection_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flog, fsnap = _future_pair()
    clog, csnap = _current_pair()
    slog, ssnap = _stale_pair()
    calls = {"n": 0}
    _spy_project(monkeypatch, calls)

    # future (fatal) → no recovery attempted, no re-projection
    with pytest.raises(SnapshotMismatchError):
        recover(flog, fsnap)
    assert calls["n"] == 0
    # current (valid) → no recovery needed, no re-projection
    recover(clog, csnap)
    assert calls["n"] == 0
    # stale (recoverable) → recovery attempted (re-projection happens)
    recover(slog, ssnap)
    assert calls["n"] == 1


# --- RP-019: recovered engagement is identical to project(log) ---------------


def test_rp019_recovered_equals_project_log() -> None:
    log, stale = _stale_pair()
    recovered = recover(log, stale)
    assert recovered.get_state() == project(list(log))
    assert recovered.get_state().projection_version == PROJECTION_VERSION


# --- RP-020: recovery never writes persistence artifacts (source-scan) -------


def test_rp020_recovery_writes_no_persistence() -> None:
    src = Path(replay_engine.__file__).read_text(encoding="utf-8")
    # ban the call/construct forms — the docstring may *mention* EngagementStore.save
    # to state that recovery does not call it (persisting is the caller's job)
    for banned in (
        "EngagementStore(",
        ".save(",
        "atomic_write(",
        "append_bytes(",
        "os.replace",
        "hashlib",
        "import persistence",
        "from persistence",
    ):
        assert banned not in src, f"recovery must not write persistence: {banned}"


# --- RP-021: recovery performs exactly one projection ------------------------


def test_rp021_recovery_performs_exactly_one_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slog, ssnap = _stale_pair()
    clog, csnap = _current_pair()
    calls = {"n": 0}
    _spy_project(monkeypatch, calls)

    recover(slog, ssnap)
    assert calls["n"] == 1  # stale upgrade → exactly one re-projection
    recover(clog, csnap)
    assert calls["n"] == 1  # valid pair → no additional projection


# --- RP-022: non-recoverable ReplayIntegrityError propagate unchanged --------


def test_rp022_non_recoverable_errors_propagate() -> None:
    flog, fsnap = _future_pair()
    with pytest.raises(SnapshotMismatchError) as future_exc:
        recover(flog, fsnap)
    assert future_exc.value.error_code is ReplayErrorCode.PROJECTION_FUTURE

    with pytest.raises(ReplayIntegrityError) as log_exc:
        recover(_corrupt_log(), project([]))
    assert log_exc.value.error_code is ReplayErrorCode.GENESIS_MISSING


# --- RP-023: recovery is deterministic ---------------------------------------


def test_rp023_recovery_is_deterministic() -> None:
    log, stale = _stale_pair()
    first = recover(log, stale)
    second = recover(log, stale)  # same inputs, not mutated between calls
    assert first.get_state() == second.get_state()
    assert first.current_version() == second.current_version()


# --- valid-pair path: rebuild from the persisted snapshot as-is --------------


def test_recovery_valid_pair_uses_persisted_snapshot() -> None:
    log, current = _current_pair()
    engagement = recover(log, current)
    assert engagement.get_state() == current
    assert engagement.current_version() == current.metadata.state_version


# --- purity: recovery mutates neither the input snapshot nor the log ---------


def test_recovery_purity_no_input_mutation() -> None:
    log, stale = _stale_pair()
    log_before = list(log)
    pv_before = stale.projection_version

    recovered = recover(log, stale)

    assert stale.projection_version == pv_before  # snapshot untouched (still stale)
    assert list(log) == log_before  # log untouched
    assert isinstance(recovered, Engagement)


# --- recovered engagement is append-capable ----------------------------------


def test_recovered_engagement_is_append_capable() -> None:
    log, stale = _stale_pair()
    engagement = recover(log, stale)
    version = engagement.current_version()
    result = engagement.append_event(_evidence("after"), expected_version=version)
    assert result.version == version + 1


# --- recovery imports only approved frozen seams (source-scan) ---------------


def test_recovery_source_scan_only_approved_seams() -> None:
    src = Path(replay_engine.__file__).read_text(encoding="utf-8")
    for seam in ("verify_log", "verify_pair", "project", "AppendPipeline"):
        assert seam in src, seam
    for banned in ("read_bytes", "load_log", "load_snapshot", "Manifest", "open("):
        assert banned not in src, f"recovery must not read/decode artifacts: {banned}"
    # replay_pkg exposes recover as part of its surface
    assert "recover" in replay_pkg.__all__
