"""M1.7.3-S5 invariant tests F1-F10: facade event API (one test per invariant)."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

import state.facade as facade_module
from state import (
    AppendErrorCode,
    AppendUnsupportedError,
    Engagement,
    EngagementProtocol,
    Evidence,
    EvidenceType,
    VersionConflictError,
)
from state.append import AppendPipeline
from state.events import EngagementCreated, EventMetadata, EventSource, EvidenceAdded
from state.models import EngagementMetadata, EngagementState
from state.validation import validate as run_validation


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


def test_f1_append_apis_delegate_exactly_once() -> None:
    e = _engagement()
    e.append_event(_created(), expected_version=0)
    assert e.current_version() == 1  # exactly one pipeline append happened
    e.append_events([_evidence_added(), _evidence_added("c2")], expected_version=1)
    assert e.current_version() == 3  # exactly +k, not doubled
    assert e.get_state().metadata.state_version == 3


def test_f2_current_version_reads_stored_version() -> None:
    src = inspect.getsource(Engagement.current_version)
    assert "committed().version" in src
    assert "derive_current_sequence" not in src
    e = _engagement()
    assert e.current_version() == 0
    e.append_event(_created(), expected_version=0)
    assert e.current_version() == e.get_state().metadata.state_version == 1


def test_f3_current_sequence_delegates_to_s2() -> None:
    src = inspect.getsource(Engagement.current_sequence)
    assert "derive_current_sequence(" in src
    e = _engagement()
    assert e.current_sequence() == 1
    e.append_event(_created(), expected_version=0)
    assert e.current_sequence() == e.current_version() + 1 == 2


def test_f4_append_event_equals_single_batch() -> None:
    event = _created()
    a, b = _engagement(), _engagement()
    result_a = a.append_event(event, expected_version=0)
    result_b = b.append_events([event], expected_version=0)
    assert result_a == result_b
    assert a.get_state() == b.get_state()
    with pytest.raises(VersionConflictError):
        a.append_event(_evidence_added(), expected_version=0)
    with pytest.raises(VersionConflictError):
        b.append_events([_evidence_added()], expected_version=0)


def test_f5_validation_report_passed_through_unaltered() -> None:
    e = _engagement()
    e.append_event(_created(), expected_version=0)
    via_facade = e.validate()
    direct = run_validation(e.get_state())
    assert via_facade.valid == direct.valid
    assert via_facade.counts == direct.counts
    assert via_facade.violations == direct.violations
    assert via_facade.groups_checked == direct.groups_checked
    # duration_ms is timing, not contract — deliberately not compared


def test_f6_snapshot_semantics_unchanged() -> None:
    e = _engagement()
    e.append_event(_created(), expected_version=0)
    e.append_event(_evidence_added(), expected_version=1)
    pristine = e.get_state()
    snapshot = e.get_state()
    snapshot.evidence.clear()
    snapshot.metadata.slug = "mutated"
    assert e.get_state() == pristine
    adopted_source = e.get_state()
    adopted = Engagement.from_state(adopted_source)
    adopted_source.evidence.clear()
    assert len(adopted.get_state().evidence) == 1  # copy-on-ingest held


def test_f7_facade_imports_only_public_append_surface() -> None:
    src = Path(facade_module.__file__).read_text(encoding="utf-8")
    assert "from state.append import" in src
    for module in ("pipeline", "commit", "guard", "sequencing", "versioning"):
        assert f"state.append.{module}" not in src
    assert "metadata.seq" not in src
    assert "from state.validation import" in src


def test_f8_public_api_matches_protocol_exactly() -> None:
    protocol_methods = {
        name for name in dir(EngagementProtocol) if not name.startswith("_")
    }
    engagement_methods = {
        name
        for name in dir(Engagement)
        if not name.startswith("_") and callable(getattr(Engagement, name))
    }
    assert engagement_methods == protocol_methods
    assert len(engagement_methods) == 10


def test_f9_read_only_adopted_engagements_reject_append() -> None:
    # from_state — even a fresh, internally consistent state (no heuristics)
    bare = EngagementState(
        metadata=EngagementMetadata(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    )
    adopted = Engagement.from_state(bare)
    before = adopted.get_state()
    for attempt in ("event", "events"):
        with pytest.raises(AppendUnsupportedError) as excinfo:
            if attempt == "event":
                adopted.append_event(_created(), expected_version=0)
            else:
                adopted.append_events([_created()], expected_version=0)
        assert excinfo.value.error_code is AppendErrorCode.APPEND_UNSUPPORTED
    assert adopted.get_state() == before
    assert adopted.current_version() == 0
    # from_json — the original motivating case: a mid-flight round-trip
    native = _engagement()
    native.append_event(_created(), expected_version=0)
    rehydrated = Engagement.from_json(native.to_json())
    with pytest.raises(AppendUnsupportedError):
        rehydrated.append_event(_evidence_added(), expected_version=1)
    # direct pipeline construction behaves identically
    pipeline = AppendPipeline(bare, append_supported=False)
    assert pipeline.append_supported is False
    with pytest.raises(AppendUnsupportedError):
        pipeline.append_event(_created(), expected_version=0)


def test_f10_pipeline_native_engagements_accept_append() -> None:
    e = _engagement()
    e.append_event(_created(), expected_version=0)
    with pytest.raises(VersionConflictError):
        e.append_event(_evidence_added(), expected_version=0)
    e.append_event(_evidence_added(), expected_version=1)  # still accepts
    assert e.current_version() == 2
    bare = EngagementState(
        metadata=EngagementMetadata(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    )
    assert AppendPipeline(bare).append_supported is True
