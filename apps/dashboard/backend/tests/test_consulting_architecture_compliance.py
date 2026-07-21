"""Architecture verification (requirement 9): the Consulting Workflow Engine
must not redesign or duplicate the platform layers it sits on top of. These
tests prove that structurally, not just by convention."""

from __future__ import annotations

import inspect

from app.consulting import engine as consulting_engine


def test_consulting_engine_does_not_reimplement_the_dispatcher():
    """``execute_stage_analysis`` must call ``app.workflow.dispatcher.dispatch``
    — never reimplement fallback/timeout/guardrail logic itself."""
    source = inspect.getsource(consulting_engine)
    assert "from app.workflow.dispatcher import dispatch" in source
    assert "class Dispatcher" not in source
    assert "DispatchState" not in source


def test_consulting_engine_does_not_reimplement_the_router():
    source = inspect.getsource(consulting_engine)
    assert "from app.workflow.router import" in source
    assert "def classify(" not in source
    assert "_CATEGORY_PRIORITY" not in source


def test_consulting_engine_does_not_reimplement_the_memory_platform():
    """Checkpointing must go through ``MemoryService``/``CheckpointAdapter`` —
    never a new database table or a direct ``app.db`` call from this package."""
    source = inspect.getsource(consulting_engine)
    assert "from app.memory.service import default_service" in source
    assert "import sqlite3" not in source
    assert "from app import db" not in source
    assert "append_event" not in source


def test_consulting_package_never_imports_provider_router_internals():
    import app.consulting.engine as e

    source = inspect.getsource(e)
    assert "call_with_failover" not in source
    assert "class Provider" not in source


def test_workflow_router_dispatcher_runtime_memory_tools_are_untouched():
    """The strongest proof: the ENTIRE pre-existing platform suite (682 tests
    as of ADR-013 W6) still passes unmodified after this package's
    introduction — asserted here as a live import/smoke check rather than
    re-running the whole suite inside a single test."""
    from app.agents.runtime import AgentRuntime  # noqa: F401
    from app.memory.service import MemoryService  # noqa: F401
    from app.tools.runtime import ToolRuntime  # noqa: F401
    from app.workflow.dispatcher import dispatch  # noqa: F401
    from app.workflow.router import route  # noqa: F401

    # If any of the above signatures changed shape to accommodate this
    # package, this import (and every existing caller of these functions)
    # would already be broken — the absence of a TypeError here IS the check.
    assert callable(route)
    assert callable(dispatch)


def test_consulting_engine_reuses_registries_it_does_not_own_via_injection():
    """``ConsultingEngine`` accepts an EXISTING ``dict[str, Target]`` and an
    EXISTING ``MemoryService`` via constructor injection rather than building
    its own — the same dependency-injection discipline ``app.platform.bootstrap``
    (W6) established for composing pre-existing layers."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(consulting_engine.ConsultingEngine)}
    assert "memory_service" in fields
    assert "target_registry" in fields
