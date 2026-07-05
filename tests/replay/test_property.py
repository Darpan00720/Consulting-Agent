"""M1.9 Phase 5 deterministic property & stress suite (RP-024…RP-030).

Correctness only — no timing, no benchmarks (Phase 6). Every fixture is built by
a deterministic generator: each event carries an explicit id and a fixed
timestamp, so a given generator call reproduces byte-identical logs across runs.
No entropy or clock sources are used (see the source-scan, RP-030).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from replay import replay
from state import Engagement, Evidence, EvidenceType
from state.append import current_version
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
    ObjectivesRecorded,
    ProblemDefined,
)
from state.projection import PROJECTION_VERSION, project

_TS = datetime(2020, 1, 1, tzinfo=UTC)  # fixed origin — never a clock read
_SIZES = [0, 1, 10, 100, 1000, 10000]  # empty … maximum approved scale


# --- deterministic generators ------------------------------------------------


def _meta(seq: int) -> EventMetadata:
    """Fully-pinned metadata: explicit id + seq + fixed timestamps."""
    return EventMetadata(
        engagement_id="eng_1",
        actor="system",
        source=EventSource.SYSTEM,
        event_id=f"ev_{seq}",
        seq=seq,
        occurred_at=_TS,
        recorded_at=_TS,
    )


def _evidence(seq: int) -> EvidenceAdded:
    return EvidenceAdded(
        metadata=_meta(seq),
        evidence=Evidence(
            claim=f"c{seq}", type=EvidenceType.CLIENT_FACT, confidence=0.5
        ),
    )


def _genesis() -> EngagementCreated:
    return EngagementCreated(metadata=_meta(1), slug="demo", tenant_id="t_1")


def _evidence_log(size: int) -> tuple[Event, ...]:
    """Genesis + (size-1) EvidenceAdded — a contiguous, genesis-led log."""
    if size == 0:
        return ()
    events: list[Event] = [_genesis()]
    events += [_evidence(seq) for seq in range(2, size + 1)]
    return tuple(events)


def _mixed_log(size: int) -> tuple[Event, ...]:
    """Genesis + a repeated cycle of three additive event categories."""
    if size == 0:
        return ()
    events: list[Event] = [_genesis()]
    for seq in range(2, size + 1):
        which = seq % 3
        if which == 0:
            events.append(_evidence(seq))
        elif which == 1:
            events.append(
                ProblemDefined(
                    metadata=_meta(seq), raw_input=f"raw{seq}", real_question=f"q{seq}"
                )
            )
        else:
            events.append(
                ObjectivesRecorded(metadata=_meta(seq), success_criteria=[f"s{seq}"])
            )
    return tuple(events)


# --- RP-024: replay is deterministic -----------------------------------------


@pytest.mark.parametrize("size", _SIZES)
def test_rp024_replay_is_deterministic(size: int) -> None:
    log = _evidence_log(size)
    first = replay(log)
    second = replay(log)
    assert first.get_state() == second.get_state()
    assert first.current_version() == second.current_version()


# --- RP-025: Replay(log) == Replay(log) (full reconstruction) ----------------


@pytest.mark.parametrize("size", _SIZES)
def test_rp025_replay_equals_replay(size: int) -> None:
    log = _mixed_log(size)
    first = replay(log)
    second = replay(log)
    assert first._pipeline.committed().log == second._pipeline.committed().log
    assert first.get_state() == second.get_state()
    assert first.current_version() == second.current_version()


# --- RP-026: fold equivalence — Replay(log).state == project(log) ------------


@pytest.mark.parametrize("size", _SIZES)
def test_rp026_fold_equivalence(size: int) -> None:
    for log in (_evidence_log(size), _mixed_log(size)):
        assert replay(log).get_state() == project(list(log))


# --- RP-027: repeated replay produces append-capable engagements -------------


@pytest.mark.parametrize("size", [1, 10, 100])
def test_rp027_repeated_replay_append_capable(size: int) -> None:
    log = _evidence_log(size)
    for _ in range(3):  # repeated replay of the same log
        engagement = replay(log)
        version = engagement.current_version()
        # an appendable event is unassigned (seq 0) so the pipeline stamps it;
        # "ev_0" is unique against the committed ids ev_1..ev_size
        result = engagement.append_event(_evidence(0), expected_version=version)
        assert result.version == version + 1


# --- RP-028: replay preserves version, sequence, and identity ----------------


@pytest.mark.parametrize("size", _SIZES)
def test_rp028_preserves_version_sequence_identity(size: int) -> None:
    log = _evidence_log(size)
    engagement = replay(log)
    expected = current_version(log)
    state = engagement.get_state()
    assert engagement.current_version() == expected
    assert state.metadata.state_version == expected
    committed_seqs = [e.metadata.seq for e in engagement._pipeline.committed().log]
    assert committed_seqs == list(range(1, size + 1))  # contiguous, preserved
    if size > 0:
        assert state.metadata.engagement_id == log[0].metadata.engagement_id


# --- RP-029: replay scales linearly over deterministic datasets (no timing) --


@pytest.mark.parametrize("size", _SIZES)
def test_rp029_scales_linearly_over_datasets(size: int) -> None:
    engagement = replay(_evidence_log(size))
    # every event is processed: output grows exactly linearly with the input,
    # with no truncation and no fabrication (structural, never a timing check)
    assert engagement.current_version() == size
    assert len(engagement._pipeline.committed().log) == size
    assert engagement.get_state().projection_version == PROJECTION_VERSION
    assert isinstance(engagement, Engagement)


# --- RP-030: the property suite is completely deterministic (source-scan) -----


def test_rp030_property_suite_is_deterministic() -> None:
    # Scan only the generators/fixtures/tests *above* this checker — this
    # function names the banned tokens (as strings), so it must exclude itself.
    src = Path(__file__).read_text(encoding="utf-8")
    generators = src.split("# --- RP-030")[0]
    for banned in (
        "import random",
        "random.",
        "uuid",
        "secrets",
        "datetime.now",
        "utcnow",
        ".now(",
        "time.time",
        "perf_counter",
        "new_event_id",
        "new_id(",
    ):
        assert banned not in generators, f"non-deterministic source: {banned!r}"
