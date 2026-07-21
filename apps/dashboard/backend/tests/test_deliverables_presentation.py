"""Tests for the 9 named visual spec builders — all reference existing
data only."""

from __future__ import annotations

import pytest

from app.deliverables.errors import MissingTraceabilityError
from app.deliverables.models import VisualType
from app.deliverables.presentation import (
    build_chart_from_business_impact,
    build_decision_tree,
    build_implementation_wave,
    build_matrix_from_trade_off,
    build_risk_heatmap,
    build_roadmap,
    build_table_from_findings,
    build_timeline,
)
from app.synthesis.business_impact import assess_business_impact
from app.synthesis.models import (
    ApprovalStatus,
    BusinessImpactDimension,
    BusinessImpactEstimate,
    Finding,
    FindingStatus,
    ImplementationTheme,
    Recommendation,
    TradeOffOption,
)
from app.synthesis.root_cause import five_whys
from app.synthesis.tradeoff import compare_options


def test_chart_from_business_impact_references_real_assessment():
    assessment = assess_business_impact(
        "rec-1",
        (
            BusinessImpactEstimate(
                dimension=BusinessImpactDimension.REVENUE,
                estimate="+$2M",
                confidence=0.8,
                estimated_value=2_000_000.0,
            ),
        ),
    )
    spec = build_chart_from_business_impact(assessment)
    assert spec.visual_type is VisualType.CHART
    assert spec.data_refs == (assessment.id,)
    assert spec.data["values"] == [2_000_000.0]


def test_table_from_findings_references_real_finding_ids():
    finding = Finding(
        id="find-1",
        statement="x",
        supporting_evidence_ids=("ev-1",),
        confidence=0.8,
        business_impact="y",
        status=FindingStatus.DRAFT,
    )
    spec = build_table_from_findings((finding,))
    assert spec.visual_type is VisualType.TABLE
    assert spec.data_refs == ("find-1",)
    assert spec.data["rows"][0][0] == "x"


def test_roadmap_and_timeline_reference_real_theme_ids():
    theme = ImplementationTheme(
        id="theme-1",
        name="Phase 1",
        description="d",
        supporting_recommendation_ids=("srec-1",),
        timeline="Q1",
    )
    roadmap = build_roadmap((theme,))
    timeline = build_timeline((theme,))
    assert roadmap.data_refs == ("theme-1",)
    assert timeline.data_refs == ("theme-1",)


def test_matrix_from_trade_off_references_real_option_ids():
    options = (
        TradeOffOption(id="a", name="A", dimension_scores={"financial": 9}),
        TradeOffOption(id="b", name="B", dimension_scores={"financial": 3}),
    )
    result = compare_options(options, dimension_weights={"financial": 1.0})
    spec = build_matrix_from_trade_off(result)
    assert set(spec.data_refs) == {"a", "b"}
    assert spec.data["ranked_option_ids"] == ["a", "b"]


def test_decision_tree_reuses_root_cause_analysis_nodes_directly():
    rca = five_whys("Churn", (("Churn", "Support slow", "Understaffed"),))
    spec = build_decision_tree(rca)
    assert spec.data_refs == (rca.id,)
    assert len(spec.data["nodes"]) == len(rca.nodes)


def test_risk_heatmap_rejects_scores_for_unknown_recommendations():
    rec = Recommendation(
        id="srec-1",
        statement="s",
        business_rationale="r",
        supporting_opportunity_ids=(),
        supporting_insight_ids=(),
        supporting_finding_ids=("find-1",),
        supporting_evidence_ids=("ev-1",),
        risk="competitive response",
        approval_status=ApprovalStatus.PENDING,
    )
    with pytest.raises(MissingTraceabilityError):
        build_risk_heatmap((rec,), {"srec-ghost": (0.5, 0.5)})


def test_risk_heatmap_accepts_real_recommendation_ids():
    rec = Recommendation(
        id="srec-1",
        statement="s",
        business_rationale="r",
        supporting_opportunity_ids=(),
        supporting_insight_ids=(),
        supporting_finding_ids=("find-1",),
        supporting_evidence_ids=("ev-1",),
        risk="competitive response",
        approval_status=ApprovalStatus.PENDING,
    )
    spec = build_risk_heatmap((rec,), {"srec-1": (0.6, 0.8)})
    assert spec.data["entries"][0]["likelihood"] == 0.6


def test_implementation_wave_groups_by_real_timeline_values():
    themes = (
        ImplementationTheme(
            id="t1",
            name="P1",
            description="d",
            supporting_recommendation_ids=("r1",),
            timeline="Q1",
        ),
        ImplementationTheme(
            id="t2",
            name="P2",
            description="d",
            supporting_recommendation_ids=("r1",),
            timeline="Q2",
        ),
    )
    spec = build_implementation_wave(themes)
    assert set(spec.data["waves"].keys()) == {"Q1", "Q2"}
