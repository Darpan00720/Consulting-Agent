"""Core data types for the Tool Platform (ADR-013 W5).

Tool types, operation classification (for permissions), health, metadata,
execution context/request/response, and the Runtime's final result — plain,
frozen dataclasses/enums, no behavior. Dependency-free of ``app.agents``/
``app.workflow``/``app.memory`` at runtime (only ``TYPE_CHECKING`` imports for
annotations), so this stays a lower, independent layer (same discipline as
``app.agents.models``/``app.memory.models``, W3/W4).
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.memory.models import ExecutionMemoryBundle
    from app.workflow.targets import WorkflowCategory


class ToolType(StrEnum):
    """The five supported tool types (requirement 1)."""

    MCP = "mcp"
    CLI = "cli"
    REST_API = "rest-api"
    LOCAL_PROCESS = "local-process"
    KNOWLEDGE_SYNC = "knowledge-sync"


class OperationClass(StrEnum):
    """How one operation is classified for permission purposes (requirement
    5). A tool declares this per-operation in ``ToolMetadata.operation_classes``
    — the Runtime looks it up before consulting the policy; it is never
    inferred or guessed."""

    READ_ONLY = "read-only"
    WRITE = "write"
    DANGEROUS = "dangerous"
    OFFLINE = "offline"


class PermissionDecision(StrEnum):
    """What the policy returns for one (tool, operation-class) pair
    (requirement 5)."""

    ALLOW = "allow"
    DENY = "deny"
    INTERACTIVE = "interactive"  # requires human approval before proceeding


class ToolHealthState(StrEnum):
    """Same 4-value shape as ``app.agents.models.HealthState`` /
    ``app.memory.models.MemoryHealthState`` — deliberately redefined, not
    imported, to keep ``app.tools`` dependency-free (the same duplication-
    over-coupling call W3/W4 made)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ToolHealthResult:
    state: ToolHealthState
    detail: str = ""
    checked_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ToolMetadata:
    """Static tool metadata. ``operation_classes`` maps operation name →
    ``OperationClass`` — the declarative source the permission engine reads
    (requirement 5: "rules must be declarative"); an operation absent from
    this map is treated as the most conservative class (DANGEROUS) by the
    Runtime, never assumed safe."""

    version: str
    author: str
    tool_type: ToolType
    backing_system: str  # "graphify" | "agentdb" | "obsidian" | "github" | ...
    operation_classes: Mapping[str, OperationClass] = field(default_factory=dict)
    required_tools: tuple[str, ...] = ()
    required_mcps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolExecutionContext:
    """Standardized context every tool execution receives (requirement 6).

    Immutable, no globals. ``memory_context``/``workflow`` are typed only via
    ``TYPE_CHECKING`` — ``app.tools`` never imports ``app.memory``/
    ``app.workflow`` at runtime; a caller (an agent, or code above it) passes
    an already-built bundle in, this layer never fetches it itself.
    """

    trace_id: str
    agent_id: str | None
    workflow: WorkflowCategory | None
    caller: str
    started_at: float
    metadata: Mapping[str, str] = field(default_factory=dict)
    memory_context: ExecutionMemoryBundle | None = None
    tool_context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolRequest:
    """What ``ToolRuntime`` hands to ``Tool.execute()`` — the business-logic
    input, stripped of timing/retry/telemetry/permission concerns (mirrors
    ``AgentRequest``'s split, W3)."""

    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    context: ToolExecutionContext | None = None


@dataclass(frozen=True)
class ToolResponse:
    """What ``Tool.execute()`` returns — the adapter's own outcome, before the
    Runtime wraps it with timing/telemetry/retries/error-mapping."""

    success: bool
    output: Any = None
    error: str | None = None


@dataclass(frozen=True)
class ToolResult:
    """The Runtime's final, deterministic output (requirement 7). Telemetry
    fields are first-class DATA, not log-only — mirrors ``ExecutionResult``
    (W3) / ``DispatcherResult`` (W2) / ``MemoryResult`` (W4)'s "never raise"
    discipline, one more layer."""

    success: bool
    output: Any
    error: str | None
    error_type: str | None
    tool_id: str
    adapter: str  # ToolMetadata.backing_system
    operation: str
    duration_ms: float
    attempts: int
    trace_id: str
    permission_decision: PermissionDecision
