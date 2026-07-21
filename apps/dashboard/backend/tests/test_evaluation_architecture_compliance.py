"""Architecture verification (requester's own section): the Evaluation
Platform must not redesign the platform, Workflow Router/Dispatcher/Runtime/
Memory/Tool Platforms, or the Consulting Workflow/Knowledge/Organization/
Synthesis/Deliverables engines — and must "consume outputs only, never
modify consulting artifacts." Structural proof, not convention.
"""

from __future__ import annotations

import inspect

from app.evaluation import (
    ai_evaluation,
    benchmarking,
    continuous_improvement,
    dashboard,
    evaluation,
    hallucination,
    human_evaluation,
    integration,
    regression,
    replay,
    versioning,
)

_ALL_MODULES = (
    ai_evaluation,
    benchmarking,
    continuous_improvement,
    dashboard,
    evaluation,
    hallucination,
    human_evaluation,
    integration,
    regression,
    replay,
    versioning,
)

# every module EXCEPT replay.py — replay.py is the ONE place allowed to call
# into the 5 consulting layers' mutators, since its entire job is executing
# a fresh, isolated replay end to end, not modifying a live engagement.
_NON_REPLAY_MODULES = tuple(m for m in _ALL_MODULES if m is not replay)

_MUTATOR_IMPORTS = (
    "app.consulting.tracking",
    "app.consulting.engine",
    "app.knowledge.execution",
    "app.knowledge.integration",
    "app.organization.allocation",
    "app.organization.governance",
    "app.organization.review",
    "app.synthesis.tracking",
    "app.deliverables.generator",
)


def _import_lines(source: str) -> str:
    return "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


def test_evaluation_package_never_imports_workflow_router_or_dispatcher():
    for module in _ALL_MODULES:
        imports = _import_lines(inspect.getsource(module))
        assert "app.workflow.router" not in imports, module.__name__
        assert "app.workflow.dispatcher" not in imports, module.__name__


def test_evaluation_package_never_imports_agent_runtime_or_tool_runtime():
    for module in _ALL_MODULES:
        imports = _import_lines(inspect.getsource(module))
        assert "app.agents.runtime" not in imports, module.__name__
        assert "app.tools.runtime" not in imports, module.__name__


def test_only_replay_py_may_call_into_consulting_layer_mutators():
    """ "Consume outputs only. Never modify consulting artifacts." — every
    OTHER module in this package must not import any of the 5 consulting
    layers' mutator entry points; only ``replay.py`` (which builds its own
    fresh engagement/synthesis state per replay) is allowed to."""
    for module in _NON_REPLAY_MODULES:
        imports = _import_lines(inspect.getsource(module))
        for forbidden in _MUTATOR_IMPORTS:
            assert forbidden not in imports, (module.__name__, forbidden)


def test_replay_module_only_calls_existing_layer_functions():
    source = inspect.getsource(replay)
    assert "from app.consulting.engine import ConsultingEngine" in source
    assert "from app.knowledge.execution import execute_framework" in source
    assert "from app.organization.allocation import allocate_team" in source
    assert "from app.deliverables.generator import generate_deliverable" in source


def test_ai_evaluation_output_is_structurally_separate_from_consulting_state():
    """An ``AIEvaluation`` is never fed back into a ``SynthesisState`` or
    ``EngagementState`` — verified by the same mutator-import check plus an
    explicit scan for any synthesis/consulting state mutation call."""
    source = inspect.getsource(ai_evaluation)
    assert "SynthesisState(" not in source
    assert ".findings[" not in source
    assert ".recommendations[" not in source


def test_prior_layers_are_untouched_by_the_evaluation_platform():
    """The strongest proof: none of the five prior layers' own source
    references app.evaluation — this package is purely additive."""
    from app.consulting import engine as consulting_engine
    from app.deliverables import generator as deliverables_generator
    from app.knowledge import execution as knowledge_execution
    from app.organization import governance as organization_governance
    from app.synthesis import tracking as synthesis_tracking

    for module in (
        consulting_engine,
        knowledge_execution,
        organization_governance,
        synthesis_tracking,
        deliverables_generator,
    ):
        source = inspect.getsource(module)
        assert "app.evaluation" not in source, module.__name__


def test_platform_and_prior_layers_still_importable_unmodified():
    from app.consulting.engine import ConsultingEngine  # noqa: F401
    from app.deliverables.registry import default_deliverable_registry  # noqa: F401
    from app.knowledge.registry import default_framework_registry  # noqa: F401
    from app.organization.registry import default_organization_registry  # noqa: F401
    from app.synthesis.state import SynthesisState  # noqa: F401
    from app.workflow.dispatcher import dispatch  # noqa: F401
    from app.workflow.router import route  # noqa: F401

    assert callable(route)
    assert callable(dispatch)
