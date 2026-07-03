"""M1.7.4 replay-integrity tests: invariants R1-R18 (one dedicated test each).

R9 (deterministic replay) is owned by projection and referenced, not re-tested
here: see test_projection determinism tests and P14.
"""

from __future__ import annotations

from typing import Any

import pytest

from common.errors import StratAgentError
from state.append import (
    AppendError,
    AppendPipeline,
    LogIdentityError,
    ReplayErrorCode,
    ReplayIntegrityError,
    SequenceIntegrityError,
    SnapshotMismatchError,
    verify_log,
    verify_pair,
)
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.identifiers import EventId
from state.ledgers import Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.projection import project


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _created(**meta_kwargs: Any) -> EngagementCreated:
    return EngagementCreated(
        metadata=_meta(**meta_kwargs), slug="demo", tenant_id="t_1"
    )


def _evidence(seq: int, claim: str = "c", **meta_kwargs: Any) -> EvidenceAdded:
    ev = Evidence(claim=claim, type=EvidenceType.CLIENT_FACT, confidence=0.5)
    return EvidenceAdded(metadata=_meta(seq=seq, **meta_kwargs), evidence=ev)


def _valid_log(n: int = 3) -> list[Event]:
    log: list[Event] = [_created(seq=1)]
    for seq in range(2, n + 1):
        log.append(_evidence(seq, claim=f"c{seq}"))
    return log


def _raises(log: list[Event]) -> ReplayIntegrityError:
    with pytest.raises(ReplayIntegrityError) as excinfo:
        verify_log(log)
    return excinfo.value


def test_r1_first_seq_must_be_one() -> None:
    err = _raises([_created(seq=2)])
    assert err.error_code is ReplayErrorCode.SEQUENCE_ORIGIN
    assert err.index == 0


def test_r2_gap_detected() -> None:
    err = _raises([_created(seq=1), _evidence(2), _evidence(4)])
    assert err.error_code is ReplayErrorCode.SEQUENCE_GAP
    assert err.index == 2


def test_r3_duplicate_seq_detected() -> None:
    err = _raises([_created(seq=1), _evidence(2), _evidence(2, claim="x")])
    assert err.error_code is ReplayErrorCode.SEQUENCE_DUPLICATE
    assert err.index == 2


def test_r4_disorder_detected() -> None:
    # (1, 3, 2) would trip SEQUENCE_GAP first at index 1 — a true disorder
    # needs no preceding gap: (1, 2, 1)
    err = _raises([_created(seq=1), _evidence(2), _evidence(1, claim="x")])
    assert err.error_code is ReplayErrorCode.SEQUENCE_DISORDER
    assert err.index == 2


def test_r5_unassigned_event_detected() -> None:
    err = _raises([_created(seq=1), _evidence(0)])
    assert err.error_code is ReplayErrorCode.UNASSIGNED_EVENT
    assert err.index == 1
    genesis_err = _raises([_created(seq=0)])
    assert genesis_err.error_code is ReplayErrorCode.UNASSIGNED_EVENT


def test_r6_duplicate_event_id_detected() -> None:
    shared = EventId("ev_shared")
    log: list[Event] = [
        _created(seq=1, event_id=shared),
        _evidence(2, event_id=shared),
    ]
    err = _raises(log)
    assert err.error_code is ReplayErrorCode.EVENT_ID_DUPLICATE
    assert err.event_id == "ev_shared"


def test_r7_mixed_engagement_detected() -> None:
    err = _raises([_created(seq=1), _evidence(2, engagement_id="eng_B")])
    assert err.error_code is ReplayErrorCode.ENGAGEMENT_MISMATCH
    assert err.index == 1


def test_r8_genesis_required() -> None:
    verify_log([])  # empty log is valid
    err = _raises([_evidence(1)])
    assert err.error_code is ReplayErrorCode.GENESIS_MISSING
    assert err.index == 0
    assert err.recoverable is False  # no recovery, per approval


def test_r8_duplicate_genesis_detected() -> None:
    err = _raises([_created(seq=1), _created(seq=2)])
    assert err.error_code is ReplayErrorCode.GENESIS_DUPLICATE
    assert err.index == 1
    assert err.recoverable is False


def test_r10_valid_logs_pass() -> None:
    verify_log(_valid_log(1))
    verify_log(_valid_log(5))
    # cross-check: a pipeline-produced log passes the at-rest gate
    initial = EngagementState(
        metadata=EngagementMetadata(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    )
    pipeline = AppendPipeline(initial)
    pipeline.append_events(
        [_created(), _evidence(0, claim="via-pipeline")], expected_version=0
    )
    committed = pipeline.committed()
    verify_log(committed.log)
    # and the canonical pair passes: (log, project(log))
    verify_pair(committed.log, project(list(committed.log)))


def test_r11_state_version_mismatch_detected() -> None:
    log = _valid_log(3)
    snapshot = project(log)
    tampered = snapshot.model_copy(
        update={"metadata": snapshot.metadata.model_copy(update={"state_version": 5})}
    )
    with pytest.raises(SnapshotMismatchError) as excinfo:
        verify_pair(log, tampered)
    assert excinfo.value.error_code is ReplayErrorCode.STATE_VERSION_MISMATCH
    assert excinfo.value.expected == 3
    assert excinfo.value.actual == 5


def test_r12_foreign_snapshot_detected() -> None:
    log = _valid_log(2)
    snapshot = project(log)
    foreign = snapshot.model_copy(
        update={
            "metadata": snapshot.metadata.model_copy(
                update={"engagement_id": "eng_OTHER"}
            )
        }
    )
    with pytest.raises(SnapshotMismatchError) as excinfo:
        verify_pair(log, foreign)
    assert excinfo.value.error_code is ReplayErrorCode.ENGAGEMENT_MISMATCH


def test_r13_truncation_detected_only_with_pair() -> None:
    full = _valid_log(4)
    truncated = full[:2]
    verify_log(truncated)  # a prefix is a valid log — undetectable alone
    snapshot = project(full)  # claims version 4
    with pytest.raises(SnapshotMismatchError) as excinfo:
        verify_pair(truncated, snapshot)
    assert excinfo.value.error_code is ReplayErrorCode.STATE_VERSION_MISMATCH


def test_r14_projection_future_fatal() -> None:
    log = _valid_log(2)
    snapshot = project(log).model_copy(update={"projection_version": 99})
    with pytest.raises(SnapshotMismatchError) as excinfo:
        verify_pair(log, snapshot)
    assert excinfo.value.error_code is ReplayErrorCode.PROJECTION_FUTURE
    assert excinfo.value.recoverable is False


def test_r14_projection_stale_recoverable() -> None:
    log = _valid_log(2)
    snapshot = project(log).model_copy(update={"projection_version": 1})
    with pytest.raises(SnapshotMismatchError) as excinfo:
        verify_pair(log, snapshot)
    assert excinfo.value.error_code is ReplayErrorCode.PROJECTION_STALE
    assert excinfo.value.recoverable is True  # operator action: re-project


def test_r18_empty_engagement_id_detected() -> None:
    err = _raises([_created(seq=1, engagement_id="")])
    assert err.error_code is ReplayErrorCode.ENGAGEMENT_EMPTY
    assert err.index == 0
    assert err.recoverable is False


def test_error_codes_frozen_namespace() -> None:
    assert {code.value for code in ReplayErrorCode} == {
        "sequence_origin",
        "sequence_gap",
        "sequence_duplicate",
        "sequence_disorder",
        "unassigned_event",
        "event_id_duplicate",
        "engagement_mismatch",
        "engagement_empty",
        "genesis_missing",
        "genesis_duplicate",
        "state_version_mismatch",
        "projection_future",
        "projection_stale",
    }


def test_error_hierarchy_contracts() -> None:
    for concrete in (SequenceIntegrityError, LogIdentityError, SnapshotMismatchError):
        assert issubclass(concrete, ReplayIntegrityError)
        assert issubclass(concrete, StratAgentError)
        assert not issubclass(concrete, AppendError)  # replay is not append
    err = _raises([_created(seq=7)])
    assert isinstance(err, SequenceIntegrityError)
    assert err.index == 0 and err.event_id is not None
    # only PROJECTION_STALE is recoverable
    fatal = [c for c in ReplayErrorCode if c is not ReplayErrorCode.PROJECTION_STALE]
    for code in fatal:
        probe = ReplayIntegrityError("x", error_code=code)
        assert probe.recoverable is False
    assert (
        ReplayIntegrityError("x", error_code=ReplayErrorCode.PROJECTION_STALE)
    ).recoverable is True


def test_same_corrupt_log_same_code() -> None:
    # multi-defect log (wrong genesis AND seq gap): fixed order -> same code
    corrupt: list[Event] = [_evidence(5), _evidence(9)]
    first, second = _raises(corrupt), _raises(corrupt)
    assert first.error_code is second.error_code is ReplayErrorCode.GENESIS_MISSING
    assert first.index == second.index == 0
    assert str(first) == str(second)


def test_verify_does_not_mutate_inputs() -> None:
    log = _valid_log(3)
    snapshots = [e.model_copy(deep=True) for e in log]
    state = project(log)
    state_snapshot = state.model_copy(deep=True)
    verify_log(log)
    verify_pair(log, state)
    assert log == snapshots
    assert state == state_snapshot
