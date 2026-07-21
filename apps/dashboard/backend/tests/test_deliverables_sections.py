"""Tests for the shared section library, section generation, and ordering
rules."""

from __future__ import annotations

import pytest

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.deliverables.errors import MissingTraceabilityError, UnknownSectionError
from app.deliverables.section_builder import build_section
from app.deliverables.sections import (
    all_section_definitions,
    get_section_definition,
    resolve_order,
)
from app.synthesis import tracking as stracking
from app.synthesis.state import SynthesisState


def _synthesis_state():
    engine = ConsultingEngine()
    cstate = engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="t1"
    )
    ev = ctracking.add_evidence(
        cstate,
        "report",
        EvidenceSourceType.EXTERNAL_RESEARCH,
        EvidenceQuality.HIGH,
        0.8,
        "x",
    )
    return SynthesisState(engagement_state=cstate), ev


def test_all_14_sections_are_unique():
    defs = all_section_definitions()
    assert len(defs) == 14
    assert len({d.id for d in defs}) == 14


def test_get_unknown_section_raises():
    with pytest.raises(UnknownSectionError):
        get_section_definition("ghost")


def test_resolve_order_is_dependency_consistent():
    order = resolve_order(("recommendations", "core_insights", "key_findings"))
    assert order.index("key_findings") < order.index("core_insights")
    assert order.index("core_insights") < order.index("recommendations")


def test_resolve_order_rejects_unknown_section():
    with pytest.raises(UnknownSectionError):
        resolve_order(("ghost",))


def test_build_section_unknown_section_raises():
    syn, _ev = _synthesis_state()
    with pytest.raises(UnknownSectionError):
        build_section("ghost", syn)


def test_build_section_refuses_empty_content():
    syn, _ev = _synthesis_state()
    with pytest.raises(MissingTraceabilityError):
        build_section("key_findings", syn)  # no findings created yet


def test_build_section_succeeds_with_real_content():
    syn, ev = _synthesis_state()
    stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    section = build_section("key_findings", syn)
    assert section.content
    assert section.traced_ids
