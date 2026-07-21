"""Tests for the strategic narrative builder."""

from __future__ import annotations

import pytest

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.synthesis import tracking as stracking
from app.synthesis.errors import UnknownFindingError, UnknownRecommendationError
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
    rec = stracking.create_recommendation(
        syn, "Enter market", "rationale", (finding.id,), (ev.id,)
    )
    return syn, finding, rec


def test_narrative_defaults_to_referencing_everything_in_state():
    syn, finding, rec = _built_state()
    narrative = build_strategic_narrative(
        syn,
        "Current situation text",
        ("Choice A",),
        ("Grow revenue",),
        ("Execution risk",),
        "Exec summary",
    )
    assert narrative.key_finding_ids == (finding.id,)
    assert narrative.recommendation_ids == (rec.id,)
    assert narrative.id in syn.narratives


def test_narrative_can_curate_a_subset():
    syn, finding, rec = _built_state()
    narrative = build_strategic_narrative(
        syn,
        "sit",
        (),
        (),
        (),
        "summary",
        key_finding_ids=(),
        recommendation_ids=(rec.id,),
    )
    assert narrative.key_finding_ids == ()
    assert narrative.recommendation_ids == (rec.id,)


def test_narrative_rejects_unknown_finding_id():
    syn, _f, _r = _built_state()
    with pytest.raises(UnknownFindingError):
        build_strategic_narrative(
            syn, "sit", (), (), (), "summary", key_finding_ids=("find-ghost",)
        )


def test_narrative_rejects_unknown_recommendation_id():
    syn, _f, _r = _built_state()
    with pytest.raises(UnknownRecommendationError):
        build_strategic_narrative(
            syn, "sit", (), (), (), "summary", recommendation_ids=("srec-ghost",)
        )
