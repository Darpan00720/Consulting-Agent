"""Tests for all 8 named consistency checks."""

from __future__ import annotations

import dataclasses

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.synthesis import tracking as stracking
from app.synthesis.consistency import validate_consistency
from app.synthesis.models import ConsistencyIssueType as CIT
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


def test_no_issues_on_a_clean_state():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    insight = stracking.create_insight(syn, "theme", (finding.id,), confidence=0.8)
    opp = stracking.create_opportunity(
        syn, "desc", (insight.id,), "high", "high", "med", "med", "low", confidence=0.8
    )
    stracking.create_recommendation(
        syn,
        "s",
        "r",
        (finding.id,),
        (ev.id,),
        supporting_opportunity_ids=(opp.id,),
        confidence=0.8,
    )
    issues = validate_consistency(syn)
    assert issues == ()


def test_unsupported_recommendation_detected_when_bypassing_tracking():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    rec = stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    broken = dataclasses.replace(rec, supporting_finding_ids=())
    syn.recommendations[rec.id] = broken
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.UNSUPPORTED_RECOMMENDATION for i in issues)


def test_duplicate_finding_detected_case_insensitively():
    syn, ev = _synthesis_state()
    stracking.create_finding(syn, "Market is large", (ev.id,), 0.8, "y")
    stracking.create_finding(syn, "market IS large", (ev.id,), 0.8, "y")
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.DUPLICATE_FINDING for i in issues)


def test_contradictory_recommendations_declared_via_contradicts_field():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    rec1 = stracking.create_recommendation(syn, "Do X", "r", (finding.id,), (ev.id,))
    stracking.create_recommendation(
        syn, "Do NOT X", "r", (finding.id,), (ev.id,), contradicts=(rec1.id,)
    )
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.CONTRADICTORY_RECOMMENDATIONS for i in issues)


def test_missing_evidence_detected_on_direct_object_manipulation():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    broken = dataclasses.replace(finding, supporting_evidence_ids=("ev-ghost",))
    syn.findings[finding.id] = broken
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.MISSING_EVIDENCE for i in issues)


def test_conflicting_assumptions_flagged_as_advisory():
    syn, ev = _synthesis_state()
    stracking.create_finding(
        syn, "x", (ev.id,), 0.8, "y", assumptions=("market keeps growing",)
    )
    stracking.create_finding(
        syn, "z", (ev.id,), 0.8, "y", assumptions=("market keeps growing",)
    )
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.CONFLICTING_ASSUMPTIONS for i in issues)


def test_orphan_insight_detected_when_never_referenced_upward():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_insight(syn, "orphaned theme", (finding.id,))
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.ORPHAN_INSIGHT for i in issues)


def test_circular_reasoning_detected_in_insight_dependencies():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    i1 = stracking.create_insight(syn, "theme1", (finding.id,))
    i2 = stracking.create_insight(syn, "theme2", (finding.id,), dependencies=(i1.id,))
    # manually inject a cycle: i1 now depends on i2 too (bypassing tracking's
    # own referential check, which only validates dependencies at CREATION time)
    broken_i1 = dataclasses.replace(i1, dependencies=(i2.id,))
    syn.insights[i1.id] = broken_i1
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.CIRCULAR_REASONING for i in issues)


def test_low_confidence_conclusion_detected():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_insight(syn, "theme", (finding.id,), confidence=0.1)
    issues = validate_consistency(syn)
    assert any(i.issue_type is CIT.LOW_CONFIDENCE_CONCLUSION for i in issues)
