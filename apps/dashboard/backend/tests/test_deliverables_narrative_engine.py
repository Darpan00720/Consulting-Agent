"""Tests for the deliverables narrative engine (SCR construction)."""

from __future__ import annotations

import pytest

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.deliverables.errors import MissingTraceabilityError
from app.deliverables.narrative_engine import build_narrative_structure
from app.synthesis import tracking as stracking
from app.synthesis.narrative import build_strategic_narrative
from app.synthesis.state import SynthesisState


def _built_state():
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
    syn = SynthesisState(engagement_state=cstate)
    finding = stracking.create_finding(syn, "Market is large", (ev.id,), 0.8, "y")
    stracking.create_recommendation(
        syn,
        "Enter market",
        "rationale",
        (finding.id,),
        (ev.id,),
        expected_benefits=("new revenue",),
        risk="competitive response",
    )
    narrative = build_strategic_narrative(
        syn,
        "Client evaluating expansion",
        ("build vs buy",),
        ("growth",),
        ("exec risk",),
        "summary",
    )
    return syn, narrative


def test_narrative_structure_derives_every_field_from_real_content():
    syn, narrative = _built_state()
    structure = build_narrative_structure(syn, narrative.id)
    assert structure.situation == "Client evaluating expansion"
    assert "Market is large" in structure.complication
    assert "Enter market" in structure.resolution
    assert "new revenue" in structure.business_impact
    assert "competitive response" in structure.risks
    assert structure.source_narrative_id == narrative.id


def test_narrative_structure_rejects_unknown_narrative():
    syn, _n = _built_state()
    with pytest.raises(MissingTraceabilityError):
        build_narrative_structure(syn, "narr-ghost")
