"""Tests that the role catalog is complete and every entry is well-formed —
the requester's exhaustive named list, verified as data."""

from __future__ import annotations

from app.consulting.models import ArtifactType
from app.knowledge.registry import default_framework_registry
from app.organization.catalog import all_role_definitions

_EXPECTED_ROLES = {
    "managing_partner",
    "partner",
    "principal",
    "engagement_manager",
    "project_leader",
    "strategy_consultant",
    "industry_specialist",
    "financial_analyst",
    "operations_consultant",
    "digital_transformation_consultant",
    "ai_strategy_consultant",
    "technology_architect",
    "market_research_analyst",
    "competitive_intelligence_analyst",
    "customer_insights_analyst",
    "risk_consultant",
    "implementation_consultant",
    "pmo_consultant",
    "knowledge_manager",
    "research_librarian",
    "qa_reviewer",
    "executive_editor",
    "presentation_specialist",
    "data_analyst",
    "business_analyst",
}


def test_catalog_has_25_unique_roles_matching_the_requested_list():
    roles = all_role_definitions()
    ids = {r.id for r in roles}
    assert len(roles) == 25
    assert ids == _EXPECTED_ROLES


def test_every_role_has_every_required_field_populated():
    for r in all_role_definitions():
        assert r.id, r
        assert r.name, r
        assert r.description, r.id
        assert r.primary_responsibilities, r.id
        assert r.decision_authority, r.id
        assert r.required_capabilities, r.id
        assert r.quality_checklist, r.id
        assert r.handoff_criteria, r.id
        assert r.escalation_rules, r.id
        assert r.outputs_produced, r.id
        assert r.kpis, r.id
        assert r.review_authority, r.id
        assert r.owner


def test_exactly_one_role_is_the_top_of_the_firm():
    roles = all_role_definitions()
    tops = [r.id for r in roles if r.reporting_line is None]
    assert tops == ["managing_partner"]


def test_every_reporting_line_resolves_to_a_real_role():
    roles = all_role_definitions()
    ids = {r.id for r in roles}
    for r in roles:
        if r.reporting_line is not None:
            assert r.reporting_line in ids, r.id


def test_no_reporting_cycles_reaching_the_top():
    roles = {r.id: r for r in all_role_definitions()}
    for role_id, role in roles.items():
        seen = set()
        current = role
        while current.reporting_line is not None:
            assert current.id not in seen, f"cycle involving {role_id}"
            seen.add(current.id)
            current = roles[current.reporting_line]


def test_every_deliverable_type_is_owned_by_at_most_one_role_no_duplication():
    roles = all_role_definitions()
    owner_by_artifact: dict[ArtifactType, str] = {}
    for r in roles:
        for artifact in r.deliverables_owned:
            assert artifact not in owner_by_artifact, (
                f"{artifact} owned by both {owner_by_artifact.get(artifact)} and {r.id}"
            )
            owner_by_artifact[artifact] = r.id


def test_all_13_artifact_types_have_an_owning_role():
    roles = all_role_definitions()
    owned = {a for r in roles for a in r.deliverables_owned}
    assert owned == set(ArtifactType)


def test_supported_frameworks_cross_reference_real_knowledge_library_entries():
    kreg = default_framework_registry()
    all_fw_ids = {f.id for f in kreg.list()}
    for r in all_role_definitions():
        for fid in r.supported_frameworks:
            assert fid in all_fw_ids, (r.id, fid)


def test_every_practice_is_used_by_at_least_one_role():
    from app.organization.models import Practice

    roles = all_role_definitions()
    used = {r.practice for r in roles}
    assert used == set(Practice)
