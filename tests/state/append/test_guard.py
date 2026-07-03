"""M1.7.3-S3 invariant tests G1-G16: guard decisions (one test per invariant)."""

from __future__ import annotations

from typing import Any

import pytest

from state.append import (
    AppendErrorCode,
    EventAdmissionError,
    GuardDecision,
    VersionConflictError,
    check_append,
)
from state.events import Event, EventMetadata, EventSource, EvidenceAdded
from state.identifiers import EngagementId, EventId
from state.ledgers import Evidence, EvidenceType

_ENG = EngagementId("eng_1")


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _candidate(claim: str = "c", **meta_kwargs: Any) -> EvidenceAdded:
    ev = Evidence(claim=claim, type=EvidenceType.CLIENT_FACT, confidence=0.5)
    return EvidenceAdded(metadata=_meta(**meta_kwargs), evidence=ev)


def _check(
    candidates: list[Event],
    *,
    committed_version: int = 0,
    committed_event_ids: frozenset[EventId] = frozenset(),
    expected_version: int = 0,
) -> GuardDecision:
    return check_append(
        candidates,
        engagement_id=_ENG,
        committed_version=committed_version,
        committed_event_ids=committed_event_ids,
        expected_version=expected_version,
    )


def test_g1_purity_inputs_never_mutated() -> None:
    candidates: list[Event] = [_candidate()]
    committed_ids = frozenset({EventId("ev_prev")})
    snapshots = [e.model_copy(deep=True) for e in candidates]
    _check(candidates, committed_event_ids=committed_ids)
    assert candidates == snapshots
    assert committed_ids == frozenset({EventId("ev_prev")})


def test_g2_determinism_field_for_field() -> None:
    candidates: list[Event] = [_candidate(seq=7)]
    first = _check(candidates, committed_version=3, expected_version=3)
    second = _check(candidates, committed_version=3, expected_version=3)
    assert first.admitted == second.admitted is False
    assert first.error is not None and second.error is not None
    assert type(first.error) is type(second.error)
    assert first.error.error_code is second.error.error_code
    assert str(first.error) == str(second.error)
    assert isinstance(first.error, EventAdmissionError)
    assert isinstance(second.error, EventAdmissionError)
    assert first.error.reason == second.error.reason
    assert first.error.event_id == second.error.event_id


def test_g3_statelessness_call_history_irrelevant() -> None:
    good: list[Event] = [_candidate()]
    bad: list[Event] = [_candidate(seq=5)]
    before = _check(good)
    _check(bad)  # interleave a rejection
    after = _check(good)
    assert before.admitted is after.admitted is True
    assert before.error is None and after.error is None


def test_g4_decision_exclusivity() -> None:
    admitted = _check([_candidate()])
    assert admitted.admitted is True and admitted.error is None
    rejected = _check([], expected_version=0)
    assert rejected.admitted is False and rejected.error is not None


def test_g5_version_equality_admits() -> None:
    decision = _check([_candidate()], committed_version=4, expected_version=4)
    assert decision.admitted is True


def test_g6_stale_writer_rejected() -> None:
    decision = _check([_candidate()], committed_version=5, expected_version=3)
    assert decision.admitted is False
    assert isinstance(decision.error, VersionConflictError)
    assert decision.error.expected == 3
    assert decision.error.actual == 5


def test_g7_ahead_writer_rejected() -> None:
    decision = _check([_candidate()], committed_version=2, expected_version=9)
    assert decision.admitted is False
    assert isinstance(decision.error, VersionConflictError)
    assert decision.error.expected == 9
    assert decision.error.actual == 2


def test_g8_empty_batch_rejected() -> None:
    decision = _check([])
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)
    assert "empty" in decision.error.reason


def test_g9_foreign_engagement_rejected() -> None:
    foreign = _candidate(engagement_id="eng_OTHER")
    decision = _check([foreign])
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)
    assert decision.error.event_id == foreign.metadata.event_id
    assert "eng_OTHER" in decision.error.reason


def test_g10_preassigned_seq_rejected() -> None:
    stamped = _candidate(seq=2)
    decision = _check([stamped])
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)
    assert "already assigned" in decision.error.reason
    assert decision.error.event_id == stamped.metadata.event_id


def test_g11_committed_event_id_rejected() -> None:
    candidate = _candidate()
    decision = _check(
        [candidate],
        committed_event_ids=frozenset({candidate.metadata.event_id}),
    )
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)
    assert "already committed" in decision.error.reason


def test_g12_intra_batch_duplicate_rejected() -> None:
    candidate = _candidate()
    decision = _check([candidate, candidate])
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)
    assert "within batch" in decision.error.reason


def test_g13_admission_precedes_version() -> None:
    # both defective candidates AND a version conflict: admission error wins
    decision = _check([_candidate(seq=9)], committed_version=5, expected_version=1)
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)


def test_g14_error_code_taxonomy() -> None:
    admission = _check([])
    version = _check([_candidate()], committed_version=1, expected_version=0)
    assert admission.error is not None
    assert admission.error.error_code is AppendErrorCode.EVENT_ADMISSION
    assert version.error is not None
    assert version.error.error_code is AppendErrorCode.VERSION_CONFLICT


def test_g15_negative_committed_version_is_programmer_error() -> None:
    with pytest.raises(ValueError, match="committed_version"):
        _check([_candidate()], committed_version=-1)


def test_g16_mixed_engagement_batch_rejected() -> None:
    batch: list[Event] = [
        _candidate(claim="a1"),
        _candidate(claim="a2"),
        _candidate(claim="b", engagement_id="eng_B"),
    ]
    decision = _check(batch)
    assert decision.admitted is False
    assert isinstance(decision.error, EventAdmissionError)
    assert decision.error.event_id == batch[2].metadata.event_id
    assert "eng_B" in decision.error.reason
