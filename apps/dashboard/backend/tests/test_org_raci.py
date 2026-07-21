"""Tests for the RACI model and conflict detection."""

from __future__ import annotations

from app.organization.models import RACIAssignment, RACIMatrix, RACIRole
from app.organization.raci import build_default_raci_matrix, detect_conflicts
from app.organization.registry import default_organization_registry


def test_default_matrix_has_zero_conflicts():
    r = default_organization_registry()
    matrix = build_default_raci_matrix(r)
    conflicts = detect_conflicts(matrix)
    assert conflicts == ()


def test_every_activity_has_exactly_one_accountable_owner():
    r = default_organization_registry()
    matrix = build_default_raci_matrix(r)
    activities = {a.activity for a in matrix.assignments}
    for activity in activities:
        accountable = [
            a for a in matrix.for_activity(activity) if a.raci is RACIRole.ACCOUNTABLE
        ]
        assert len(accountable) == 1, activity


def test_lifecycle_stage_activities_are_all_present():
    r = default_organization_registry()
    matrix = build_default_raci_matrix(r)
    activities = {a.activity for a in matrix.assignments}
    for stage in (
        "problem_definition",
        "hypothesis_development",
        "issue_tree_construction",
        "analysis_planning",
        "evidence_collection",
        "analysis_execution",
        "synthesis",
        "recommendations",
        "implementation_roadmap",
        "executive_deliverable",
    ):
        assert stage in activities


def test_decision_activities_are_all_present():
    r = default_organization_registry()
    matrix = build_default_raci_matrix(r)
    activities = {a.activity for a in matrix.assignments}
    for decision in (
        "approve_hypotheses",
        "approve_assumptions",
        "approve_findings",
        "approve_recommendations",
        "approve_implementation_plans",
        "approve_executive_summaries",
    ):
        assert decision in activities


def test_detect_conflicts_flags_multiple_accountable_owners():
    matrix = RACIMatrix(
        assignments=[
            RACIAssignment("some_activity", "role_a", RACIRole.ACCOUNTABLE),
            RACIAssignment("some_activity", "role_b", RACIRole.ACCOUNTABLE),
        ]
    )
    conflicts = detect_conflicts(matrix)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "multiple accountable owners"
    assert set(conflicts[0].role_ids) == {"role_a", "role_b"}


def test_detect_conflicts_flags_missing_accountable_owner():
    matrix = RACIMatrix(
        assignments=[RACIAssignment("some_activity", "role_a", RACIRole.RESPONSIBLE)]
    )
    conflicts = detect_conflicts(matrix)
    assert len(conflicts) == 1
    assert conflicts[0].reason == "no accountable owner"


def test_problem_definition_is_owned_by_engagement_manager():
    r = default_organization_registry()
    matrix = build_default_raci_matrix(r)
    accountable = [
        a
        for a in matrix.for_activity("problem_definition")
        if a.raci is RACIRole.ACCOUNTABLE
    ]
    assert accountable[0].role_id == "engagement_manager"
