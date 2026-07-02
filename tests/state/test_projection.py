"""M1.5 tests: projection purity, determinism, reducers, and replay-as-composition."""

from __future__ import annotations

import typing
from functools import reduce
from typing import Any

from state.enums import LifecycleStatus
from state.events import (
    AssumptionAdded,
    AssumptionInvalidated,
    CaseClassified,
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
    EvidenceValidated,
    PhaseTransitioned,
)
from state.ledgers import Assumption, AssumptionStatus, Evidence, EvidenceType
from state.projection import PROJECTION_VERSION, _apply, apply, project
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


def _created() -> EngagementCreated:
    return EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")


def _evidence() -> Evidence:
    return Evidence(claim="rev $600M", type=EvidenceType.CLIENT_FACT, confidence=0.9)


def test_empty_log_returns_empty_state() -> None:
    state = project([])
    assert state.status is LifecycleStatus.INTAKE
    assert state.projection_version == PROJECTION_VERSION
    assert state.evidence == []


def test_engagement_created_sets_metadata() -> None:
    state = project([_created()])
    assert state.metadata.slug == "demo"
    assert state.metadata.tenant_id == "t_1"


def test_apply_is_pure() -> None:
    state = project([_created()])
    before = state.model_copy(deep=True)
    new = apply(state, EvidenceAdded(metadata=_meta(), evidence=_evidence()))
    assert state == before  # input unchanged
    assert new is not state
    assert len(new.evidence) == 1


def test_projection_is_deterministic() -> None:
    log: list[Event] = [
        _created(),
        EvidenceAdded(metadata=_meta(), evidence=_evidence()),
    ]
    assert project(log) == project(log)


def test_assumption_invalidated_is_projected() -> None:
    a = Assumption(statement="s", value="v", rationale="r", owner="o", confidence=0.5)
    log: list[Event] = [
        _created(),
        AssumptionAdded(metadata=_meta(), assumption=a),
        AssumptionInvalidated(
            metadata=_meta(), assumption_id=a.id, statement="s", reason="disproved"
        ),
    ]
    assert project(log).assumptions[0].status is AssumptionStatus.INVALIDATED


def test_evidence_validated_is_projected() -> None:
    ev = _evidence()
    log: list[Event] = [
        _created(),
        EvidenceAdded(metadata=_meta(), evidence=ev),
        EvidenceValidated(
            metadata=_meta(), evidence_id=ev.id, claim=ev.claim, validator="reviewer"
        ),
    ]
    projected = project(log).evidence[0]
    assert projected.validated is True
    assert projected.validator == "reviewer"


def test_phase_transition_updates_status_and_history() -> None:
    log: list[Event] = [
        _created(),
        PhaseTransitioned(
            metadata=_meta(),
            from_status=LifecycleStatus.INTAKE,
            to_status=LifecycleStatus.ANALYSIS,
        ),
    ]
    state = project(log)
    assert state.status is LifecycleStatus.ANALYSIS
    assert state.phase_history[-1].phase is LifecycleStatus.ANALYSIS


def test_classification_is_projected() -> None:
    cls = CaseClassification(
        primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8
    )
    state = project([_created(), CaseClassified(metadata=_meta(), classification=cls)])
    assert state.classification is not None
    assert state.classification.primary_archetype is CaseArchetype.PROFITABILITY


def test_replay_is_composition_of_project() -> None:
    log: list[Event] = [
        _created(),
        EvidenceAdded(metadata=_meta(), evidence=_evidence()),
    ]
    assert reduce(apply, log, project([])) == project(log)


def test_every_event_type_has_a_reducer() -> None:
    members = typing.get_args(typing.get_args(Event)[0])
    registered = set(_apply.registry.keys())
    for member in members:
        assert member in registered, f"no reducer for {member.__name__}"


# --- M1.7.2 (design D4): fold-derived state_version --------------------------


def _sequenced_log(n: int) -> list[Event]:
    """A log of n events with contiguous 1-based seq."""
    log: list[Event] = [
        EngagementCreated(metadata=_meta(seq=1), slug="demo", tenant_id="t_1")
    ]
    for seq in range(2, n + 1):
        log.append(EvidenceAdded(metadata=_meta(seq=seq), evidence=_evidence()))
    return log


def test_empty_projection_has_state_version_zero() -> None:
    state = project([])
    assert state.metadata.state_version == 0
    assert state.projection_version == PROJECTION_VERSION


def test_single_event_projection_derives_state_version() -> None:
    assert project(_sequenced_log(1)).metadata.state_version == 1


def test_multi_event_projection_derives_state_version() -> None:
    assert project(_sequenced_log(5)).metadata.state_version == 5


def test_reprojection_yields_identical_state_version() -> None:
    log = _sequenced_log(3)
    first, second = project(log), project(log)
    assert first == second
    assert first.metadata.state_version == second.metadata.state_version == 3


def test_projection_version_is_2() -> None:
    assert PROJECTION_VERSION == 2
    assert project([]).projection_version == 2
    assert project(_sequenced_log(2)).projection_version == 2


def test_manual_state_version_cannot_influence_projection() -> None:
    log = _sequenced_log(2)
    tampered = project(log)
    tampered.metadata.state_version = 999
    # applying the next event derives the version from the event, not the input
    next_event = EvidenceAdded(metadata=_meta(seq=3), evidence=_evidence())
    assert apply(tampered, next_event).metadata.state_version == 3
    # and a fresh projection of the same log is untouched by the tampering
    assert project(log).metadata.state_version == 2
