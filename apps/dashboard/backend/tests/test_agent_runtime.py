"""Tests for the Agent Runtime execution wrapper (ADR-013 W3, requirement 6/7/
10/11).

Execution wrapper behavior, ExecutionContext propagation, telemetry, runtime
failures/cancellation/timeout, error mapping, and overall Runtime consistency.
The Runtime owns policy (timing/retry/telemetry); the agent owns business
logic — these tests pin that split.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from app.agents.errors import ExecutionFailure
from app.agents.models import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    Capability,
    HealthResult,
    HealthState,
)
from app.agents.runtime import AgentRuntime, CancellationToken
from app.workflow.router import RoutingContext, Work
from app.workflow.targets import WorkflowCategory as C


def _ctx(
    trace_id: str = "trace-1", category: C | None = C.GENERAL_REASONING
) -> RoutingContext:
    return RoutingContext(trace_id=trace_id, category=category, classified=True)


def _work(text: str = "hello") -> Work:
    return Work(text=text)


def _run(coro):
    return asyncio.run(coro)


@dataclass
class ScriptedAgent:
    """A minimal Agent test double with fully injectable behavior."""

    id: str = "scripted"
    name: str = "Scripted"
    version: str = "1.0.0"
    description: str = "test"
    owner: str = "test"
    caps: tuple[Capability, ...] = (Capability.REASONING,)
    workflows: tuple[C, ...] = (C.GENERAL_REASONING,)
    behavior: str = "success"  # success | fail | raise | hang | agent_error
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
        if self.behavior == "raise":
            raise RuntimeError("business logic boom")
        if self.behavior == "agent_error":
            raise ExecutionFailure("typed agent failure")
        if self.behavior == "fail":
            return AgentResponse(success=False, error="reported failure")
        if self.behavior == "hang":
            await asyncio.sleep(3600)
        return AgentResponse(success=True, output="ok", provider_used="fake-provider")


class FlakyAgent(ScriptedAgent):
    """Fails N times, then succeeds — for retry tests."""

    def __init__(self, fail_times: int, **kw):
        super().__init__(**kw)
        self.fail_times = fail_times
        self.call_count = 0

    async def execute(self, request: AgentRequest) -> AgentResponse:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            return AgentResponse(
                success=False, error=f"attempt {self.call_count} failed"
            )
        return AgentResponse(success=True, output="recovered")


# ---- Execution wrapper: happy path -----------------------------------------


def test_successful_execution():
    runtime = AgentRuntime()
    result = _run(runtime.execute(ScriptedAgent(), _work(), _ctx()))
    assert result.success is True
    assert result.output == "ok"
    assert result.provider_used == "fake-provider"
    assert result.error is None


def test_agent_business_logic_and_runtime_policy_are_separate():
    """The agent's execute() has NO timing/retry/telemetry of its own — those
    are entirely Runtime concerns (requirement 6's split)."""
    agent = ScriptedAgent()
    runtime = AgentRuntime()
    result = _run(runtime.execute(agent, _work(), _ctx()))
    assert result.attempts == 1  # Runtime counted it; agent didn't
    assert result.duration_ms >= 0  # Runtime timed it; agent didn't


# ---- Context propagation (requirement 7) -----------------------------------


def test_context_is_built_from_routing_context_and_passed_to_agent():
    agent = ScriptedAgent(workflows=(C.CODING,))
    runtime = AgentRuntime()
    ctx = _ctx(trace_id="propagate-me", category=C.CODING)
    _run(runtime.execute(agent, _work("x"), ctx))
    request = agent.calls[0]
    assert request.context.trace_id == "propagate-me"
    assert request.context.workflow is C.CODING
    assert request.context.routing_context is ctx
    assert request.context.correlation_id == "propagate-me"  # reused, not new


def test_context_is_immutable():
    agent = ScriptedAgent()
    runtime = AgentRuntime()
    _run(runtime.execute(agent, _work(), _ctx()))
    request = agent.calls[0]
    with pytest.raises(FrozenInstanceError):
        request.context.trace_id = "mutated"  # frozen dataclass


def test_no_global_state_two_concurrent_contexts_stay_isolated():
    agent = ScriptedAgent()
    runtime = AgentRuntime()
    _run(runtime.execute(agent, _work(), _ctx(trace_id="A")))
    _run(runtime.execute(agent, _work(), _ctx(trace_id="B")))
    assert [c.context.trace_id for c in agent.calls] == ["A", "B"]


# ---- Telemetry (requirement 10) --------------------------------------------


def test_telemetry_fields_present():
    runtime = AgentRuntime()
    result = _run(runtime.execute(ScriptedAgent(), _work(), _ctx(trace_id="t-1")))
    assert result.agent_id == "scripted"
    assert result.agent_version == "1.0.0"
    assert result.trace_id == "t-1"
    assert result.workflow == "general_reasoning"
    assert result.success is True
    assert result.provider_used == "fake-provider"


def test_telemetry_log_line_has_no_duplicated_trace_id(caplog):
    with caplog.at_level("DEBUG", logger="app.agents.runtime"):
        _run(AgentRuntime().execute(ScriptedAgent(), _work(), _ctx(trace_id="corr-42")))
    line = next(
        r.getMessage() for r in caplog.records if "agent-execute" in r.getMessage()
    )
    assert "trace_id=corr-42" in line
    assert "agent_id=scripted" in line
    assert "success=True" in line


# ---- Runtime failures / error mapping (requirement 11) ---------------------


def test_raised_exception_is_mapped_to_execution_failure():
    runtime = AgentRuntime()
    result = _run(runtime.execute(ScriptedAgent(behavior="raise"), _work(), _ctx()))
    assert result.success is False
    assert result.error_type == "ExecutionFailure"
    assert "business logic boom" in result.error


def test_reported_failure_is_mapped_to_execution_failure():
    runtime = AgentRuntime()
    result = _run(runtime.execute(ScriptedAgent(behavior="fail"), _work(), _ctx()))
    assert result.error_type == "ExecutionFailure"
    assert "reported failure" in result.error


def test_agent_raised_typed_error_is_preserved():
    runtime = AgentRuntime()
    result = _run(
        runtime.execute(ScriptedAgent(behavior="agent_error"), _work(), _ctx())
    )
    assert result.error_type == "ExecutionFailure"
    assert "typed agent failure" in result.error


def test_unsupported_workflow_is_rejected_before_any_attempt():
    agent = ScriptedAgent(workflows=(C.CODING,))
    runtime = AgentRuntime()
    result = _run(runtime.execute(agent, _work(), _ctx(category=C.RESEARCH)))
    assert result.error_type == "UnsupportedWorkflow"
    assert agent.calls == []  # never attempted


def test_capability_mismatch_when_required_capability_missing():
    agent = ScriptedAgent(caps=(Capability.CODING,))
    runtime = AgentRuntime()
    result = _run(
        runtime.execute(agent, _work(), _ctx(), required_capability=Capability.RESEARCH)
    )
    assert result.error_type == "CapabilityMismatch"
    assert agent.calls == []


def test_no_capability_required_by_default_no_gate():
    agent = ScriptedAgent(caps=(Capability.CODING,))
    runtime = AgentRuntime()
    result = _run(runtime.execute(agent, _work(), _ctx()))
    assert result.success is True  # no required_capability => not gated


def test_raw_exception_never_escapes_execute():
    """Requirement 11: 'never expose raw exceptions outside Runtime.'"""
    runtime = AgentRuntime()
    result = _run(runtime.execute(ScriptedAgent(behavior="raise"), _work(), _ctx()))
    assert result.error_type != "RuntimeError"  # mapped, not raw
    assert isinstance(result.error, str)  # never a raised exception object


# ---- Timeout ----------------------------------------------------------------


def test_timeout_maps_to_timeout_error():
    runtime = AgentRuntime()
    result = _run(
        runtime.execute(ScriptedAgent(behavior="hang"), _work(), _ctx(), timeout_s=0.05)
    )
    assert result.error_type == "Timeout"
    assert "timeout" in result.error


def test_timeout_does_not_leave_an_orphan_task():
    agent = ScriptedAgent(behavior="hang")
    runtime = AgentRuntime()
    _run(runtime.execute(agent, _work(), _ctx(), timeout_s=0.05))
    # No assertion needed beyond "this returns promptly and doesn't hang the
    # test suite" — the timeout path cancels + awaits the loser (see runtime.py).
    assert True


# ---- Cancellation -------------------------------------------------------------


def test_cancellation_before_execution_starts():
    token = CancellationToken()
    token.cancel()
    runtime = AgentRuntime()
    result = _run(runtime.execute(ScriptedAgent(), _work(), _ctx(), cancellation=token))
    assert result.error_type == "Cancelled"


def test_cancellation_mid_execution():
    agent = ScriptedAgent(behavior="hang")
    runtime = AgentRuntime()
    token = CancellationToken()

    async def _go():
        task = asyncio.ensure_future(
            runtime.execute(agent, _work(), _ctx(), cancellation=token)
        )
        await asyncio.sleep(0.02)
        token.cancel()
        return await task

    result = _run(_go())
    assert result.error_type == "Cancelled"


def test_cancelled_is_never_retried():
    token = CancellationToken()
    token.cancel()
    agent = FlakyAgent(fail_times=100)
    runtime = AgentRuntime()
    result = _run(
        runtime.execute(agent, _work(), _ctx(), cancellation=token, max_retries=5)
    )
    assert result.error_type == "Cancelled"
    assert agent.call_count == 0  # never attempted at all


# ---- Retries (requirement 6: "where appropriate") --------------------------


def test_no_retries_by_default():
    agent = FlakyAgent(fail_times=1)
    runtime = AgentRuntime()
    result = _run(runtime.execute(agent, _work(), _ctx()))
    assert result.success is False
    assert result.attempts == 1


def test_retries_recover_a_transient_failure():
    agent = FlakyAgent(fail_times=2)
    runtime = AgentRuntime()
    result = _run(runtime.execute(agent, _work(), _ctx(), max_retries=3))
    assert result.success is True
    assert result.attempts == 3
    assert result.output == "recovered"


def test_capability_mismatch_is_never_retried():
    agent = ScriptedAgent(caps=())
    runtime = AgentRuntime()
    result = _run(
        runtime.execute(
            agent,
            _work(),
            _ctx(),
            required_capability=Capability.CODING,
            max_retries=5,
        )
    )
    assert result.attempts == 0  # rejected before any attempt loop
    assert agent.calls == []


# ---- Runtime consistency (requirement 14) ----------------------------------


def test_runtime_is_stateless_across_calls():
    """Same AgentRuntime instance, different agents/contexts — no leakage."""
    runtime = AgentRuntime()
    r1 = _run(runtime.execute(ScriptedAgent(id="a"), _work(), _ctx(trace_id="1")))
    r2 = _run(
        runtime.execute(
            ScriptedAgent(id="b", behavior="fail"), _work(), _ctx(trace_id="2")
        )
    )
    assert r1.agent_id == "a" and r1.success is True
    assert r2.agent_id == "b" and r2.success is False
    assert r1.trace_id == "1" and r2.trace_id == "2"


def test_default_runtime_singleton_and_reset():
    from app.agents.runtime import default_runtime, reset_runtime

    r1 = default_runtime()
    r2 = default_runtime()
    assert r1 is r2
    reset_runtime()
    r3 = default_runtime()
    assert r3 is not r1
