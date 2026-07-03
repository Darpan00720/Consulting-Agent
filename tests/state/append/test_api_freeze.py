"""M1.7.3-S6: edge-case verification + the final public-API freeze.

Edge-case coverage map (per the S6 instruction, already-covered cases are
referenced, not duplicated):
  S6-1 empty batch via the facade ............ test_s6_1 (pipeline level: P16/G8)
  S6-2 single vs one-element batch ........... covered by F4 (test_facade_api)
  S6-3 sequential appends vs one batch ....... test_s6_3
  S6-4 current_sequence never decreases ...... test_s6_4
  S6-5 current_version never decreases ....... test_s6_5
  S6-6 AppendResult serialization stable ..... test_s6_6
  S6-7 validate() matches direct runner ...... covered by F5 (test_facade_api)
  S6-8 documented API example executes ....... test_s6_8
"""

from __future__ import annotations

from typing import Any

import pytest

import state
from state import (
    AppendError,
    AppendErrorCode,
    AppendResult,
    AppendUnsupportedError,
    Engagement,
    EventAdmissionError,
    Evidence,
    EvidenceType,
    ValidationReport,
    VersionConflictError,
)
from state.events import EngagementCreated, EventMetadata, EventSource, EvidenceAdded
from tests.state.test_facade import EXPECTED_PUBLIC_API


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


def _engagement() -> Engagement:
    return Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")


# --- edge cases ---------------------------------------------------------------


def test_s6_1_empty_batch_via_facade() -> None:
    e = _engagement()
    with pytest.raises(EventAdmissionError, match="empty"):
        e.append_events([], expected_version=0)
    assert e.current_version() == 0


def test_s6_3_sequential_appends_equal_one_batch() -> None:
    events = [_created(), _evidence_added(), _evidence_added("c2")]
    sequential, batch = _engagement(), _engagement()
    for i, event in enumerate(events):
        sequential.append_event(event, expected_version=i)
    batch.append_events(events, expected_version=0)
    assert sequential.get_state() == batch.get_state()
    assert sequential.current_version() == batch.current_version() == 3


def test_s6_4_current_sequence_never_decreases() -> None:
    e = _engagement()
    observed = [e.current_sequence()]
    e.append_event(_created(), expected_version=0)
    observed.append(e.current_sequence())
    with pytest.raises(VersionConflictError):
        e.append_event(_evidence_added(), expected_version=0)
    observed.append(e.current_sequence())  # failure must not move it either way
    e.append_events([_evidence_added(), _evidence_added("c2")], expected_version=1)
    observed.append(e.current_sequence())
    assert observed == sorted(observed)
    assert observed == [1, 2, 2, 4]


def test_s6_5_current_version_never_decreases() -> None:
    e = _engagement()
    observed = [e.current_version()]
    e.append_event(_created(), expected_version=0)
    observed.append(e.current_version())
    with pytest.raises(EventAdmissionError):
        e.append_events([], expected_version=1)
    observed.append(e.current_version())
    e.append_event(_evidence_added(), expected_version=1)
    observed.append(e.current_version())
    assert observed == sorted(observed)
    assert observed == [0, 1, 1, 2]


def test_s6_6_append_result_serialization_stable() -> None:
    e = _engagement()
    result = e.append_events([_created(), _evidence_added()], expected_version=0)
    dumped = result.model_dump()
    assert set(dumped) == {
        "success",
        "version",
        "projection_version",
        "first_seq",
        "last_seq",
        "appended",
        "warnings",
    }
    restored = AppendResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_s6_8_documented_api_example_executes() -> None:
    # the exact usage pattern documented in docs/api/EngagementState.md
    engagement = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    assert engagement.current_version() == 0
    result = engagement.append_event(_created(), expected_version=0)
    assert result.success and result.version == 1
    report = engagement.validate()
    assert report.valid
    snapshot = engagement.get_state()
    snapshot.evidence.clear()  # snapshots are detached
    assert engagement.get_state().metadata.state_version == 1
    rehydrated = Engagement.from_json(engagement.to_json())
    with pytest.raises(AppendUnsupportedError):  # read-only until M1.8/M1.9
        rehydrated.append_event(_evidence_added(), expected_version=1)


# --- the final API freeze -------------------------------------------------------


def test_s6_public_api_freeze() -> None:
    """Any future surface change must consciously edit this test."""
    # Engagement public methods — exactly the ten frozen operations
    methods = {
        name
        for name in dir(Engagement)
        if not name.startswith("_") and callable(getattr(Engagement, name))
    }
    assert methods == {
        "create",
        "from_state",
        "from_json",
        "get_state",
        "validate",
        "to_json",
        "append_event",
        "append_events",
        "current_version",
        "current_sequence",
    }
    # state.__all__ — the curated allowlist (single source: test_facade)
    assert set(state.__all__) == EXPECTED_PUBLIC_API
    assert len(state.__all__) == 86
    # AppendResult fields
    assert set(AppendResult.model_fields) == {
        "success",
        "version",
        "projection_version",
        "first_seq",
        "last_seq",
        "appended",
        "warnings",
    }
    # AppendError hierarchy
    for concrete in (VersionConflictError, EventAdmissionError, AppendUnsupportedError):
        assert issubclass(concrete, AppendError)
    # AppendErrorCode namespace (additive-frozen)
    assert {code.value for code in AppendErrorCode} == {
        "version_conflict",
        "event_admission",
        "append_unsupported",
    }
    # ValidationReport public surface
    assert set(ValidationReport.model_fields) == {
        "valid",
        "violations",
        "counts",
        "duration_ms",
        "groups_checked",
    }
