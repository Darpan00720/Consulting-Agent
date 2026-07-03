"""M1.7.6 ownership-dataset completeness tests (data only — no enforcement)."""

from __future__ import annotations

import json
from pathlib import Path

from state.events import EventType
from state.models import EngagementState
from state.ownership import (
    COMPONENT_OWNERSHIP,
    EVENT_OWNERSHIP,
    SECTION_OWNERSHIP,
    Role,
)

_JSON = Path(__file__).resolve().parents[2] / ("docs/implementation/traceability.json")


def test_every_writable_resource_has_exactly_one_owner() -> None:
    resources: list[str] = []
    for row in COMPONENT_OWNERSHIP:
        resources.extend(row.writes)
    assert resources, "no writable resources declared"
    assert len(resources) == len(set(resources)), (
        "a writable resource has more than one owner: "
        f"{[r for r in resources if resources.count(r) > 1]}"
    )


def test_write_ownership_is_pairwise_disjoint() -> None:
    rows = [row for row in COMPONENT_OWNERSHIP if row.writes]
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            overlap = set(a.writes) & set(b.writes)
            assert not overlap, f"{a.component} and {b.component}: {overlap}"


def test_component_names_unique_and_rows_complete() -> None:
    names = [row.component for row in COMPONENT_OWNERSHIP]
    assert len(names) == len(set(names))
    assert len(names) == 16
    for row in COMPONENT_OWNERSHIP:
        assert row.owner and row.reason and row.evidence and row.enforcement
        assert row.status in {"verified", "design"}


def test_all_adr_sections_represented_and_fields_drift_free() -> None:
    sections = [row.section for row in SECTION_OWNERSHIP]
    assert len(sections) == len(set(sections))
    assert sum(1 for row in SECTION_OWNERSHIP if row.adr) == 26
    # every EngagementState field maps to exactly one section row
    mapped: list[str] = []
    for row in SECTION_OWNERSHIP:
        mapped.extend(row.fields)
    assert len(mapped) == len(set(mapped)), "a field is mapped twice"
    assert set(mapped) == set(EngagementState.model_fields), (
        "section/field drift: "
        f"unmapped={set(EngagementState.model_fields) - set(mapped)} "
        f"stale={set(mapped) - set(EngagementState.model_fields)}"
    )


def test_all_event_types_mapped() -> None:
    assert set(EVENT_OWNERSHIP) == set(
        EventType
    ), f"unmapped events: {set(EventType) - set(EVENT_OWNERSHIP)}"


def test_event_sections_reference_known_sections() -> None:
    known = {row.section for row in SECTION_OWNERSHIP}
    for event_type, ownership in EVENT_OWNERSHIP.items():
        assert ownership.writers, f"{event_type} has no writer"
        for section in ownership.sections:
            assert section in known, f"{event_type} -> unknown {section!r}"


def test_ownership_references_valid_roles() -> None:
    for row in SECTION_OWNERSHIP:
        for role in (*row.write, *row.update, *row.approve, *row.reject):
            assert isinstance(role, Role)
    for ownership in EVENT_OWNERSHIP.values():
        for role in ownership.writers:
            assert isinstance(role, Role)


def test_traceability_output_includes_ownership() -> None:
    committed = json.loads(_JSON.read_text(encoding="utf-8"))
    ownership = committed["ownership"]
    assert len(ownership["components"]) == len(COMPONENT_OWNERSHIP)
    assert len(ownership["sections"]) == len(SECTION_OWNERSHIP)
    assert len(ownership["events"]) == len(EVENT_OWNERSHIP) == 49


def test_adr_fidelity_spot_checks() -> None:
    by_section = {row.section: row for row in SECTION_OWNERSHIP}
    # Reviewer Notes: Reviewer across all five ADR-002 columns
    reviewer_notes = by_section["Reviewer Notes"]
    assert (
        reviewer_notes.write
        == reviewer_notes.update
        == reviewer_notes.approve
        == reviewer_notes.reject
        == (Role.REVIEWER,)
    )
    # Audit Trail: append-only by all, mutable by none
    audit = by_section["Audit Trail"]
    assert audit.write == (Role.ALL,) and audit.update == ()
    # Financial Analysis: owner-exclusive analyst; Reviewer/Challenger gates
    fin = by_section["Financial Analysis"]
    assert fin.write == (Role.FINANCIAL_ANALYST,)
    assert fin.reject == (Role.REVIEWER, Role.CHALLENGER)
    # Recommendations: rejected by Challenger, Reviewer, Human (ADR order)
    rec = by_section["Recommendations"]
    assert rec.reject == (Role.CHALLENGER, Role.REVIEWER, Role.HUMAN)
    # Event-level: PhaseTransitioned is Manager-written, Lifecycle-scoped
    phase = EVENT_OWNERSHIP[EventType.PHASE_TRANSITIONED]
    assert phase.writers == (Role.MANAGER,)
    assert phase.sections == ("Lifecycle Status",)
