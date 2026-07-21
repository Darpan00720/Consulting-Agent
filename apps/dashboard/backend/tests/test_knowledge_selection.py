"""Tests for the deterministic framework selection engine."""

from __future__ import annotations

from app.consulting.models import EngagementCategory as EC
from app.knowledge.models import CompanySize, SelectionContext
from app.knowledge.registry import default_framework_registry
from app.knowledge.selection import select_frameworks


def test_selection_only_returns_frameworks_supporting_the_engagement_type():
    r = default_framework_registry()
    ctx = SelectionContext(engagement_type=EC.MARKET_ENTRY)
    result = select_frameworks(ctx, r, limit=20, alternatives_limit=0)
    for rec in result.recommended:
        fw = r.get(rec.framework_id)
        assert EC.MARKET_ENTRY in fw.supported_engagements


def test_recommendations_are_ranked_by_descending_priority():
    r = default_framework_registry()
    ctx = SelectionContext(engagement_type=EC.MARKET_ENTRY)
    result = select_frameworks(ctx, r)
    priorities = [rec.priority for rec in result.recommended]
    assert priorities == sorted(priorities)
    assert priorities[0] == 1


def test_every_recommendation_carries_reasoning():
    r = default_framework_registry()
    ctx = SelectionContext(engagement_type=EC.COST_REDUCTION)
    result = select_frameworks(ctx, r)
    for rec in result.recommended:
        assert len(rec.reasoning) > 0


def test_data_readiness_improves_score_and_confidence():
    r = default_framework_registry()
    ctx_no_data = SelectionContext(engagement_type=EC.MARKET_ENTRY, confidence=0.8)
    ctx_with_data = SelectionContext(
        engagement_type=EC.MARKET_ENTRY,
        available_data=("industry definition", "competitor list"),
        available_evidence=("industry reports", "competitor financials"),
        confidence=0.8,
    )
    result_no_data = select_frameworks(ctx_no_data, r, limit=20, alternatives_limit=0)
    result_with_data = select_frameworks(
        ctx_with_data, r, limit=20, alternatives_limit=0
    )
    ff_no_data = next(
        rec for rec in result_no_data.recommended if rec.framework_id == "five_forces"
    )
    ff_with_data = next(
        rec for rec in result_with_data.recommended if rec.framework_id == "five_forces"
    )
    assert ff_with_data.confidence > ff_no_data.confidence


def test_business_problem_keyword_match_affects_reasoning():
    r = default_framework_registry()
    ctx = SelectionContext(
        engagement_type=EC.PRICING_STRATEGY,
        business_problem="we need a pricing analysis",
    )
    result = select_frameworks(ctx, r, limit=20, alternatives_limit=0)
    pricing = next(
        x for x in result.recommended if x.framework_id == "pricing_analysis"
    )
    assert any("problem statement matches" in reason for reason in pricing.reasoning)


def test_alternatives_are_disjoint_from_recommended():
    r = default_framework_registry()
    ctx = SelectionContext(engagement_type=EC.MARKET_ENTRY)
    result = select_frameworks(ctx, r, limit=3, alternatives_limit=3)
    recommended_ids = {rec.framework_id for rec in result.recommended}
    alt_ids = {rec.framework_id for rec in result.alternatives}
    assert recommended_ids.isdisjoint(alt_ids)


def test_company_size_filter_respected_in_scoring():
    r = default_framework_registry()
    ctx = SelectionContext(
        engagement_type=EC.MARKET_ENTRY, company_size=CompanySize.STARTUP
    )
    result = select_frameworks(ctx, r, limit=20, alternatives_limit=0)
    for rec in result.recommended:
        assert any("company size" in reason for reason in rec.reasoning)
