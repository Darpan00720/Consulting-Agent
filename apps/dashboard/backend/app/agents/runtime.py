"""Agent Runtime (requirement 6) — the execution wrapper.

Owns EXECUTION POLICY: timing, telemetry, exception → ``AgentError`` mapping,
bounded retries, ``ExecutionContext`` construction/propagation, and
cancellation. The AGENT owns business logic (``Agent.execute()``) — the
Runtime never touches what an agent does, only how it is called (requirement
15: "Runtime: agent orchestration. Agent: business logic.").

Deliberately imports nothing from ``app.workflow`` at runtime — the Agent
Platform is the LOWER layer; ``app.workflow.targets`` imports FROM here, never
the reverse. Its own ``CancellationToken`` is intentionally a separate,
same-shaped class from ``app.workflow.dispatcher.CancellationToken`` (W2) —
duplicated in spirit, not in code, specifically to avoid a reverse dependency
from this lower layer up into the workflow package.

Composition with the Dispatcher's OWN timeout (W2): the Dispatcher's
per-target timeout is the OUTER bound around the whole ``Target.invoke()``
call; this Runtime's ``timeout_s`` is an INNER bound around one
``Agent.execute()`` attempt. ``DEFAULT_TIMEOUT_S`` here is deliberately below
the Dispatcher's own default so the common case never double-times-out
confusingly — documented, not accidental.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from app.agents.agent import Agent
from app.agents.errors import (
    AgentError,
    Cancelled,
    CapabilityMismatch,
    ExecutionFailure,
    Timeout,
    UnsupportedWorkflow,
)
from app.agents.models import (
    AgentRequest,
    AgentResponse,
    ExecutionContext,
    ExecutionResult,
)

if TYPE_CHECKING:
    from app.agents.models import Capability
    from app.memory.service import MemoryService
    from app.workflow.router import RoutingContext, Work

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 20.0  # inside the Dispatcher's own outer per-target budget


class CancellationToken:
    """Runtime-local cancellation signal — same shape as the Dispatcher's own
    token (W2), intentionally not imported from it (see module docstring)."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


class AgentRuntime:
    """Executes one ``Agent`` against one unit of work. Stateless — safe to
    share a single instance (``default_runtime()``) across calls."""

    async def execute(
        self,
        agent: Agent,
        work: Work,
        routing_context: RoutingContext,
        *,
        caller: str = "dispatcher",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        cancellation: CancellationToken | None = None,
        max_retries: int = 0,
        required_capability: Capability | None = None,
        memory_service: MemoryService | None = None,
    ) -> ExecutionResult:
        """Run ``agent`` once (or with bounded retries), never raising
        (requirement 8's discipline, one layer down from the Dispatcher).

        ``max_retries`` defaults to 0 — Dispatcher already owns cross-target
        fallback (W2); this Runtime's retry is a WITHIN-one-agent concern, off
        by default so builtin agents' behavior is unchanged unless a caller
        explicitly opts in.

        ``memory_service`` (W4, requirement 6) is optional and ``None`` by
        default: "the Runtime requests memory" means the Runtime is the thing
        that CALLS the Memory Service to build the bundle — it does so only
        when a caller supplies one, so every pre-W4 execution is unaffected.
        """
        start = time.monotonic()
        token = cancellation or CancellationToken()

        memory_bundle = None
        if memory_service is not None:
            memory_bundle = await self._gather_memory(memory_service, routing_context)

        exec_ctx = ExecutionContext(
            trace_id=routing_context.trace_id,
            workflow=routing_context.category,
            routing_context=routing_context,
            caller=caller,
            started_at=time.time(),
            correlation_id=routing_context.trace_id,  # reused — no duplicated IDs
            memory=memory_bundle,
        )

        if (
            required_capability is not None
            and required_capability not in agent.capabilities
        ):
            return self._finish(
                agent,
                start,
                0,
                None,
                CapabilityMismatch(
                    f"{agent.id} does not declare capability "
                    f"{required_capability.value}"
                ),
                exec_ctx,
            )

        if (
            exec_ctx.workflow is not None
            and exec_ctx.workflow not in agent.supported_workflows
        ):
            return self._finish(
                agent,
                start,
                0,
                None,
                UnsupportedWorkflow(
                    f"{agent.id} does not support workflow {exec_ctx.workflow.value}"
                ),
                exec_ctx,
            )

        request = AgentRequest(work=work, context=exec_ctx)
        attempts = 0
        last_error: AgentError | None = None
        last_output: str | None = None
        provider_used: str | None = None

        while attempts <= max_retries:
            attempts += 1
            if token.is_cancelled:
                return self._finish(
                    agent,
                    start,
                    attempts,
                    None,
                    Cancelled("cancelled before attempt"),
                    exec_ctx,
                )

            response, error = await self._run_once(agent, request, timeout_s, token)
            if error is not None:
                last_error = error
                if not self._retryable(error):
                    return self._finish(
                        agent, start, attempts, None, error, exec_ctx, provider_used
                    )
                continue

            assert response is not None
            provider_used = response.provider_used
            if response.success:
                return self._finish(
                    agent,
                    start,
                    attempts,
                    response.output,
                    None,
                    exec_ctx,
                    provider_used,
                )
            last_error = ExecutionFailure(response.error or "agent reported failure")
            last_output = response.output

        return self._finish(
            agent, start, attempts, last_output, last_error, exec_ctx, provider_used
        )

    @staticmethod
    async def _gather_memory(
        memory_service: MemoryService, routing_context: RoutingContext
    ):
        """ "The Runtime requests memory" (requirement 6) — session, execution,
        project, and long-term memory, scoped by ``trace_id``. Uses
        ``MemoryService.search`` (never a raw provider call) so caching,
        telemetry, and error-mapping all apply here exactly as they do for any
        other memory access — no special-cased path. A provider error on one
        memory type does not abort the others; each is independently
        best-effort (an empty tuple on failure), since memory augmentation must
        never be allowed to fail an execution (the same fail-open spirit as
        every other layer in this program)."""
        from app.memory.models import ExecutionMemoryBundle, MemoryQuery, MemoryType

        trace_id = routing_context.trace_id
        filt = {"engagement_id": trace_id}

        async def _fetch(memory_type: MemoryType) -> tuple:
            result = await memory_service.search(
                MemoryQuery(memory_type=memory_type, metadata_filter=filt),
                trace_id=trace_id,
            )
            return result.records if result.success else ()

        return ExecutionMemoryBundle(
            session=await _fetch(MemoryType.SESSION),
            execution=await _fetch(MemoryType.EXECUTION),
            project=await _fetch(MemoryType.PROJECT),
            long_term=await _fetch(MemoryType.KNOWLEDGE),
        )

    @staticmethod
    def _retryable(error: AgentError) -> bool:
        # ExecutionFailure/Timeout MAY be transient; Cancelled must never be
        # retried; CapabilityMismatch/UnsupportedWorkflow are deterministic —
        # retrying cannot fix them (requirement 11's error taxonomy applied to
        # requirement 6's "retries where appropriate").
        return type(error) in (ExecutionFailure, Timeout)

    async def _run_once(
        self,
        agent: Agent,
        request: AgentRequest,
        timeout_s: float,
        token: CancellationToken,
    ) -> tuple[AgentResponse | None, AgentError | None]:
        exec_task: asyncio.Task = asyncio.ensure_future(
            self._safe_execute(agent, request)
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
        agent: Agent, request: AgentRequest
    ) -> tuple[AgentResponse | None, AgentError | None]:
        try:
            response = await agent.execute(request)
            return response, None
        except AgentError as exc:
            return None, exc
        except Exception as exc:  # noqa: BLE001 — never let a raw exception escape
            return None, ExecutionFailure(f"{type(exc).__name__}: {exc}")

    def _finish(
        self,
        agent: Agent,
        start: float,
        attempts: int,
        output: str | None,
        error: AgentError | None,
        exec_ctx: ExecutionContext,
        provider_used: str | None = None,
    ) -> ExecutionResult:
        result = ExecutionResult(
            success=error is None,
            output=output,
            error=str(error) if error else None,
            error_type=type(error).__name__ if error else None,
            agent_id=agent.id,
            agent_version=agent.version,
            duration_ms=(time.monotonic() - start) * 1000,
            attempts=attempts,
            trace_id=exec_ctx.trace_id,
            workflow=exec_ctx.workflow.value if exec_ctx.workflow else None,
            provider_used=provider_used,
            health_state=None,
        )
        _log_execution(result)
        return result


def _log_execution(result: ExecutionResult) -> None:
    """One telemetry line per execution (requirement 10): agent id, version,
    duration, success, provider used, trace_id, workflow, error type.
    ``trace_id`` is reused from the RoutingContext — no duplicated telemetry,
    the same discipline as the Dispatcher's own log line (W2 §7), so this line
    and ``dispatch trace_id=...`` and ``route trace_id=...`` all correlate."""
    log.debug(
        "agent-execute trace_id=%s agent_id=%s version=%s workflow=%s success=%s "
        "duration_ms=%.1f attempts=%d provider=%s error_type=%s",
        result.trace_id,
        result.agent_id,
        result.agent_version,
        result.workflow,
        result.success,
        result.duration_ms,
        result.attempts,
        result.provider_used,
        result.error_type,
    )


_runtime: AgentRuntime | None = None


def default_runtime() -> AgentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime


def reset_runtime() -> None:
    """Rebuild on next use (tests) — mirrors ``providers.reset_chain()``."""
    global _runtime
    _runtime = None
