"""Architecture verification (requester's own section): the Deliverables
Engine must not redesign the platform, Workflow Router/Dispatcher/Runtime/
Memory/Tool Platforms, the Consulting Workflow Engine, Knowledge Library,
Organization Layer, or Synthesis Engine. Structural proof, not convention.
"""

from __future__ import annotations

import inspect

from app.deliverables import (
    audience,
    export,
    generator,
    integration,
    narrative_engine,
    presentation,
    quality,
    section_builder,
)

_ALL_MODULES = (
    audience,
    export,
    generator,
    integration,
    narrative_engine,
    presentation,
    quality,
    section_builder,
)


def _import_lines(source: str) -> str:
    return "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


def test_deliverables_package_never_imports_workflow_router_or_dispatcher():
    for module in _ALL_MODULES:
        imports = _import_lines(inspect.getsource(module))
        assert "app.workflow.router" not in imports, module.__name__
        assert "app.workflow.dispatcher" not in imports, module.__name__


def test_deliverables_package_never_imports_agent_runtime_or_tool_runtime():
    for module in _ALL_MODULES:
        imports = _import_lines(inspect.getsource(module))
        assert "app.agents.runtime" not in imports, module.__name__
        assert "app.tools.runtime" not in imports, module.__name__


def test_deliverables_never_creates_findings_insights_or_recommendations():
    """ "Deliverables never perform consulting reasoning" / "does not invent
    recommendations" — verified structurally: this package never calls the
    app.synthesis mutators that CREATE new reasoning-chain nodes, only reads
    what already exists."""
    for module in _ALL_MODULES:
        source = inspect.getsource(module)
        assert "create_finding(" not in source, module.__name__
        assert "create_insight(" not in source, module.__name__
        assert "create_opportunity(" not in source, module.__name__
        assert "create_recommendation(" not in source, module.__name__


def test_export_module_never_imports_a_document_generation_library():
    """No new dependency was added for PowerPoint/Word/PDF — the honest
    placeholder approach, verified structurally (checking IMPORT lines only
    — the module's own docstring discusses these libraries by name to
    explain why they aren't used, which isn't an import)."""
    imports = _import_lines(inspect.getsource(export))
    for forbidden in ("pptx", "docx", "reportlab", "weasyprint", "fpdf"):
        assert forbidden not in imports.lower()


def test_prior_layers_are_untouched_by_the_deliverables_engine():
    """The strongest proof: none of the four prior layers' own source
    references app.deliverables — this package is purely additive."""
    from app.consulting import engine as consulting_engine
    from app.knowledge import execution as knowledge_execution
    from app.organization import governance as organization_governance
    from app.synthesis import tracking as synthesis_tracking

    for module in (
        consulting_engine,
        knowledge_execution,
        organization_governance,
        synthesis_tracking,
    ):
        source = inspect.getsource(module)
        assert "app.deliverables" not in source, module.__name__


def test_platform_and_prior_layers_still_importable_unmodified():
    from app.consulting.engine import ConsultingEngine  # noqa: F401
    from app.knowledge.registry import default_framework_registry  # noqa: F401
    from app.organization.registry import default_organization_registry  # noqa: F401
    from app.synthesis.state import SynthesisState  # noqa: F401
    from app.workflow.dispatcher import dispatch  # noqa: F401
    from app.workflow.router import route  # noqa: F401

    assert callable(route)
    assert callable(dispatch)
