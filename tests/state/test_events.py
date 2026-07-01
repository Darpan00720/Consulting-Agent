"""M1.4 event tests: immutability, actor/source, times, categories, and union."""

from __future__ import annotations

import typing

import pytest
from pydantic import TypeAdapter, ValidationError

from state import events
from state.enums import LifecycleStatus
from state.events import (
    EVENT_CATEGORIES,
    EngagementCreated,
    Event,
    EventCategory,
    EventMetadata,
    EventSource,
    EventType,
    EvidenceValidated,
    PhaseTransitioned,
)


def _meta() -> EventMetadata:
    return EventMetadata(
        engagement_id="eng_1", actor="system", source=EventSource.SYSTEM
    )


def test_event_constructs_with_metadata() -> None:
    e = EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")
    assert e.type is EventType.ENGAGEMENT_CREATED
    assert e.metadata.schema_version == 1


def test_business_and_system_times_present() -> None:
    m = _meta()
    assert m.occurred_at is not None
    assert m.recorded_at is not None


def test_actor_and_source_are_distinct() -> None:
    m = EventMetadata(
        engagement_id="e", actor="financial-analyst", source=EventSource.AGENT
    )
    assert m.actor == "financial-analyst"
    assert m.source is EventSource.AGENT


def test_event_is_immutable() -> None:
    e = PhaseTransitioned(
        metadata=_meta(),
        from_status=LifecycleStatus.INTAKE,
        to_status=LifecycleStatus.CLASSIFYING,
    )
    with pytest.raises(ValidationError):
        e.from_status = LifecycleStatus.PLANNING


def test_metadata_is_immutable() -> None:
    m = _meta()
    with pytest.raises(ValidationError):
        m.actor = "someone-else"


def test_discriminated_union_round_trip() -> None:
    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    original = EvidenceValidated(
        metadata=_meta(), evidence_id="ev_1", claim="rev $600M", validator="reviewer"
    )
    parsed = adapter.validate_json(adapter.dump_json(original))
    assert isinstance(parsed, EvidenceValidated)
    assert parsed == original


def test_every_event_type_maps_to_exactly_one_category() -> None:
    assert set(EVENT_CATEGORIES) == set(EventType)
    assert all(isinstance(cat, EventCategory) for cat in EVENT_CATEGORIES.values())


def _union_members() -> tuple[type, ...]:
    return typing.get_args(typing.get_args(Event)[0])


def test_union_covers_every_event_type() -> None:
    declared = {member.model_fields["type"].default for member in _union_members()}
    assert declared == set(EventType)


def test_all_event_classes_exported() -> None:
    for member in _union_members():
        assert member.__name__ in events.__all__
