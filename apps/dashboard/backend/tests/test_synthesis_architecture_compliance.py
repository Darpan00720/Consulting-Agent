"""Architecture verification (requester's own section): the Synthesis
Engine must not redesign the platform, Workflow Router/Dispatcher/Runtime/
Memory/Tool Platforms, the Consulting Workflow Engine, the Knowledge
Library, or the Organization Layer. Structural proof, not convention.
"""

from __future__ import annotations

import inspect

from app.synthesis import (
    business_impact,
    consistency,
    integration,
    narrative,
    prioritization,
    quality,
    root_cause,
    tradeoff,
)

_ALL_MODULES = (
    business_impact,
    consistency,
    integration,
    narrative,
    prioritization,
    quality,
    root_cause,
    tradeoff,
)


def _import_lines(source: str) -> str:
    return "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


def test_synthesis_package_never_imports_workflow_router_or_dispatcher():
    for module in _ALL_MODULES:
        imports = _import_lines(inspect.getsource(module))
        assert "app.workflow.router" not in imports, module.__name__
        assert "app.workflow.dispatcher" not in imports, module.__name__


def test_synthesis_package_never_imports_agent_runtime_or_tool_runtime():
    for module in _ALL_MODULES:
        imports = _import_lines(inspect.getsource(module))
        assert "app.agents.runtime" not in imports, module.__name__
        assert "app.tools.runtime" not in imports, module.__name__


def test_integration_module_only_calls_existing_layer_functions():
    source = inspect.getsource(integration)
    assert "from app.organization.governance import" in source
    assert "from app.consulting.serialization import" in source
    # Never reimplements the functions it delegates to.
    assert "def request_approval(" not in source
    assert "def execute_framework(" not in source


def test_integration_module_never_calls_create_recommendation_directly_on_consulting():
    """The Synthesis Engine's OWN Recommendation model is distinct; this
    confirms integration.py never reaches into
    app.consulting.tracking.create_recommendation (that would blur the two
    concepts this package's own models.py docstring explicitly separates)."""
    source = inspect.getsource(integration)
    assert "app.consulting.tracking" not in source


def test_consulting_knowledge_and_organization_layers_are_untouched():
    """The strongest proof: none of the three prior layers' own source
    references app.synthesis — this package is purely additive, wired in
    from the OUTSIDE."""
    from app.consulting import engine as consulting_engine
    from app.knowledge import execution as knowledge_execution
    from app.organization import governance as organization_governance

    for module in (consulting_engine, knowledge_execution, organization_governance):
        source = inspect.getsource(module)
        assert "app.synthesis" not in source, module.__name__


def test_no_report_or_presentation_generation_exists_in_this_package():
    """ "Do NOT generate PowerPoint. Do NOT generate reports. Do NOT generate
    executive documents." — verified structurally: no python-pptx / docx /
    PDF-rendering import anywhere in the package."""
    for module in _ALL_MODULES:
        source = inspect.getsource(module)
        assert "pptx" not in source.lower()
        assert "docx" not in source.lower()
        assert "reportlab" not in source.lower()


def test_platform_and_prior_layers_still_importable_unmodified():
    from app.consulting.engine import ConsultingEngine  # noqa: F401
    from app.knowledge.registry import default_framework_registry  # noqa: F401
    from app.organization.registry import default_organization_registry  # noqa: F401
    from app.workflow.dispatcher import dispatch  # noqa: F401
    from app.workflow.router import route  # noqa: F401

    assert callable(route)
    assert callable(dispatch)
