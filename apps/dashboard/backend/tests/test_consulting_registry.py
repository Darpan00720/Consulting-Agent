"""Tests for ``WorkflowRegistry`` — registration, versioning, extensibility
("support future engagement types without redesign")."""

from __future__ import annotations

import pytest

from app.consulting.errors import DuplicateWorkflowError, UnknownWorkflowError
from app.consulting.models import EngagementCategory
from app.consulting.quality_gates import standard_gates
from app.consulting.registry import WorkflowRegistry, default_workflow_registry
from app.consulting.workflow import standard_workflow


def test_default_registry_has_a_workflow_for_every_requested_category():
    registry = default_workflow_registry()
    for category in EngagementCategory:
        wf = registry.get(f"workflow.{category.value}")
        assert wf.category is category
        assert len(wf.required_stages) == 10
        assert len(wf.quality_gates) == 10


def test_duplicate_registration_raises():
    registry = WorkflowRegistry()
    gates = standard_gates()
    wf = standard_workflow(EngagementCategory.PRICING_STRATEGY, quality_gates=gates)
    registry.register(wf)
    with pytest.raises(DuplicateWorkflowError):
        registry.register(wf)


def test_unknown_workflow_raises():
    registry = WorkflowRegistry()
    with pytest.raises(UnknownWorkflowError):
        registry.get("workflow.does_not_exist")


def test_versioning_get_without_version_returns_latest():
    registry = WorkflowRegistry()
    gates = standard_gates()
    v1 = standard_workflow(
        EngagementCategory.DUE_DILIGENCE, quality_gates=gates, version="1.0.0"
    )
    v2 = standard_workflow(
        EngagementCategory.DUE_DILIGENCE, quality_gates=gates, version="1.1.0"
    )
    registry.register(v1)
    registry.register(v2)
    assert registry.get(v1.id).version == "1.1.0"
    assert registry.get(v1.id, "1.0.0").version == "1.0.0"
    assert set(registry.versions_of(v1.id)) == {"1.0.0", "1.1.0"}


def test_find_by_category():
    registry = default_workflow_registry()
    found = registry.find_by_category(EngagementCategory.SUPPLY_CHAIN)
    assert len(found) == 1
    assert found[0].category is EngagementCategory.SUPPLY_CHAIN


def test_a_future_engagement_category_registers_without_touching_this_module():
    """The concrete "extensibility" proof: a hypothetical 29th category is a
    single ``standard_workflow`` call plus one registration — no new class,
    no change to the registry's own code. We simulate this with an existing
    enum member registered under a custom workflow id, proving the mechanism
    itself is generic (id is caller-chosen, not hardcoded)."""
    registry = WorkflowRegistry()
    gates = standard_gates()
    custom = standard_workflow(
        EngagementCategory.VENTURE_VALIDATION, quality_gates=gates
    )
    import dataclasses

    custom = dataclasses.replace(custom, id="workflow.custom_future_category")
    registry.register(custom)
    fetched = registry.get("workflow.custom_future_category")
    assert fetched.category is EngagementCategory.VENTURE_VALIDATION
    assert len(fetched.required_stages) == 10
