"""M1.7.3-S2 invariant tests V1-V7 and C1-C3: version derivation + composition."""

from __future__ import annotations

from typing import Any

from state.append import current_sequence, current_version, next_state_version, stamp
from state.events import (
    CaseClassified,
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.ledgers import Evidence, EvidenceType
from state.sections.enums import CaseArchetype
from state.sections.scoping import CaseClassification


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _evidence_added(seq: int, claim: str = "c") -> EvidenceAdded:
    ev = Evidence(claim=claim, type=EvidenceType.CLIENT_FACT, confidence=0.5)
    return EvidenceAdded(metadata=_meta(seq=seq), evidence=ev)


def _log(n: int) -> list[Event]:
    """A committed log with contiguous seqs 1..n."""
    log: list[Event] = [
        EngagementCreated(metadata=_meta(seq=1), slug="demo", tenant_id="t_1")
    ]
    for seq in range(2, n + 1):
        log.append(_evidence_added(seq))
    return log


def _unassigned(n: int) -> list[Event]:
    return [_evidence_added(0, claim=f"u{i}") for i in range(n)]


def test_v1_version_is_last_seq() -> None:
    assert current_version(_log(7)) == 7
    assert current_version(_log(1)) == 1


def test_v2_sequence_is_version_plus_one() -> None:
    for n in (0, 1, 3):
        log = _log(n) if n else []
        assert current_sequence(log) == current_version(log) + 1


def test_v3_next_state_version_identity() -> None:
    for n in (0, 2, 5):
        log = _log(n) if n else []
        assert next_state_version(log) == current_sequence(log)


def test_v4_version_monotonic_under_append() -> None:
    log = _log(3)
    before = current_version(log)
    stamped = stamp(_unassigned(2), first_seq=current_sequence(log))
    extended = log + stamped
    assert current_version(extended) == before + 2
    assert current_version(extended) > before


def test_v5_metadata_only_derivation() -> None:
    # identical seqs, radically different payloads/event types -> same result
    log_a: list[Event] = [
        EngagementCreated(metadata=_meta(seq=1), slug="demo", tenant_id="t_1"),
        _evidence_added(2, claim="revenue fell 12%"),
    ]
    log_b: list[Event] = [
        EngagementCreated(metadata=_meta(seq=1), slug="other", tenant_id="t_2"),
        CaseClassified(
            metadata=_meta(seq=2),
            classification=CaseClassification(
                primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8
            ),
        ),
    ]
    assert current_version(log_a) == current_version(log_b) == 2
    assert current_sequence(log_a) == current_sequence(log_b) == 3


def test_v6_empty_log() -> None:
    assert current_version([]) == 0
    assert current_sequence([]) == 1


def test_v7_purity() -> None:
    log = _log(3)
    snapshot = [e.model_copy(deep=True) for e in log]
    assert current_version(log) == current_version(log)
    assert current_sequence(log) == current_sequence(log)
    assert next_state_version(log) == next_state_version(log)
    assert log == snapshot


def test_c1_first_allocation_follows_version() -> None:
    log = _log(4)
    stamped = stamp(_unassigned(3), first_seq=current_sequence(log))
    assert stamped[0].metadata.seq == current_version(log) + 1


def test_c2_multi_round_contiguity() -> None:
    log: list[Event] = []
    for batch_size in (1, 2, 3, 1):
        stamped = stamp(_unassigned(batch_size), first_seq=current_sequence(log))
        log = log + stamped
    assert [e.metadata.seq for e in log] == list(range(1, 8))


def test_c3_no_seq_reuse() -> None:
    log: list[Event] = []
    round_maxes: list[int] = []
    for batch_size in (2, 1, 3):
        stamped = stamp(_unassigned(batch_size), first_seq=current_sequence(log))
        round_seqs = [e.metadata.seq for e in stamped]
        if round_maxes:
            assert min(round_seqs) > round_maxes[-1]
        round_maxes.append(max(round_seqs))
        log = log + stamped
    all_seqs = [e.metadata.seq for e in log]
    assert len(all_seqs) == len(set(all_seqs))
