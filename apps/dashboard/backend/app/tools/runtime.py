"""Tool Runtime (requirement 3) — the execution wrapper.

Owns EXECUTION POLICY: permission checks, timing, telemetry, exception →
``ToolError`` mapping, bounded retries, ``ToolExecutionContext``
construction/propagation, and cancellation. The ADAPTER owns backend-specific
logic (``Tool.execute()``) — the Runtime never touches what an adapter does,
only how and WHETHER it is called (requirement 12: "Tool Platform: external
integrations", no responsibility leakage).

"Agents request tools through the runtime; agents never invoke adapters
directly" (requirement 3) — this module is the ONLY place ``Tool.execute()``
is called in the platform.

Deliberately imports nothing from ``app.agents``/``app.workflow``/
``app.memory`` at runtime — the same lower-layer discipline W3/W4 established.
Its own ``CancellationToken`` is intentionally a separate, same-shaped class
from ``app.agents.runtime.CancellationToken``/``app.workflow.dispatcher.
CancellationToken`` — duplicated in spirit, not in code, to avoid a reverse
dependency from this lower layer upward.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from app.tools.errors import (
    Cancelled,
    ExecutionFailure,
    PermissionDenied,
    Timeout,
    ToolError,
)
from app.tools.models import (
    OperationClass,
    PermissionDecision,
    ToolExecutionContext,
    ToolRequest,
    ToolResponse,
    ToolResult,
)
from app.tools.permissions import PermissionPolicy
from app.tools.tool import Tool

if TYPE_CHECKING:
    from app.memory.models import ExecutionMemoryBundle
    from app.workflow.targets import WorkflowCategory

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 20.0


class CancellationToken:
    """Tool-Runtime-local cancellation signal — same shape as
    ``app.agents.runtime.CancellationToken`` (W3), intentionally not shared
    (see module docstring)."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


class ToolRuntime:
    """Executes one ``Tool`` operation. Stateless beyond its permission policy
    — safe to share a single instance (``default_runtime()``) across calls."""

    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self.policy = policy or PermissionPolicy()

    async def execute(
        self,
        tool: Tool,
        operation: str,
        parameters: dict[str, Any] | None = None,
        *,
        trace_id: str,
        agent_id: str | None = None,
        workflow: WorkflowCategory | None = None,
        caller: str = "agent",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        cancellation: CancellationToken | None = None,
        max_retries: int = 0,
        approved: bool = False,
        memory_context: ExecutionMemoryBundle | None = None,
        tool_context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Run ``tool``'s ``operation`` once (or with bounded retries), never
        raising (requirement 10's discipline). ``approved=True`` is the hook a
        caller uses to represent "a human already approved this out-of-band"
        for an INTERACTIVE-classified operation — the Runtime never itself
        implements an approval UI, only the gate.
        """
        start = time.monotonic()
        token = cancellation or CancellationToken()

        exec_ctx = ToolExecutionContext(
            trace_id=trace_id,
            agent_id=agent_id,
            workflow=workflow,
            caller=caller,
            started_at=time.time(),
            memory_context=memory_context,
            tool_context=tool_context or {},
        )

        # Permission check (requirement 3/5) — BEFORE any execution attempt.
        # An operation absent from the tool's declared map is the most
        # conservative class (DANGEROUS), never assumed safe.
        meta = tool.metadata()
        op_class = meta.operation_classes.get(operation, OperationClass.DANGEROUS)
        decision = self.policy.evaluate(tool.id, op_class)

        if decision is PermissionDecision.DENY:
            return self._finish(
                tool,
                operation,
                start,
                0,
                None,
                PermissionDenied(
                    f"'{tool.id}:{operation}' ({op_class.value}) is denied by policy"
                ),
                decision,
                trace_id,
            )
        if decision is PermissionDecision.INTERACTIVE and not approved:
            return self._finish(
                tool,
                operation,
                start,
                0,
                None,
                PermissionDenied(
                    f"'{tool.id}:{operation}' ({op_class.value}) requires "
                    "interactive approval"
                ),
                decision,
                trace_id,
            )

        request = ToolRequest(
            operation=operation, parameters=parameters or {}, context=exec_ctx
        )
        attempts = 0
        last_error: ToolError | None = None
        last_output: Any = None

        while attempts <= max_retries:
            attempts += 1
            if token.is_cancelled:
                return self._finish(
                    tool,
                    operation,
                    start,
                    attempts,
                    None,
                    Cancelled("cancelled before attempt"),
                    decision,
                    trace_id,
                )

            response, error = await self._run_once(tool, request, timeout_s, token)
            if error is not None:
                last_error = error
                if not self._retryable(error):
                    return self._finish(
                        tool,
                        operation,
                        start,
                        attempts,
                        None,
                        error,
                        decision,
                        trace_id,
                    )
                continue

            assert response is not None
            if response.success:
                return self._finish(
                    tool,
                    operation,
                    start,
                    attempts,
                    response.output,
                    None,
                    decision,
                    trace_id,
                )
            last_error = ExecutionFailure(response.error or "tool reported failure")
            last_output = response.output

        return self._finish(
            tool,
            operation,
            start,
            attempts,
            last_output,
            last_error,
            decision,
            trace_id,
        )

    @staticmethod
    def _retryable(error: ToolError) -> bool:
        # Same taxonomy as AgentRuntime (W3): only ExecutionFailure/Timeout MAY
        # be transient. PermissionDenied/Cancelled/UnsupportedCapability are
        # never retried — retrying cannot fix a policy decision or a cancel.
        return type(error) in (ExecutionFailure, Timeout)

    async def _run_once(
        self,
        tool: Tool,
        request: ToolRequest,
        timeout_s: float,
        token: CancellationToken,
    ) -> tuple[ToolResponse | None, ToolError | None]:
        exec_task: asyncio.Task = asyncio.ensure_future(
            self._safe_execute(tool, request)
        )
        cancel_task: asyncio.Task = asyncio.ensure_future(token.wait())
        done, _pending = await asyncio.wait(
            {exec_task, cancel_task},
            timeout=timeout_s,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if cancel_task in done:
            exec_task.cancel()
            await asyncio.gather(exec_task, return_exceptions=True)
            return None, Cancelled("cancelled mid-execution")

        if exec_task not in done:
            exec_task.cancel()
            await asyncio.gather(exec_task, return_exceptions=True)
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)
            return None, Timeout(f"timeout after {timeout_s}s")

        cancel_task.cancel()
        await asyncio.gather(cancel_task, return_exceptions=True)
        return exec_task.result()

    @staticmethod
    async def _safe_execute(
        tool: Tool, request: ToolRequest
    ) -> tuple[ToolResponse | None, ToolError | None]:
        try:
            response = await tool.execute(request)
            return response, None
        except ToolError as exc:
            return None, exc
        except Exception as exc:  # noqa: BLE001 — never let a raw exception escape
            return None, ExecutionFailure(f"{type(exc).__name__}: {exc}")

    def _finish(
        self,
        tool: Tool,
        operation: str,
        start: float,
        attempts: int,
        output: Any,
        error: ToolError | None,
        decision: PermissionDecision,
        trace_id: str,
    ) -> ToolResult:
        result = ToolResult(
            success=error is None,
            output=output,
            error=str(error) if error else None,
            error_type=type(error).__name__ if error else None,
            tool_id=tool.id,
            adapter=tool.metadata().backing_system,
            operation=operation,
            duration_ms=(time.monotonic() - start) * 1000,
            attempts=attempts,
            trace_id=trace_id,
            permission_decision=decision,
        )
        _log_execution(result)
        return result


def _log_execution(result: ToolResult) -> None:
    """One telemetry line per tool execution (requirement 7): trace_id, tool,
    adapter, duration, success/failure, permission decision, retry count.
    ``trace_id`` is always the caller-supplied one — never invented — so this
    correlates with Runtime (agent-execute) and Memory (memory-op) telemetry
    without a shared global (requirement 7's "no duplicated telemetry")."""
    log.debug(
        "tool-execute trace_id=%s tool=%s adapter=%s operation=%s duration_ms=%.1f "
        "success=%s permission=%s attempts=%d error_type=%s",
        result.trace_id,
        result.tool_id,
        result.adapter,
        result.operation,
        result.duration_ms,
        result.success,
        result.permission_decision.value,
        result.attempts,
        result.error_type,
    )


_runtime: ToolRuntime | None = None


def default_runtime() -> ToolRuntime:
    """Lazy singleton (mirrors ``app.agents.runtime.default_runtime()``)."""
    global _runtime
    if _runtime is None:
        _runtime = ToolRuntime()
    return _runtime


def reset_runtime() -> None:
    """Rebuild on next use (tests)."""
    global _runtime
    _runtime = None
