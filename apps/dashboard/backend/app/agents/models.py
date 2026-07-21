"""Core data types for the Agent Platform (ADR-013 W3, extended W4).

Capability, lifecycle state (+ legal transitions), health, metadata, execution
context/request/response, and the Runtime's final result — all plain, frozen
dataclasses/enums, no behavior. Kept dependency-free of ``app.workflow`` at
runtime (only ``TYPE_CHECKING`` imports for annotations) so this package stays
the lower layer ``app.workflow`` builds on, never the reverse.

**W4 addition:** ``ExecutionContext.memory`` is a REAL (not TYPE_CHECKING-only)
import of ``app.memory.models.ExecutionMemoryBundle`` — safe and one-directional
(Agent Platform → Memory Platform, mirroring Workflow → Agent Platform, W3),
since ``app.memory`` never imports ``app.agents``.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from app.memory.models import ExecutionMemoryBundle

if TYPE_CHECKING:
    from app.workflow.router import RoutingContext, Work
    from app.workflow.targets import WorkflowCategory


class Capability(StrEnum):
    """What an agent can DO — the platform's own vocabulary (requirement 3).

    Deliberately distinct from ``WorkflowCategory`` (the Workflow Router's
    task-TYPE vocabulary, ADR-013 §3): a capability is a reusable skill an
    agent advertises; a ``WorkflowCategory`` is what one unit of work IS. An
    agent's ``supported_workflows`` is the bridge between the two — kept
    separate so the Agent Platform's public vocabulary never couples to the
    Workflow Router's internal one (no responsibility leakage, requirement 15).
    """

    STRATEGY = "strategy"
    RESEARCH = "research"
    CODING = "coding"
    REPOSITORY_ANALYSIS = "repository-analysis"
    DOCUMENTATION = "documentation"
    CONSULTING = "consulting"
    EVALUATION = "evaluation"
    REASONING = "reasoning"


class AgentState(StrEnum):
    """Lifecycle states (requirement 4)."""

    REGISTERED = "registered"
    READY = "ready"
    BUSY = "busy"
    FAILED = "failed"
    DISABLED = "disabled"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


# Legal transitions: current -> allowed next states (requirement 4). A pair not
# listed is illegal — ``AgentRegistry.set_state`` raises ``IllegalTransitionError``
# rather than silently applying it (registry consistency, requirement 14).
# FAILED -> READY is the explicit "temporary failure without unregistering"
# recovery path the requirement calls out. STOPPED is terminal: a stopped agent
# is re-registered, never resurrected.
_LEGAL_TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.REGISTERED: frozenset(
        {AgentState.READY, AgentState.DISABLED, AgentState.STOPPED, AgentState.UNKNOWN}
    ),
    AgentState.READY: frozenset(
        {
            AgentState.BUSY,
            AgentState.FAILED,
            AgentState.DISABLED,
            AgentState.STOPPED,
            AgentState.UNKNOWN,
        }
    ),
    AgentState.BUSY: frozenset(
        {AgentState.READY, AgentState.FAILED, AgentState.STOPPED}
    ),
    AgentState.FAILED: frozenset(
        {AgentState.READY, AgentState.DISABLED, AgentState.STOPPED, AgentState.UNKNOWN}
    ),
    AgentState.DISABLED: frozenset({AgentState.READY, AgentState.STOPPED}),
    AgentState.UNKNOWN: frozenset(
        {AgentState.READY, AgentState.FAILED, AgentState.DISABLED, AgentState.STOPPED}
    ),
    AgentState.STOPPED: frozenset(),  # terminal
}


def is_legal_transition(current: AgentState, target: AgentState) -> bool:
    """Pure lookup against the transition table. A same-state transition is
    always legal (idempotent no-op)."""
    if current is target:
        return True
    return target in _LEGAL_TRANSITIONS.get(current, frozenset())


class HealthState(StrEnum):
    """Health probe results (requirement 5)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthResult:
    state: HealthState
    detail: str = ""
    checked_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class AgentMetadata:
    """Static agent metadata (requirement 8)."""

    version: str
    author: str
    supported_models: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    required_mcps: tuple[str, ...] = ()
    supported_providers: tuple[str, ...] = ()
    min_runtime_version: str = "1.0.0"


@dataclass(frozen=True)
class ExecutionContext:
    """Standardized context every agent receives (requirement 7).

    Immutable, no globals — built fresh per execution by the Runtime from the
    ``RoutingContext`` the Workflow Router/Dispatcher already produced.
    ``correlation_id`` reuses ``trace_id`` rather than minting a new id — the
    same "no duplicated IDs" discipline ADR-012/W2 telemetry already commits to.

    ``memory`` (W4, requirement 6) is populated by the Runtime ONLY when a
    ``memory_service`` is explicitly passed to ``AgentRuntime.execute()`` —
    ``None`` otherwise, so every pre-W4 caller/test is byte-identical.
    """

    trace_id: str
    workflow: WorkflowCategory | None
    routing_context: RoutingContext
    caller: str
    started_at: float
    correlation_id: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    memory: ExecutionMemoryBundle | None = None


@dataclass(frozen=True)
class AgentRequest:
    """What the Runtime hands to ``Agent.execute()`` — the business-logic
    input, stripped of timing/retry/telemetry (requirement 6's split)."""

    work: Work
    context: ExecutionContext


@dataclass(frozen=True)
class AgentResponse:
    """What ``Agent.execute()`` returns — the agent's own outcome, before the
    Runtime wraps it with timing/telemetry/retries/error-mapping."""

    success: bool
    output: str | None = None
    error: str | None = None
    provider_used: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """The Runtime's final, deterministic output (requirement 8/10). Telemetry
    fields are first-class DATA, not log-only — mirrors ``DispatcherResult``
    (W2)."""

    success: bool
    output: str | None
    error: str | None  # human-readable; never a raw exception (requirement 11)
    error_type: str | None  # the mapped AgentError class name, or None
    agent_id: str
    agent_version: str
    duration_ms: float
    attempts: int
    trace_id: str
    workflow: str | None
    provider_used: str | None
    health_state: str | None
