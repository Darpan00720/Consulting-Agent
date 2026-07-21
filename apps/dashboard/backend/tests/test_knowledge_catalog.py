"""Tests that the framework catalog is complete and every entry is
well-formed — the requester's exhaustive named list, verified as data."""

from __future__ import annotations

from app.consulting.models import EngagementCategory
from app.knowledge.catalog import all_framework_definitions
from app.knowledge.models import FrameworkCategory

_EXPECTED_STRATEGY = {
    "five_forces",
    "value_chain",
    "vrio",
    "swot",
    "pestle",
    "bcg_matrix",
    "ge_mckinsey_matrix",
    "ansoff_matrix",
    "blue_ocean",
    "three_horizons",
    "core_competency",
    "capability_assessment",
    "strategic_positioning",
    "growth_share_analysis",
}
_EXPECTED_MARKET_GROWTH = {
    "tam_sam_som",
    "customer_segmentation",
    "market_attractiveness",
    "competitive_positioning",
    "customer_journey",
    "gtm_assessment",
    "pricing_analysis",
    "market_entry_assessment",
    "growth_diagnostic",
    "demand_forecasting",
}
_EXPECTED_OPERATIONS = {
    "lean",
    "six_sigma",
    "theory_of_constraints",
    "value_stream_mapping",
    "process_mapping",
    "capacity_analysis",
    "bottleneck_analysis",
    "operational_maturity",
    "supply_chain_assessment",
    "ops_operating_model_assessment",
}
_EXPECTED_FINANCE = {
    "dcf",
    "npv",
    "irr",
    "payback_period",
    "sensitivity_analysis",
    "scenario_analysis",
    "unit_economics",
    "breakeven_analysis",
    "cost_structure_analysis",
    "profitability_analysis",
    "financial_benchmarking",
}
_EXPECTED_PRODUCT = {
    "jobs_to_be_done",
    "product_discovery",
    "north_star_metrics",
    "product_lifecycle",
    "feature_prioritization",
    "customer_value_proposition",
    "product_portfolio_analysis",
    "product_market_fit",
    "adoption_funnel",
    "retention_analysis",
}
_EXPECTED_INNOVATION = {
    "design_thinking",
    "lean_startup",
    "business_model_canvas",
    "value_proposition_canvas",
    "innovation_portfolio",
    "experiment_design",
    "hypothesis_validation",
}
_EXPECTED_ORGANIZATION = {
    "mckinsey_7s",
    "raci",
    "stakeholder_analysis",
    "org_operating_model",
    "decision_rights",
    "organizational_design",
    "capability_mapping",
    "governance_assessment",
}
_EXPECTED_DIGITAL_AI = {
    "digital_maturity",
    "ai_readiness",
    "automation_assessment",
    "technology_capability_assessment",
    "platform_strategy",
    "cloud_readiness",
    "data_strategy",
    "technology_landscape",
    "architecture_assessment",
}
_EXPECTED_RISK = {
    "risk_matrix",
    "failure_mode_analysis",
    "scenario_planning",
    "business_continuity",
    "dependency_mapping",
    "risk_heatmap",
    "mitigation_planning",
}


def _ids_by_category(defs, category: FrameworkCategory) -> set[str]:
    return {d.id for d in defs if d.category is category}


def test_catalog_has_86_unique_frameworks():
    defs = all_framework_definitions()
    assert len(defs) == 86
    assert len({d.id for d in defs}) == 86


def test_every_requested_framework_is_present_by_category():
    defs = all_framework_definitions()
    assert _ids_by_category(defs, FrameworkCategory.STRATEGY) == _EXPECTED_STRATEGY
    assert (
        _ids_by_category(defs, FrameworkCategory.MARKET_GROWTH)
        == _EXPECTED_MARKET_GROWTH
    )
    assert _ids_by_category(defs, FrameworkCategory.OPERATIONS) == _EXPECTED_OPERATIONS
    assert _ids_by_category(defs, FrameworkCategory.FINANCE) == _EXPECTED_FINANCE
    assert _ids_by_category(defs, FrameworkCategory.PRODUCT) == _EXPECTED_PRODUCT
    assert _ids_by_category(defs, FrameworkCategory.INNOVATION) == _EXPECTED_INNOVATION
    assert (
        _ids_by_category(defs, FrameworkCategory.ORGANIZATION) == _EXPECTED_ORGANIZATION
    )
    assert _ids_by_category(defs, FrameworkCategory.DIGITAL_AI) == _EXPECTED_DIGITAL_AI
    assert _ids_by_category(defs, FrameworkCategory.RISK) == _EXPECTED_RISK


def test_scenario_planning_is_registered_once_tagged_for_both_homes():
    """Requester listed "Scenario Planning" under both Strategy and Risk
    verbatim — registered once (Risk), tagged so strategy search still finds
    it. See catalog.py's module docstring for the explicit rationale."""
    defs = all_framework_definitions()
    matches = [d for d in defs if d.name == "Scenario Planning"]
    assert len(matches) == 1
    assert matches[0].category is FrameworkCategory.RISK
    assert "strategy" in matches[0].tags


def test_every_framework_has_every_required_field_populated():
    for d in all_framework_definitions():
        assert d.id, d
        assert d.name, d
        assert d.version, d
        assert d.description, d
        assert d.purpose, d
        assert d.when_to_use, d.id
        assert d.when_not_to_use, d.id
        assert d.required_inputs, d.id
        assert d.output_schema.fields, d.id
        assert d.supported_engagements, d.id
        assert all(isinstance(e, EngagementCategory) for e in d.supported_engagements)
        assert d.owner
        assert d.estimated_duration_days > 0


def test_every_framework_has_at_least_the_inputs_quality_gate():
    for d in all_framework_definitions():
        assert any(
            g.check_kind == "required_inputs_present" for g in d.quality_gates
        ), d.id


def test_no_framework_declares_a_dependency_on_itself():
    for d in all_framework_definitions():
        assert d.id not in d.dependencies


def test_every_declared_dependency_resolves_to_a_real_catalog_entry():
    all_ids = {d.id for d in all_framework_definitions()}
    for d in all_framework_definitions():
        for dep in d.dependencies:
            assert dep in all_ids, (d.id, dep)


def test_market_entry_worked_example_frameworks_are_registered():
    """The requester's own Market Entry composition example."""
    all_ids = {d.id for d in all_framework_definitions()}
    for fid in ("pestle", "five_forces", "tam_sam_som", "swot", "dcf", "risk_matrix"):
        assert fid in all_ids
