"""Tests for Agent Runtime <-> Memory Platform integration (ADR-013 W4,
requirement 6/8/13/15).

Covers: ExecutionContext memory injection, backward compatibility (memory is
None unless a caller opts in), Runtime <-> Service integration, and the
Repository Analysis migration to the Memory Platform (no behavioral change).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app import db
from app.agents.builtin import repository_analysis_agent
from app.agents.models import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    Capability,
    HealthResult,
    HealthState,
)
from app.agents.runtime import AgentRuntime
from app.memory.adapters import default_memory_registry
from app.memory.models import MemoryQuery, MemoryRecord, MemoryType
from app.memory.registry import MemoryRegistry
from app.memory.service import MemoryService, reset_service
from app.workflow.router import RoutingContext, Work
from app.workflow.targets import WorkflowCategory as C


def _run(coro):
    return asyncio.run(coro)


def _ctx(trace_id: str = "t-1", category=C.GENERAL_REASONING) -> RoutingContext:
    return RoutingContext(trace_id=trace_id, category=category, classified=True)


@dataclass
class ScriptedAgent:
    id: str = "scripted"
    name: str = "Scripted"
    version: str = "1.0.0"
    description: str = "test"
    owner: str = "test"
    caps: tuple = (Capability.REASONING,)
    workflows: tuple = (C.GENERAL_REASONING,)
    calls: list = field(default_factory=list)

    @property
    def capabilities(self):
        return self.caps

    @property
    def supported_workflows(self):
        return self.workflows

    async def health(self) -> HealthResult:
        return HealthResult(HealthState.HEALTHY)

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(version=self.version, author=self.owner)

    async def execute(self, request: AgentRequest) -> AgentResponse:
        self.calls.append(request)
        return AgentResponse(success=True, output="ok")


# ---- Backward compatibility: memory is None unless opted in --------------


def test_memory_is_none_by_default_zero_behavior_change():
    """Requirement 15's 'no responsibility leakage' cuts both ways: the
    Runtime must not silently start fetching memory for callers who never
    asked for it."""
    agent = ScriptedAgent()
    runtime = AgentRuntime()
    _run(runtime.execute(agent, Work(text="x"), _ctx()))
    request = agent.calls[0]
    assert request.context.memory is None


# ---- Context injection (requirement 6) -------------------------------------


def test_memory_service_populates_the_execution_context_bundle():
    reg = MemoryRegistry()

    @dataclass
    class InMemoryProvider:
        id: str = "mem"
        types: tuple = (
            MemoryType.SESSION,
            MemoryType.EXECUTION,
            MemoryType.PROJECT,
            MemoryType.KNOWLEDGE,
        )
        strategies: tuple = ()

        def supported_types(self):
            return self.types

        def supported_strategies(self):
            from app.memory.models import RetrievalStrategy

            return (RetrievalStrategy.METADATA,)

        async def store(self, record):
            pass

        async def retrieve(self, key, memory_type=None):
            return None

        async def search(self, query):
            if query.memory_type is MemoryType.SESSION:
                return (
                    MemoryRecord(
                        key="s1", value="session data", memory_type=MemoryType.SESSION
                    ),
                )
            if query.memory_type is MemoryType.EXECUTION:
                return (
                    MemoryRecord(
                        key="e1",
                        value="execution data",
                        memory_type=MemoryType.EXECUTION,
                    ),
                )
            return ()

        async def update(self, key, value, *, memory_type=None):
            pass

        async def delete(self, key, *, memory_type=None):
            pass

        async def exists(self, key, *, memory_type=None):
            return False

        async def health(self):
            return HealthResult(HealthState.HEALTHY)

        def metadata(self):
            return AgentMetadata(version="1.0.0", author="test")

    reg.register(InMemoryProvider())
    service = MemoryService(reg)
    agent = ScriptedAgent()
    runtime = AgentRuntime()

    _run(
        runtime.execute(
            agent, Work(text="x"), _ctx(trace_id="eng-1"), memory_service=service
        )
    )
    request = agent.calls[0]
    assert request.context.memory is not None
    assert request.context.memory.session[0].value == "session data"
    assert request.context.memory.execution[0].value == "execution data"
    assert request.context.memory.project == ()  # nothing declared PROJECT results
    assert request.context.memory.long_term == ()


def test_memory_bundle_scoped_by_trace_id():
    """Every memory query the Runtime issues is scoped to THIS execution's
    trace_id — no cross-engagement leakage."""
    reg = MemoryRegistry()

    @dataclass
    class CapturingProvider:
        id: str = "mem"
        captured: list = field(default_factory=list)

        def supported_types(self):
            return tuple(MemoryType)

        def supported_strategies(self):
            from app.memory.models import RetrievalStrategy

            return (RetrievalStrategy.METADATA,)

        async def store(self, record):
            pass

        async def retrieve(self, key, memory_type=None):
            return None

        async def search(self, query: MemoryQuery):
            self.captured.append(query.metadata_filter.get("engagement_id"))
            return ()

        async def update(self, key, value, *, memory_type=None):
            pass

        async def delete(self, key, *, memory_type=None):
            pass

        async def exists(self, key, *, memory_type=None):
            return False

        async def health(self):
            return HealthResult(HealthState.HEALTHY)

        def metadata(self):
            return AgentMetadata(version="1.0.0", author="test")

    provider = CapturingProvider()
    reg.register(provider)
    service = MemoryService(reg)
    runtime = AgentRuntime()
    _run(
        runtime.execute(
            ScriptedAgent(),
            Work(text="x"),
            _ctx(trace_id="scoped-eng"),
            memory_service=service,
        )
    )
    assert all(eng_id == "scoped-eng" for eng_id in provider.captured)


def test_memory_failure_does_not_fail_the_execution():
    """Requirement 6/15: memory augmentation is best-effort — a broken memory
    provider must not abort an otherwise-successful agent execution."""
    reg = MemoryRegistry()

    @dataclass
    class BrokenProvider:
        id: str = "broken"

        def supported_types(self):
            return tuple(MemoryType)

        def supported_strategies(self):
            from app.memory.models import RetrievalStrategy

            return (RetrievalStrategy.METADATA,)

        async def store(self, record):
            pass

        async def retrieve(self, key, memory_type=None):
            return None

        async def search(self, query):
            raise RuntimeError("memory backend down")

        async def update(self, key, value, *, memory_type=None):
            pass

        async def delete(self, key, *, memory_type=None):
            pass

        async def exists(self, key, *, memory_type=None):
            return False

        async def health(self):
            return HealthResult(HealthState.HEALTHY)

        def metadata(self):
            return AgentMetadata(version="1.0.0", author="test")

    reg.register(BrokenProvider())
    service = MemoryService(reg)
    agent = ScriptedAgent()
    runtime = AgentRuntime()

    result = _run(
        runtime.execute(agent, Work(text="x"), _ctx(), memory_service=service)
    )
    assert result.success is True  # execution succeeded despite memory failing
    assert agent.calls[0].context.memory.session == ()  # best-effort empty, not a crash


# ---- Repository Analysis migration (requirement 8/13) ----------------------


def test_repository_analysis_still_mentions_graphify_after_migration():
    """No behavioral change (requirement 13) — asserted the same way W2/W3
    tests already did."""
    agent = repository_analysis_agent()
    from app.agents.models import ExecutionContext

    ctx = ExecutionContext(
        trace_id="t-1",
        workflow=None,
        routing_context=_ctx(),
        caller="test",
        started_at=0.0,
        correlation_id="t-1",
    )
    result = _run(
        agent.execute(AgentRequest(work=Work(text="what calls this"), context=ctx))
    )
    assert result.success is True
    assert "graphify" in result.output.lower()


def test_repository_analysis_routes_through_the_real_memory_service():
    """Concrete proof the migration is real: monkeypatch default_service() and
    confirm Repository Analysis actually calls it, not an inline placeholder."""
    reset_service()
    reg = default_memory_registry()
    called = {"hit": False}
    graphify = reg.get("graphify")

    async def spy_search(query):
        called["hit"] = True
        return (
            MemoryRecord(
                key="k",
                value="spied graphify result",
                memory_type=MemoryType.REPOSITORY,
            ),
        )

    graphify.search = spy_search  # type: ignore[method-assign]

    import app.memory.service as service_module

    service_module._service = MemoryService(reg)

    agent = repository_analysis_agent()
    from app.agents.models import ExecutionContext

    ctx = ExecutionContext(
        trace_id="t-1",
        workflow=None,
        routing_context=_ctx(),
        caller="test",
        started_at=0.0,
        correlation_id="t-1",
    )
    result = _run(agent.execute(AgentRequest(work=Work(text="x"), context=ctx)))
    assert called["hit"] is True
    assert result.output == "spied graphify result"
    reset_service()


def test_repository_analysis_runner_override_still_bypasses_memory_platform():
    """The agent-level `runner` escape hatch (W3) still works unchanged — it
    bypasses the Memory Platform entirely, exactly as it bypassed the inline
    placeholder before."""

    async def fake_runner(request):
        return AgentResponse(success=True, output="overridden, no memory involved")

    agent = repository_analysis_agent(runner=fake_runner)
    from app.agents.models import ExecutionContext

    ctx = ExecutionContext(
        trace_id="t-1",
        workflow=None,
        routing_context=_ctx(),
        caller="test",
        started_at=0.0,
        correlation_id="t-1",
    )
    result = _run(agent.execute(AgentRequest(work=Work(text="x"), context=ctx)))
    assert result.output == "overridden, no memory involved"


# ---- Runtime integration end-to-end (requirement 14) -----------------------


def test_runtime_integration_end_to_end_with_default_memory_registry(
    monkeypatch, tmp_path
):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "memory-runtime-test.db")
    db.reset_for_tests()
    service = MemoryService(default_memory_registry())
    checkpoint = service.registry.get("checkpoint")
    checkpoint.save("eng-e2e", "classify", "classified!")

    runtime = AgentRuntime()
    agent = ScriptedAgent(workflows=(C.GENERAL_REASONING,))
    result = _run(
        runtime.execute(
            agent, Work(text="x"), _ctx(trace_id="eng-e2e"), memory_service=service
        )
    )
    assert result.success is True
    request = agent.calls[0]
    assert any(r.value == "classified!" for r in request.context.memory.execution)
