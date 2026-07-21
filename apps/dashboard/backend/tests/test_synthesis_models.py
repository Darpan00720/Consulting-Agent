"""Tests for the core Synthesis Engine data model."""

from __future__ import annotations

from app.synthesis.models import (
    TRADE_OFF_DIMENSIONS,
    ApprovalStatus,
    BusinessImpactDimension,
    ConsistencyIssueType,
    FindingStatus,
    PrioritizationMethod,
    QualityDimension,
    RootCauseMethod,
    TimeHorizon,
    new_finding_id,
    new_insight_id,
    new_opportunity_id,
    new_recommendation_id,
)


def test_trade_off_dimensions_has_all_8_named_dimensions():
    assert len(TRADE_OFF_DIMENSIONS) == 8
    assert set(TRADE_OFF_DIMENSIONS) == {
        "financial",
        "operational",
        "customer",
        "technology",
        "risk",
        "implementation",
        "organizational",
        "strategic_alignment",
    }


def test_root_cause_method_has_all_4_named_methods():
    assert len(list(RootCauseMethod)) == 4


def test_prioritization_method_has_all_6_named_methods():
    assert len(list(PrioritizationMethod)) == 6


def test_business_impact_dimension_has_all_8_named_dimensions():
    assert len(list(BusinessImpactDimension)) == 8


def test_consistency_issue_type_has_all_8_named_checks():
    assert len(list(ConsistencyIssueType)) == 8


def test_quality_dimension_has_all_8_named_dimensions():
    assert len(list(QualityDimension)) == 8


def test_finding_status_and_approval_status_and_time_horizon_enums():
    assert len(list(FindingStatus)) == 4
    assert len(list(ApprovalStatus)) == 4
    assert len(list(TimeHorizon)) == 3


def test_id_generators_produce_unique_prefixed_ids():
    assert new_finding_id().startswith("find-")
    assert new_insight_id().startswith("ins-")
    assert new_opportunity_id().startswith("opp-")
    assert new_recommendation_id().startswith("srec-")
    ids = {new_finding_id() for _ in range(20)}
    assert len(ids) == 20
