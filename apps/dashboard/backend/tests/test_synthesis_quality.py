"""Tests for the 8-dimension quality model."""

from __future__ import annotations

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.synthesis import tracking as stracking
from app.synthesis.models import QualityDimension
from app.synthesis.quality import assess_quality
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


def test_empty_state_reports_content_dependent_dimensions_failing():
    """An empty synthesis state has nothing to be INCONSISTENT about, so
    logical_consistency passes vacuously (zero blocking issues) — the other
    7 dimensions all require real content (recommendations, evidence
    references, confidence values) and correctly fail on empty state."""
    syn, _ev = _synthesis_state()
    report = assess_quality(syn)
    assert len(report.checks) == 8
    by_dim = {c.dimension: c for c in report.checks}
    assert by_dim[QualityDimension.LOGICAL_CONSISTENCY].passed
    other_dims = [
        c
        for c in report.checks
        if c.dimension is not QualityDimension.LOGICAL_CONSISTENCY
    ]
    assert all(not c.passed for c in other_dims)


def test_fully_built_recommendation_passes_traceability_and_completeness():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.9, "y")
    stracking.create_recommendation(
        syn,
        "s",
        "r",
        (finding.id,),
        (ev.id,),
        kpis=("ARR",),
        cost="$1M",
        risk="medium",
        trade_offs=("slower payback",),
        expected_benefits=("new revenue",),
        confidence=0.9,
    )
    report = assess_quality(syn)
    by_dim = {c.dimension: c for c in report.checks}
    assert by_dim[QualityDimension.TRACEABILITY].passed
    assert by_dim[QualityDimension.RECOMMENDATION_COMPLETENESS].passed
    assert by_dim[QualityDimension.EVIDENCE_COVERAGE].passed
    assert by_dim[QualityDimension.CONFIDENCE].passed


def test_trade_off_and_business_impact_and_feasibility_reflect_real_state():
    from app.synthesis.business_impact import assess_business_impact
    from app.synthesis.models import (
        BusinessImpactDimension,
        BusinessImpactEstimate,
        TradeOffOption,
    )
    from app.synthesis.tradeoff import compare_options

    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.9, "y")
    rec = stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))

    report_before = assess_quality(syn)
    by_dim_before = {c.dimension: c for c in report_before.checks}
    assert not by_dim_before[QualityDimension.TRADE_OFF_ANALYSIS].passed
    assert not by_dim_before[QualityDimension.BUSINESS_IMPACT].passed
    assert not by_dim_before[QualityDimension.IMPLEMENTATION_FEASIBILITY].passed

    syn.trade_off_results.append(
        compare_options(
            (
                TradeOffOption(
                    id="opt1", name="Option 1", dimension_scores={"financial": 5}
                ),
            )
        )
    )
    syn.business_impact_assessments["bia-1"] = assess_business_impact(
        rec.id,
        (
            BusinessImpactEstimate(
                dimension=BusinessImpactDimension.REVENUE, estimate="x", confidence=0.5
            ),
        ),
    )
    stracking.create_implementation_theme(syn, "Theme", "desc", (rec.id,))

    report_after = assess_quality(syn)
    by_dim_after = {c.dimension: c for c in report_after.checks}
    assert by_dim_after[QualityDimension.TRADE_OFF_ANALYSIS].passed
    assert by_dim_after[QualityDimension.BUSINESS_IMPACT].passed
    assert by_dim_after[QualityDimension.IMPLEMENTATION_FEASIBILITY].passed


def test_overall_score_is_average_of_all_8_checks():
    syn, ev = _synthesis_state()
    report = assess_quality(syn)
    manual_avg = sum(c.score for c in report.checks) / len(report.checks)
    assert abs(report.overall_score - manual_avg) < 1e-9
