"""Tests that the deliverable catalog is complete and every entry is
well-formed — the requester's exhaustive named list, verified as data."""

from __future__ import annotations

from app.deliverables.catalog import all_deliverable_definitions
from app.deliverables.models import Audience
from app.deliverables.sections import get_section_definition, resolve_order

_EXPECTED_TYPES = {
    "executive_summary",
    "board_presentation",
    "strategy_memorandum",
    "business_case",
    "market_entry_report",
    "transformation_roadmap",
    "digital_transformation_strategy",
    "ai_strategy_report",
    "operational_excellence_report",
    "due_diligence_report",
    "implementation_roadmap",
    "pmo_status_report",
    "risk_assessment_report",
    "executive_briefing",
    "steering_committee_deck",
    "workshop_pack",
    "client_proposal",
    "investment_committee_memo",
    "post_engagement_report",
    "lessons_learned",
}


def test_catalog_has_20_unique_types_matching_the_requested_list():
    defs = all_deliverable_definitions()
    ids = {d.id for d in defs}
    assert len(defs) == 20
    assert ids == _EXPECTED_TYPES


def test_every_deliverable_has_required_fields_populated():
    for d in all_deliverable_definitions():
        assert d.id, d
        assert d.name, d.id
        assert d.purpose, d.id
        assert d.audience, d.id
        assert d.template, d.id
        assert d.required_sections, d.id
        assert d.supported_engagement_types, d.id
        assert d.owner


def test_every_required_and_optional_section_resolves_to_a_real_definition():
    for d in all_deliverable_definitions():
        for sid in (*d.required_sections, *d.optional_sections):
            get_section_definition(sid)  # raises if unknown


def test_every_deliverable_required_sections_resolve_a_valid_order():
    for d in all_deliverable_definitions():
        order = resolve_order(d.required_sections)
        assert set(order) == set(d.required_sections)


def test_every_audience_is_used_by_at_least_one_deliverable():
    used = {a for d in all_deliverable_definitions() for a in d.audience}
    assert used == set(Audience)


def test_no_duplicate_ids():
    defs = all_deliverable_definitions()
    ids = [d.id for d in defs]
    assert len(ids) == len(set(ids))
