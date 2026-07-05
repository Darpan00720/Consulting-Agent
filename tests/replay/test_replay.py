"""M1.9 Phase 3 replay-implementation invariant tests (RP-001…RP-017).

One deterministic test per invariant this slice implements. The log-only replay
path always produces the canonical pair (``state = project(log)`` carries the
current ``PROJECTION_VERSION``), so the provenance/recovery invariants
RP-007/008/009 are **not** exercisable here — they belong to the recovery slice
(a persisted snapshot input) and are deliberately out of scope.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import replay as replay_pkg
import replay.engine as replay_engine
from replay import ReplayEngine
from state import Engagement, Evidence, EvidenceType
from state.append import (
    ReplayErrorCode,
    ReplayIntegrityError,
    SnapshotMismatchError,
    current_version,
)
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.projection import project


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


def _valid_log(n_evidence: int = 2) -> tuple[Event, ...]:
    """A genesis-led committed log (length 1 + n_evidence), built via the pipeline."""
    e = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    events: list[Event] = [
        EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")
    ]
    events += [_evidence(f"c{i}") for i in range(n_evidence)]
    e.append_events(events, expected_version=0)
    return e._pipeline.committed().log


# --- RP-001 / RP-017: single verified path, integrity never bypassed ---------


def test_rp001_rp017_integrity_gates_invoked_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = _valid_log()
    order: list[str] = []
    real_vl = replay_engine.verify_log
    real_vp = replay_engine.verify_pair

    def spy_vl(events: Any) -> None:
        order.append("verify_log")
        real_vl(events)

    def spy_vp(events: Any, snapshot: Any) -> None:
        order.append("verify_pair")
        real_vp(events, snapshot)

    monkeypatch.setattr(replay_engine, "verify_log", spy_vl)
    monkeypatch.setattr(replay_engine, "verify_pair", spy_vp)

    engagement = ReplayEngine().replay(log)
    # both gates ran, in the mandated order, before an Engagement was produced
    assert order == ["verify_log", "verify_pair"]
    assert isinstance(engagement, Engagement)


def test_rp017_verify_pair_failure_aborts_with_no_engagement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log = _valid_log()

    def boom(events: Any, snapshot: Any) -> None:
        raise SnapshotMismatchError(
            "injected", error_code=ReplayErrorCode.STATE_VERSION_MISMATCH
        )

    monkeypatch.setattr(replay_engine, "verify_pair", boom)
    with pytest.raises(ReplayIntegrityError):
        ReplayEngine().replay(log)  # integrity failure is never swallowed


# --- RP-006: invalid log is refused (fatal), no partial reconstruction -------


def test_rp006_invalid_log_refused() -> None:
    lone = _evidence("orphan")  # non-genesis first event → GENESIS_MISSING
    with pytest.raises(ReplayIntegrityError):
        replay_pkg.replay([lone])


# --- RP-003: determinism -----------------------------------------------------


def test_rp003_determinism() -> None:
    log = _valid_log()
    a = replay_pkg.replay(log)
    b = replay_pkg.replay(log)
    assert a.get_state() == b.get_state()
    assert a.current_version() == b.current_version()


# --- RP-004: fold equivalence (replay state == project(log)) -----------------


def test_rp004_fold_equivalence() -> None:
    log = _valid_log()
    assert replay_pkg.replay(log).get_state() == project(list(log))


# --- RP-005: repeated-replay stability (fixpoint) ----------------------------


def test_rp005_repeated_replay_stable() -> None:
    log = _valid_log()
    once = replay_pkg.replay(log)
    twice = replay_pkg.replay(once._pipeline.committed().log)
    assert twice.get_state() == once.get_state()
    assert twice._pipeline.committed().log == once._pipeline.committed().log


# --- RP-010: replayed engagement is append-capable ---------------------------


def test_rp010_append_capable() -> None:
    engagement = replay_pkg.replay(_valid_log())
    version = engagement.current_version()
    result = engagement.append_event(_evidence("after"), expected_version=version)
    assert result.version == version + 1


# --- RP-011: no input mutation -----------------------------------------------


def test_rp011_no_input_mutation() -> None:
    log = _valid_log()
    before = list(log)
    replay_pkg.replay(log)
    assert list(log) == before  # unchanged: same events, same order
    assert tuple(before) == log


# --- RP-012: no fabrication / repair (committed log == input log) ------------


def test_rp012_no_fabrication_or_repair() -> None:
    log = _valid_log()
    engagement = replay_pkg.replay(log)
    assert engagement._pipeline.committed().log == log  # nothing added/dropped


# --- RP-013: version triangle ------------------------------------------------


def test_rp013_version_triangle() -> None:
    log = _valid_log()
    engagement = replay_pkg.replay(log)
    expected = current_version(log)
    assert engagement.current_version() == expected
    assert engagement.get_state().metadata.state_version == expected


# --- RP-016: observationally pure — stateless, reusable engine ---------------


def test_rp016_engine_is_stateless_and_reusable() -> None:
    engine = ReplayEngine()
    log = _valid_log()
    a = engine.replay(log)
    b = engine.replay(log)
    assert a is not b  # a fresh immutable engagement each call
    assert a.get_state() == b.get_state()  # engine carries no state between calls


# --- RP-002 / RP-014: no duplicated frozen logic (source-scan) ---------------


def test_rp002_rp014_no_duplicated_frozen_logic() -> None:
    src = Path(replay_engine.__file__).read_text(encoding="utf-8")
    for seam in ("verify_log", "verify_pair", "project", "AppendPipeline"):
        assert seam in src, seam  # the frozen seams are called
    for banned in (
        "def project",
        "def verify_log",
        "def verify_pair",
        "def apply",
        "current_version(",
        "current_sequence(",
        "next_state_version(",
        "stamp(",
        "make_committed(",  # invoked transitively by AppendPipeline, never here
    ):
        assert banned not in src, banned


# --- RP-015: replay is IO-free and persistence-independent (source-scan) -----


def test_rp015_replay_is_io_free() -> None:
    replay_dir = Path(replay_pkg.__file__).parent
    for module in sorted(replay_dir.glob("*.py")):
        src = module.read_text(encoding="utf-8")
        for banned in (
            "import persistence",
            "from persistence",
            "open(",
            "os.",
            "pathlib",
            "hashlib",
            "Path(",
        ):
            assert banned not in src, f"{module.name} must be IO-free; found {banned!r}"
