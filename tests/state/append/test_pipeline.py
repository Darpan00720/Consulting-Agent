"""M1.7.3-S4 invariant tests P1-P23: append pipeline (one test per invariant)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest

import state.append.pipeline as pipeline_module
from state.append import (
    AppendPipeline,
    CandidateCommit,
    EventAdmissionError,
    StateUpdater,
    VersionConflictError,
    check_append,
    current_version,
    make_committed,
)
from state.enums import LifecycleStatus
from state.events import (
    EngagementCreated,
    EngagementFailed,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
    PhaseTransitioned,
)
from state.identifiers import EngagementId
from state.ledgers import Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.projection import PROJECTION_VERSION, apply, project
from state.validation import StateValidationError, validate

from .spies import SpyStateUpdater

_REPO = Path(__file__).resolve().parents[3]


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _created() -> EngagementCreated:
    return EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")


def _evidence_added(claim: str = "c") -> EvidenceAdded:
    ev = Evidence(claim=claim, type=EvidenceType.CLIENT_FACT, confidence=0.5)
    return EvidenceAdded(metadata=_meta(), evidence=ev)


def _initial_state() -> EngagementState:
    return EngagementState(
        metadata=EngagementMetadata(
            engagement_id=EngagementId("eng_1"), tenant_id="t_1", slug="demo"
        )
    )


def _pipeline(updater_cls: type[StateUpdater] = StateUpdater) -> AppendPipeline:
    return AppendPipeline(_initial_state(), updater_cls=updater_cls)


def _blocking_event() -> PhaseTransitioned:
    # INTAKE -> REPORTING: LIFE-001 + LIFE-003 (both ERROR) on the post-state
    return PhaseTransitioned(
        metadata=_meta(),
        from_status=LifecycleStatus.INTAKE,
        to_status=LifecycleStatus.REPORTING,
    )


def test_p1_single_append_commits() -> None:
    p = _pipeline()
    pre = p.committed().state
    result = p.append_event(_created(), expected_version=0)
    c = p.committed()
    assert len(c.log) == 1
    assert c.version == 1
    assert c.state == apply(pre, c.log[0])
    assert result.version == 1


def test_p2_batch_append_commits_atomically() -> None:
    p = _pipeline()
    p.append_events(
        [_created(), _evidence_added(), _evidence_added("c2")], expected_version=0
    )
    c = p.committed()
    assert [e.metadata.seq for e in c.log] == [1, 2, 3]
    assert c.version == 3


def test_p3_byte_identical_after_admission_failure() -> None:
    p = _pipeline()
    p.append_event(_created(), expected_version=0)
    before = p.committed()
    pre_stamped = EvidenceAdded(
        metadata=_meta(seq=9),
        evidence=Evidence(claim="x", type=EvidenceType.CLIENT_FACT, confidence=0.5),
    )
    with pytest.raises(EventAdmissionError):
        p.append_event(pre_stamped, expected_version=1)
    after = p.committed()
    assert after is before
    assert after.state.model_dump_json() == before.state.model_dump_json()


def test_p4_byte_identical_after_version_conflict() -> None:
    p = _pipeline()
    before = p.committed()
    with pytest.raises(VersionConflictError):
        p.append_event(_created(), expected_version=99)
    assert p.committed() is before


def test_p5_byte_identical_after_validation_rejection() -> None:
    p = _pipeline()
    p.append_event(_created(), expected_version=0)
    before = p.committed()
    with pytest.raises(StateValidationError):
        p.append_event(_blocking_event(), expected_version=1)
    after = p.committed()
    assert after is before
    assert after.state.model_dump_json() == before.state.model_dump_json()


def test_p6_no_partial_commit_on_mid_batch_defect() -> None:
    p = _pipeline()
    before = p.committed()
    foreign = EvidenceAdded(
        metadata=_meta(engagement_id="eng_B"),
        evidence=Evidence(claim="b", type=EvidenceType.CLIENT_FACT, confidence=0.5),
    )
    with pytest.raises(EventAdmissionError):
        p.append_events([_created(), _evidence_added(), foreign], expected_version=0)
    assert p.committed() is before
    assert p.committed().version == 0


def test_p7_failures_consume_no_sequence_numbers() -> None:
    p = _pipeline()
    with pytest.raises(VersionConflictError):
        p.append_event(_created(), expected_version=5)
    with pytest.raises(EventAdmissionError):
        p.append_events([], expected_version=0)
    p.append_event(_created(), expected_version=0)
    c = p.committed()
    assert c.version == 1
    assert c.log[0].metadata.seq == 1  # no gap from the failed attempts


def test_p8_validation_precedes_commit() -> None:
    p = _pipeline(updater_cls=SpyStateUpdater)
    spy = cast(SpyStateUpdater, p.updater)
    p.append_event(_created(), expected_version=0)
    assert spy.commit_count == 1
    with pytest.raises(StateValidationError):
        p.append_event(_blocking_event(), expected_version=1)
    assert spy.commit_count == 1  # blocking candidate never reached commit
    # warnings-only states DO commit (LIFE-004 via EngagementFailed)
    p.append_event(
        PhaseTransitioned(
            metadata=_meta(),
            from_status=LifecycleStatus.INTAKE,
            to_status=LifecycleStatus.CLASSIFYING,
        ),
        expected_version=1,
    )
    result = p.append_event(
        EngagementFailed(metadata=_meta(), reason="client cancelled"),
        expected_version=2,
    )
    assert spy.commit_count == 3
    assert any(v.rule_id == "LIFE-004" for v in result.warnings)


def test_p9_commit_occurs_exactly_once() -> None:
    p = _pipeline(updater_cls=SpyStateUpdater)
    spy = cast(SpyStateUpdater, p.updater)
    p.append_event(_created(), expected_version=0)
    assert spy.commit_count == 1
    p.append_events([_evidence_added(), _evidence_added("c2")], expected_version=1)
    assert spy.commit_count == 2  # one commit for the whole batch
    with pytest.raises(VersionConflictError):
        p.append_event(_evidence_added("c3"), expected_version=0)
    assert spy.commit_count == 2  # failures never commit


def test_p10_append_result_bookkeeping() -> None:
    p = _pipeline()
    result = p.append_events(
        [_created(), _evidence_added(), _evidence_added("c2")], expected_version=0
    )
    assert result.success is True
    assert result.version == 3
    assert result.projection_version == PROJECTION_VERSION
    assert result.first_seq == 1
    assert result.last_seq == 3
    assert result.appended == 3
    assert result.warnings == []


def test_p11_fold_equivalence() -> None:
    p = _pipeline()
    p.append_events([_created(), _evidence_added()], expected_version=0)
    c = p.committed()
    projected = project(list(c.log))
    # equal modulo projection provenance: apply() must not fabricate the
    # full-projection stamp, so only projection_version may differ (0 vs 2)
    exclude = {"projection_version"}
    assert projected.model_dump(exclude=exclude) == c.state.model_dump(exclude=exclude)
    assert projected.metadata.state_version == c.state.metadata.state_version == 2


def test_p12_idempotency_at_pipeline_level() -> None:
    p = _pipeline()
    event = _created()
    p.append_event(event, expected_version=0)
    with pytest.raises(EventAdmissionError, match="already committed"):
        p.append_event(event, expected_version=1)


def test_p13_caller_events_never_mutated() -> None:
    p = _pipeline()
    events: list[Event] = [_created(), _evidence_added()]
    snapshots = [e.model_copy(deep=True) for e in events]
    p.append_events(events, expected_version=0)
    assert events == snapshots
    assert all(e.metadata.seq == 0 for e in events)


def test_p14_determinism_across_pipelines() -> None:
    events: list[Event] = [_created(), _evidence_added()]
    a, b = _pipeline(), _pipeline()
    a.append_events(events, expected_version=0)
    b.append_events(events, expected_version=0)
    assert a.committed().log == b.committed().log
    assert a.committed().state == b.committed().state
    assert a.committed().version == b.committed().version


def test_p15_boundary_raises_guard_error() -> None:
    p = _pipeline()
    event = _created()
    with pytest.raises(VersionConflictError) as excinfo:
        p.append_event(event, expected_version=7)
    reference = check_append(
        [event],
        engagement_id=EngagementId("eng_1"),
        committed_version=0,
        committed_event_ids=frozenset(),
        expected_version=7,
    )
    assert reference.error is not None
    raised = excinfo.value
    assert type(raised) is type(reference.error)
    assert raised.error_code is reference.error.error_code
    assert raised.expected == 7
    assert raised.actual == 0
    assert str(raised) == str(reference.error)


def test_p16_empty_batch_rejected() -> None:
    p = _pipeline()
    before = p.committed()
    with pytest.raises(EventAdmissionError, match="empty"):
        p.append_events([], expected_version=0)
    assert p.committed() is before


def test_p17_pipeline_performs_no_arithmetic() -> None:
    src = Path(pipeline_module.__file__).read_text(encoding="utf-8")
    assert "metadata.seq" not in src
    assert re.search(r"[+\-]\s*1\b", src) is None  # no ±1 version/seq math
    assert "current_sequence" in src and "current_version" in src  # S2 only
    assert "stamp(" in src


def test_p18_stored_version_consistency() -> None:
    p = _pipeline()
    c0 = p.committed()
    assert c0.version == current_version(c0.log) == 0
    p.append_events([_created(), _evidence_added()], expected_version=0)
    c1 = p.committed()
    assert c1.version == current_version(c1.log) == 2


def test_p19_pipeline_owns_no_business_rules() -> None:
    src = Path(pipeline_module.__file__).read_text(encoding="utf-8")
    for module in ("business", "lifecycle", "governance", "structural", "referential"):
        assert (
            f"validation.{module}" not in src
        ), f"pipeline imports rule module {module}"
    assert "from state.validation import" in src  # runner surface only


def test_p20_candidate_is_complete_commit_payload() -> None:
    p = _pipeline(updater_cls=SpyStateUpdater)
    spy = cast(SpyStateUpdater, p.updater)
    prior_log = p.committed().log
    p.append_events([_created(), _evidence_added()], expected_version=0)
    candidate = spy.last_candidate
    assert candidate is not None
    assert candidate.log == prior_log + candidate.events
    assert candidate.events == p.committed().log[-2:]
    assert [e.metadata.seq for e in candidate.events] == [1, 2]


def test_p21_single_construction_path_in_packages() -> None:
    pattern = re.compile(r"\bCommitted" + r"\(")
    offenders: dict[str, int] = {}
    for path in (_REPO / "packages").rglob("*.py"):
        hits = len(pattern.findall(path.read_text(encoding="utf-8")))
        if hits:
            offenders[path.name] = hits
    assert offenders == {"commit.py": 1}, offenders


def test_p22_make_committed_is_referentially_transparent() -> None:
    initial = _initial_state()
    candidate = CandidateCommit(
        log=(),
        state=initial,
        event_ids=frozenset(),
        validation_report=validate(initial),
        events=(),
    )
    first = make_committed(candidate)
    second = make_committed(candidate)
    assert first == second
    assert first is not second
    assert first.version == second.version == 0


def test_p23_no_alternative_committed_construction_path() -> None:
    pattern = re.compile(r"\bCommitted" + r"\(")
    offenders: dict[str, int] = {}
    for root in ("packages", "tests", "scripts"):
        for path in (_REPO / root).rglob("*.py"):
            hits = len(pattern.findall(path.read_text(encoding="utf-8")))
            if hits:
                offenders[path.name] = hits
    assert offenders == {"commit.py": 1}, offenders
