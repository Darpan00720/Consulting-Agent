"""Tests for the deterministic work allocation engine."""

from __future__ import annotations

from app.consulting.models import ConsultingStage as CS
from app.consulting.models import EngagementCategory as EC
from app.organization.allocation import allocate_team
from app.organization.models import AllocationContext
from app.organization.registry import default_organization_registry


def test_delivery_leads_are_always_included():
    r = default_organization_registry()
    ctx = AllocationContext(
        engagement_type=EC.MARKET_ENTRY, workflow_stage=CS.PROBLEM_DEFINITION
    )
    result = allocate_team(ctx, r)
    ids = {a.role_id for a in result.recommended_team}
    assert "engagement_manager" in ids
    assert "project_leader" in ids


def test_framework_match_drives_role_selection():
    r = default_organization_registry()
    ctx = AllocationContext(
        engagement_type=EC.MARKET_ENTRY,
        workflow_stage=CS.ANALYSIS_EXECUTION,
        frameworks_selected=("dcf",),
    )
    result = allocate_team(ctx, r)
    financial_analyst = next(
        a for a in result.recommended_team if a.role_id == "financial_analyst"
    )
    assert any("dcf" in reason for reason in financial_analyst.reasoning)


def test_required_expertise_drives_role_selection():
    r = default_organization_registry()
    ctx = AllocationContext(
        engagement_type=EC.MARKET_ENTRY,
        workflow_stage=CS.ANALYSIS_EXECUTION,
        required_expertise=("financial modeling",),
    )
    result = allocate_team(ctx, r)
    financial_analyst = next(
        a for a in result.recommended_team if a.role_id == "financial_analyst"
    )
    assert any("financial modeling" in reason for reason in financial_analyst.reasoning)


def test_workload_shares_sum_to_approximately_one():
    r = default_organization_registry()
    ctx = AllocationContext(
        engagement_type=EC.MARKET_ENTRY, workflow_stage=CS.SYNTHESIS
    )
    result = allocate_team(ctx, r)
    total = sum(a.workload_share for a in result.recommended_team)
    assert abs(total - 1.0) < 1e-6


def test_no_candidates_gives_zero_confidence():
    from app.organization.registry import OrganizationRegistry

    empty_registry = OrganizationRegistry()
    ctx = AllocationContext(
        engagement_type=EC.MARKET_ENTRY, workflow_stage=CS.SYNTHESIS
    )
    result = allocate_team(ctx, empty_registry)
    assert result.confidence == 0.0
    assert result.recommended_team == ()


def test_practice_relevance_to_stage_affects_scoring():
    r = default_organization_registry()
    ctx = AllocationContext(
        engagement_type=EC.CHANGE_MANAGEMENT, workflow_stage=CS.EXECUTIVE_DELIVERABLE
    )
    result = allocate_team(ctx, r)
    ids = {a.role_id for a in result.recommended_team}
    assert (
        "executive_editor" in ids
        or "presentation_specialist" in ids
        or "qa_reviewer" in ids
    )
