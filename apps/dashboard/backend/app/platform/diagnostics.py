"""Lightweight operational diagnostics (requirement 10) — NOT a benchmarking
framework. Each probe runs ONE representative operation and times it.

Honest scope: dispatch/runtime-overhead probes use a tiny synthetic no-op
Agent/Target constructed only for this diagnostic — NOT the real
``ClaudeAgent`` (which would make a real, possibly-billed LLM call and
require live credentials just to answer "how fast is the wrapper"). Memory
and tool latency probes DO use the platform's real registered providers
(the checkpoint adapter's real SQLite path; the Graphify tool adapter's
real — if placeholder — code path), since neither requires network egress
or credentials.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.platform.bootstrap import Platform


@dataclass(frozen=True)
class DiagnosticsReport:
    startup_ms: float
    routing_latency_ms: float | None
    runtime_overhead_ms: float | None
    memory_lookup_latency_ms: float | None
    tool_execution_latency_ms: float | None
    notes: tuple[str, ...] = field(default_factory=tuple)


async def _measure_routing_latency() -> float:
    """Pure, real, deterministic — no synthetic double needed (W1 has no I/O)."""
    from app.workflow.router import RoutingContext, Work, route

    start = time.monotonic()
    route(Work(text="diagnostic probe"), RoutingContext(trace_id="diagnostics"))
    return (time.monotonic() - start) * 1000


async def _measure_runtime_overhead() -> float:
    """The Agent RUNTIME wrapper's own cost (context construction, guardrail
    checks, telemetry) — isolated from any real LLM call via a synthetic
    no-op probe agent."""
    from dataclasses import dataclass as _dc

    from app.agents.models import (
        AgentMetadata,
        AgentRequest,
        AgentResponse,
        HealthResult,
        HealthState,
    )
    from app.agents.runtime import AgentRuntime
    from app.workflow.router import RoutingContext, Work
    from app.workflow.targets import WorkflowCategory

    @_dc
    class _NoOpProbeAgent:
        id: str = "diagnostics-probe"
        name: str = "Diagnostics Probe"
        version: str = "1.0.0"
        description: str = "synthetic no-op agent for runtime-overhead diagnostics only"
        owner: str = "platform"

        @property
        def capabilities(self):
            return ()

        @property
        def supported_workflows(self):
            return (WorkflowCategory.GENERAL_REASONING,)

        async def health(self) -> HealthResult:
            return HealthResult(HealthState.HEALTHY)

        def metadata(self) -> AgentMetadata:
            return AgentMetadata(version=self.version, author=self.owner)

        async def execute(self, request: AgentRequest) -> AgentResponse:
            return AgentResponse(success=True, output="diagnostic-probe-ok")

    runtime = AgentRuntime()
    ctx = RoutingContext(
        trace_id="diagnostics",
        category=WorkflowCategory.GENERAL_REASONING,
        classified=True,
    )
    start = time.monotonic()
    await runtime.execute(_NoOpProbeAgent(), Work(text="probe"), ctx)
    return (time.monotonic() - start) * 1000


async def _measure_memory_latency(
    platform: Platform,
) -> tuple[float | None, str | None]:
    """Bug found by test (W6): ``MemoryService.retrieve`` never RAISES on
    failure (that is its whole "never raise" design, W4) — it returns a
    ``MemoryResult`` with ``success=False`` instead. A bare try/except here
    would silently report a "successful" latency for a provider-unavailable
    probe. ``result.success`` must be checked explicitly; a SUCCESSFUL
    retrieve with an empty result (the key genuinely doesn't exist) is still
    a valid, real latency measurement — only ``success=False`` is a failure.
    """
    try:
        start = time.monotonic()
        result = await platform.memory_service.retrieve(
            "diagnostics::probe", trace_id="diagnostics"
        )
        elapsed = (time.monotonic() - start) * 1000
        if not result.success:
            return None, f"memory probe failed: {result.error_type}: {result.error}"
        return elapsed, None
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never raise
        return None, f"memory probe failed: {type(exc).__name__}: {exc}"


async def _measure_tool_latency(platform: Platform) -> tuple[float | None, str | None]:
    """Same fix as ``_measure_memory_latency`` — ``ToolRuntime.execute`` also
    never raises by design (W5); check ``result.success`` explicitly."""
    graphify = platform.tool_registry.get("graphify")
    if graphify is None:
        return None, "graphify tool not registered"
    try:
        start = time.monotonic()
        result = await platform.tool_runtime.execute(
            graphify, "query_graph", {"q": "diagnostic"}, trace_id="diagnostics"
        )
        elapsed = (time.monotonic() - start) * 1000
        if not result.success:
            return None, f"tool probe failed: {result.error_type}: {result.error}"
        return elapsed, None
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never raise
        return None, f"tool probe failed: {type(exc).__name__}: {exc}"


async def run_diagnostics(platform: Platform) -> DiagnosticsReport:
    """Requirement 10: startup time, dispatch/runtime latency, memory lookup
    latency, tool execution latency — one real (or synthetic-but-honest)
    probe per category, never a benchmark loop."""
    notes: list[str] = []

    routing_ms = await _measure_routing_latency()
    runtime_ms = await _measure_runtime_overhead()

    memory_ms, memory_note = await _measure_memory_latency(platform)
    if memory_note:
        notes.append(memory_note)

    tool_ms, tool_note = await _measure_tool_latency(platform)
    if tool_note:
        notes.append(tool_note)

    notes.append(
        "provider latency not probed by default — a real probe would spend "
        "live API quota; use a specific provider's own health/test path if needed"
    )

    return DiagnosticsReport(
        startup_ms=platform.startup_duration_ms,
        routing_latency_ms=routing_ms,
        runtime_overhead_ms=runtime_ms,
        memory_lookup_latency_ms=memory_ms,
        tool_execution_latency_ms=tool_ms,
        notes=tuple(notes),
    )
