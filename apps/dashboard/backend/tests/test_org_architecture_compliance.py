"""Architecture verification (requester's own section): the Organization
Layer must not redesign the platform, the Workflow Router/Dispatcher/
Runtime/Memory/Tool Platforms, the Consulting Workflow Engine, or the
Knowledge Library. Structural proof, not convention.
"""

from __future__ import annotations

import inspect

from app.organization import (
    allocation,
    collaboration,
    governance,
    integration,
    metrics,
    raci,
    review,
)


def _import_lines(source: str) -> str:
    return "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


def test_organization_package_never_imports_workflow_router_or_dispatcher():
    for module in (
        allocation,
        collaboration,
        governance,
        integration,
        metrics,
        raci,
        review,
    ):
        imports = _import_lines(inspect.getsource(module))
        assert "app.workflow.router" not in imports, module.__name__
        assert "app.workflow.dispatcher" not in imports, module.__name__


def test_organization_package_never_imports_agent_runtime_or_memory_service():
    for module in (
        allocation,
        collaboration,
        governance,
        integration,
        metrics,
        raci,
        review,
    ):
        imports = _import_lines(inspect.getsource(module))
        assert "app.agents.runtime" not in imports, module.__name__
        assert "app.memory.service" not in imports, module.__name__


def test_organization_package_never_imports_tool_runtime():
    for module in (
        allocation,
        collaboration,
        governance,
        integration,
        metrics,
        raci,
        review,
    ):
        imports = _import_lines(inspect.getsource(module))
        assert "app.tools.runtime" not in imports, module.__name__


def test_integration_module_only_calls_existing_knowledge_library_functions():
    source = inspect.getsource(integration)
    assert "from app.knowledge.execution import execute_framework" in source
    assert "from app.knowledge.integration import apply_framework_result" in source
    # Never reimplements framework execution or quality gating itself.
    assert "def execute_framework(" not in source
    assert "def evaluate_gates(" not in source


def test_integration_module_never_calls_create_recommendation():
    source = inspect.getsource(integration)
    assert "create_recommendation(" not in source


def test_consulting_engine_and_knowledge_library_are_untouched():
    """The strongest proof: neither ``ConsultingEngine``'s nor the Knowledge
    Library's own source contains any reference to app.organization — this
    package is purely additive, wired in from the OUTSIDE."""
    from app.consulting import engine as consulting_engine
    from app.knowledge import execution as knowledge_execution
    from app.knowledge import selection as knowledge_selection

    for module in (consulting_engine, knowledge_execution, knowledge_selection):
        source = inspect.getsource(module)
        assert "app.organization" not in source, module.__name__


def test_no_role_behavior_is_implemented_as_a_prompt_template():
    """ "Do not implement role behavior as prompt templates" — the catalog
    contains only data (strings/tuples/enums fed through ``_build()``), no
    LLM prompt-construction code."""
    from app.organization import catalog

    source = inspect.getsource(catalog)
    assert "system_prompt" not in source
    assert "call_with_failover" not in source
    assert "You are" not in source  # no persona/prompt text of any kind


def test_raci_activities_reuse_consultingstage_not_a_duplicate_taxonomy():
    source = inspect.getsource(raci)
    assert "from app.consulting.models import" in source
    assert "ConsultingStage" in source


def test_platform_and_prior_layers_still_importable_unmodified():
    """A live check nothing in this phase broke the layers below it."""
    from app.consulting.engine import ConsultingEngine  # noqa: F401
    from app.knowledge.registry import default_framework_registry  # noqa: F401
    from app.workflow.dispatcher import dispatch  # noqa: F401
    from app.workflow.router import route  # noqa: F401

    assert callable(route)
    assert callable(dispatch)
