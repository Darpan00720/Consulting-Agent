"""Tests for the synthesis-chain mutators — the mandatory downward
traceability the requester's "Design Principles" section states as an
absolute."""

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
from app.synthesis.errors import (
    MissingTraceabilityError,
    UnknownEvidenceError,
    UnknownFindingError,
    UnknownInsightError,
    UnknownOpportunityError,
    UnknownRecommendationError,
)
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


def test_create_finding_requires_evidence():
    syn, _ev = _synthesis_state()
    with pytest.raises(MissingTraceabilityError):
        stracking.create_finding(syn, "x", (), 0.5, "impact")


def test_create_finding_rejects_unknown_evidence():
    syn, _ev = _synthesis_state()
    with pytest.raises(UnknownEvidenceError):
        stracking.create_finding(syn, "x", ("ev-ghost",), 0.5, "impact")


def test_create_finding_succeeds_with_real_evidence():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "Market is large", (ev.id,), 0.8, "big")
    assert finding.id in syn.findings


def test_create_insight_requires_findings():
    syn, _ev = _synthesis_state()
    with pytest.raises(MissingTraceabilityError):
        stracking.create_insight(syn, "theme", ())


def test_create_insight_rejects_unknown_finding():
    syn, _ev = _synthesis_state()
    with pytest.raises(UnknownFindingError):
        stracking.create_insight(syn, "theme", ("find-ghost",))


def test_create_opportunity_requires_insights():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_insight(syn, "theme", (finding.id,))
    with pytest.raises(MissingTraceabilityError):
        stracking.create_opportunity(
            syn, "desc", (), "high", "high", "med", "med", "low"
        )


def test_create_opportunity_rejects_unknown_insight():
    syn, _ev = _synthesis_state()
    with pytest.raises(UnknownInsightError):
        stracking.create_opportunity(
            syn, "desc", ("ins-ghost",), "high", "high", "med", "med", "low"
        )


def test_create_recommendation_requires_findings_and_evidence():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    with pytest.raises(MissingTraceabilityError):
        stracking.create_recommendation(syn, "stmt", "rationale", (), (ev.id,))
    with pytest.raises(MissingTraceabilityError):
        stracking.create_recommendation(syn, "stmt", "rationale", (finding.id,), ())


def test_create_recommendation_rejects_unknown_opportunity_and_insight():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    with pytest.raises(UnknownOpportunityError):
        stracking.create_recommendation(
            syn,
            "s",
            "r",
            (finding.id,),
            (ev.id,),
            supporting_opportunity_ids=("opp-ghost",),
        )
    with pytest.raises(UnknownInsightError):
        stracking.create_recommendation(
            syn,
            "s",
            "r",
            (finding.id,),
            (ev.id,),
            supporting_insight_ids=("ins-ghost",),
        )


def test_create_recommendation_succeeds_with_full_chain():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    insight = stracking.create_insight(syn, "theme", (finding.id,))
    opp = stracking.create_opportunity(
        syn, "desc", (insight.id,), "high", "high", "med", "med", "low"
    )
    rec = stracking.create_recommendation(
        syn,
        "stmt",
        "rationale",
        (finding.id,),
        (ev.id,),
        supporting_opportunity_ids=(opp.id,),
        supporting_insight_ids=(insight.id,),
    )
    assert rec.id in syn.recommendations


def test_create_implementation_theme_requires_recommendations():
    syn, _ev = _synthesis_state()
    with pytest.raises(MissingTraceabilityError):
        stracking.create_implementation_theme(syn, "name", "desc", ())


def test_create_implementation_theme_rejects_unknown_recommendation():
    syn, _ev = _synthesis_state()
    with pytest.raises(UnknownRecommendationError):
        stracking.create_implementation_theme(syn, "name", "desc", ("srec-ghost",))


def test_create_implementation_theme_succeeds():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    rec = stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    theme = stracking.create_implementation_theme(syn, "Theme", "desc", (rec.id,))
    assert theme.id in syn.implementation_themes
