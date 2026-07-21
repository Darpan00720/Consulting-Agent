"""Tests for the Tool Runtime (ADR-013 W5, requirement 3/6/7/10).

Execution wrapper, integrated permission checks, timeout, retries,
cancellation, telemetry, context propagation, and error mapping.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, dataclass, field

import pytest

from app.tools.models import (
    OperationClass,
    ToolHealthResult,
    ToolHealthState,
    ToolMetadata,
    ToolResponse,
    ToolType,
)
from app.tools.permissions import PermissionPolicy
from app.tools.runtime import CancellationToken, ToolRuntime

_RO = OperationClass.READ_ONLY
_WR = OperationClass.WRITE
_DG = OperationClass.DANGEROUS


def _run(coro):
    return asyncio.run(coro)


@dataclass
class ScriptedTool:
    id: str = "scripted"
    name: str = "Scripted"
    version: str = "1.0.0"
    description: str = "test"
    caps: tuple = ("op",)
    tool_type: ToolType = ToolType.CLI
    behavior: str = "success"  # success | fail | raise | hang
    op_classes: dict = field(default_factory=lambda: {"op": _RO})
    calls: list = field(default_factory=list)

    @property
    def capabilities(self):
        return self.caps

    @property
    def type(self):
        return self.tool_type

    async def health(self) -> ToolHealthResult:
        return ToolHealthResult(ToolHealthState.HEALTHY)

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="test",
            tool_type=self.tool_type,
            backing_system="scripted",
            operation_classes=self.op_classes,
        )

    async def execute(self, request) -> ToolResponse:
        self.calls.append(request)
        if self.behavior == "raise":
            raise RuntimeError("tool boom")
        if self.behavior == "fail":
            return ToolResponse(success=False, error="reported failure")
        if self.behavior == "hang":
            await asyncio.sleep(3600)
        return ToolResponse(success=True, output="ok")


class FlakyTool(ScriptedTool):
    def __init__(self, fail_times: int, **kw):
        super().__init__(**kw)
        self.fail_times = fail_times
        self.call_count = 0

    async def execute(self, request):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            return ToolResponse(
                success=False, error=f"attempt {self.call_count} failed"
            )
        return ToolResponse(success=True, output="recovered")


# ---- Basic execution --------------------------------------------------------


def test_successful_execution():
    runtime = ToolRuntime()
    result = _run(runtime.execute(ScriptedTool(), "op", trace_id="t1"))
    assert result.success is True
    assert result.output == "ok"
    assert result.error is None


def test_tool_business_logic_and_runtime_policy_are_separate():
    tool = ScriptedTool()
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t1"))
    assert result.attempts == 1
    assert result.duration_ms >= 0


# ---- Permission checks (requirement 3/5) -----------------------------------


def test_read_only_operation_allowed_by_default():
    result = _run(
        ToolRuntime().execute(ScriptedTool(op_classes={"op": _RO}), "op", trace_id="t")
    )
    assert result.success is True
    assert result.permission_decision.value == "allow"


def test_write_operation_requires_interactive_approval():
    tool = ScriptedTool(op_classes={"op": _WR})
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t"))
    assert result.success is False
    assert result.error_type == "PermissionDenied"
    assert result.permission_decision.value == "interactive"
    assert tool.calls == []  # never attempted


def test_write_operation_proceeds_when_approved():
    tool = ScriptedTool(op_classes={"op": _WR})
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t", approved=True))
    assert result.success is True
    assert len(tool.calls) == 1


def test_dangerous_operation_denied_even_when_approved():
    """DANGEROUS is DENY, not INTERACTIVE — `approved=True` cannot bypass a
    hard deny (only unlocks an INTERACTIVE gate)."""
    tool = ScriptedTool(op_classes={"op": _DG})
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t", approved=True))
    assert result.success is False
    assert result.permission_decision.value == "deny"
    assert tool.calls == []


def test_undeclared_operation_defaults_to_dangerous():
    """An operation the tool never declared in operation_classes is treated
    as the MOST conservative class, never assumed safe."""
    tool = ScriptedTool(op_classes={})  # "op" undeclared
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t"))
    assert result.success is False
    assert result.permission_decision.value == "deny"


def test_custom_policy_can_relax_a_specific_tool():
    policy = PermissionPolicy()
    policy.allow("scripted", _WR)
    tool = ScriptedTool(op_classes={"op": _WR})
    result = _run(ToolRuntime(policy=policy).execute(tool, "op", trace_id="t"))
    assert result.success is True  # no approval needed — policy allows outright


# ---- Context propagation (requirement 6) -----------------------------------


def test_context_propagated_to_tool():
    tool = ScriptedTool()
    _run(
        ToolRuntime().execute(
            tool,
            "op",
            {"x": 1},
            trace_id="ctx-trace",
            agent_id="agent-1",
            caller="test-caller",
        )
    )
    request = tool.calls[0]
    assert request.context.trace_id == "ctx-trace"
    assert request.context.agent_id == "agent-1"
    assert request.context.caller == "test-caller"
    assert request.parameters == {"x": 1}


def test_context_is_immutable():
    tool = ScriptedTool()
    _run(ToolRuntime().execute(tool, "op", trace_id="t"))
    ctx = tool.calls[0].context
    with pytest.raises(FrozenInstanceError):
        ctx.trace_id = "mutated"


def test_no_globals_two_calls_stay_isolated():
    tool = ScriptedTool()
    runtime = ToolRuntime()
    _run(runtime.execute(tool, "op", trace_id="A"))
    _run(runtime.execute(tool, "op", trace_id="B"))
    assert [c.context.trace_id for c in tool.calls] == ["A", "B"]


# ---- Telemetry (requirement 7) --------------------------------------------


def test_telemetry_fields_present():
    result = _run(ToolRuntime().execute(ScriptedTool(), "op", trace_id="tel-1"))
    assert result.tool_id == "scripted"
    assert result.adapter == "scripted"
    assert result.operation == "op"
    assert result.trace_id == "tel-1"


def test_telemetry_log_line_has_no_duplicated_trace_id(caplog):
    with caplog.at_level("DEBUG", logger="app.tools.runtime"):
        _run(ToolRuntime().execute(ScriptedTool(), "op", trace_id="corr-99"))
    line = next(
        r.getMessage() for r in caplog.records if "tool-execute" in r.getMessage()
    )
    assert "trace_id=corr-99" in line
    assert "tool=scripted" in line
    assert "permission=allow" in line


# ---- Error mapping (requirement 10) ----------------------------------------


def test_raised_exception_is_mapped_never_raw():
    result = _run(
        ToolRuntime().execute(ScriptedTool(behavior="raise"), "op", trace_id="t")
    )
    assert result.success is False
    assert result.error_type == "ExecutionFailure"
    assert "tool boom" in result.error


def test_reported_failure_is_mapped():
    result = _run(
        ToolRuntime().execute(ScriptedTool(behavior="fail"), "op", trace_id="t")
    )
    assert result.error_type == "ExecutionFailure"


def test_runtime_never_raises_a_raw_exception():
    _run(
        ToolRuntime().execute(ScriptedTool(behavior="raise"), "op", trace_id="t")
    )  # must not raise


# ---- Timeout ----------------------------------------------------------------


def test_timeout_maps_to_timeout_error():
    result = _run(
        ToolRuntime().execute(
            ScriptedTool(behavior="hang"), "op", trace_id="t", timeout_s=0.05
        )
    )
    assert result.error_type == "Timeout"


# ---- Cancellation -------------------------------------------------------------


def test_cancellation_before_execution():
    token = CancellationToken()
    token.cancel()
    result = _run(
        ToolRuntime().execute(ScriptedTool(), "op", trace_id="t", cancellation=token)
    )
    assert result.error_type == "Cancelled"


def test_cancellation_mid_execution():
    tool = ScriptedTool(behavior="hang")
    token = CancellationToken()

    async def _go():
        task = asyncio.ensure_future(
            ToolRuntime().execute(tool, "op", trace_id="t", cancellation=token)
        )
        await asyncio.sleep(0.02)
        token.cancel()
        return await task

    result = _run(_go())
    assert result.error_type == "Cancelled"


def test_cancelled_is_never_retried():
    token = CancellationToken()
    token.cancel()
    tool = FlakyTool(fail_times=100)
    result = _run(
        ToolRuntime().execute(
            tool, "op", trace_id="t", cancellation=token, max_retries=5
        )
    )
    assert result.error_type == "Cancelled"
    assert tool.call_count == 0


# ---- Retries (requirement 3) ------------------------------------------------


def test_no_retries_by_default():
    tool = FlakyTool(fail_times=1)
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t"))
    assert result.success is False
    assert result.attempts == 1


def test_retries_recover_a_transient_failure():
    tool = FlakyTool(fail_times=2)
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t", max_retries=3))
    assert result.success is True
    assert result.attempts == 3


def test_permission_denied_is_never_retried():
    tool = ScriptedTool(op_classes={"op": _DG})
    result = _run(ToolRuntime().execute(tool, "op", trace_id="t", max_retries=5))
    assert result.attempts == 0  # rejected before any attempt loop
