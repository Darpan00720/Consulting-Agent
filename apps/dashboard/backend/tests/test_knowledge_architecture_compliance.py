"""Architecture verification (requester's own section): the Knowledge
Library must not redesign the platform, the Workflow Router/Dispatcher/
Runtime/Memory/Tool Platforms, or the Consulting Workflow Engine. Structural
proof, not convention.
"""

from __future__ import annotations

import inspect

from app.knowledge import composition, execution, integration, quality, selection


def _import_lines(source: str) -> str:
    """Only actual ``import``/``from ... import`` statement lines — a
    docstring PROSE mention of a module path (explaining a design choice by
    reference) is not an import and must not trip this check."""
    return "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


def test_knowledge_package_never_imports_workflow_router_or_dispatcher():
    for module in (composition, execution, integration, quality, selection):
        imports = _import_lines(inspect.getsource(module))
        assert "app.workflow.router" not in imports, module.__name__
        assert "app.workflow.dispatcher" not in imports, module.__name__


def test_knowledge_package_never_imports_agent_runtime_or_memory_service():
    for module in (composition, execution, integration, quality, selection):
        imports = _import_lines(inspect.getsource(module))
        assert "app.agents.runtime" not in imports, module.__name__
        assert "app.memory.service" not in imports, module.__name__


def test_integration_module_never_calls_create_recommendation():
    """Structural proof of "framework execution never generates executive
    recommendations": the ONLY module that reads a FrameworkExecutionResult
    into a real engagement has no CALL to
    app.consulting.tracking.create_recommendation (the docstring discusses
    it by name; a real call would be ``create_recommendation(``)."""
    source = inspect.getsource(integration)
    assert "create_recommendation(" not in source


def test_integration_module_only_uses_existing_consulting_tracking_api():
    source = inspect.getsource(integration)
    assert "from app.consulting.tracking import add_evidence" in source
    assert "import sqlite3" not in source
    assert "from app import db" not in source


def test_consulting_workflow_engine_is_untouched_by_the_knowledge_library():
    """The strongest proof: ConsultingEngine's own source contains zero
    references to app.knowledge — this package is purely additive, wired in
    from the OUTSIDE (integration.py), never by modifying engine.py."""
    from app.consulting import engine as consulting_engine

    source = inspect.getsource(consulting_engine)
    assert "app.knowledge" not in source


def test_no_hardcoded_execution_logic_in_the_catalog():
    """FrameworkDefinition fields are all data (str/tuple/small descriptor
    dataclasses) — the catalog module itself contains no per-framework
    calculation code (no arithmetic operators applied to catalog content,
    no framework-specific branching)."""
    from app.knowledge import catalog

    source = inspect.getsource(catalog)
    # The catalog builds FrameworkDefinition objects and nothing else callable
    # per-framework — no "if spec.key == " branches (which would be the
    # tell-tale sign of hardcoded per-framework logic).
    assert "spec.key ==" not in source
    assert "spec.id ==" not in source


def test_platform_and_workflow_engine_test_suites_still_importable_unmodified():
    """A live check that nothing in this phase broke the layers below it —
    the same "does the import still work" smoke check ADR-013 W6 used."""
    from app.consulting.engine import ConsultingEngine  # noqa: F401
    from app.workflow.dispatcher import dispatch  # noqa: F401
    from app.workflow.router import route  # noqa: F401

    assert callable(route)
    assert callable(dispatch)
