"""Core data types for the Memory Platform (ADR-013 W4).

Memory types, retrieval strategies, records/queries/results, provider
metadata, health, and the execution-context memory bundle — plain, frozen
dataclasses/enums, no behavior. Dependency-free of ``app.agents``/
``app.workflow`` at runtime, so this stays the lower layer other packages
build on, never the reverse (same discipline as ``app.agents.models``, W3).
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MemoryType(StrEnum):
    """Distinct memory classes (requirement 4). Each provider declares which
    it supports via ``ProviderMetadata.supported_types``."""

    CONVERSATION = "conversation"
    SESSION = "session"
    EXECUTION = "execution"
    KNOWLEDGE = "knowledge"
    PROJECT = "project"
    REPOSITORY = "repository"
    CONSULTING = "consulting"
    RESEARCH = "research"
    CACHE = "cache"


class RetrievalStrategy(StrEnum):
    """How a query is resolved (requirement 5). Callers state an ``intent``
    (a preferred strategy); the Service — never the agent — reconciles it
    against what the chosen provider actually supports."""

    EXACT = "exact"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    METADATA = "metadata"
    PROVIDER_NATIVE = "provider-native"


class MemoryHealthState(StrEnum):
    """Health probe results — same 4-value shape as
    ``app.agents.models.HealthState``, deliberately redefined rather than
    imported (keeps ``app.memory`` dependency-free of ``app.agents``, the same
    duplication-over-coupling call W3 made for ``CancellationToken``)."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MemoryHealthResult:
    state: MemoryHealthState
    detail: str = ""
    checked_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class MemoryRecord:
    """One stored/retrieved unit of memory."""

    key: str
    value: Any  # JSON-serializable payload; adapters own their own encoding
    memory_type: MemoryType
    metadata: Mapping[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float | None = None
    provider: str | None = None  # which provider served/stored it (Service fills this)
    score: float | None = None  # relevance score for search results, if applicable


@dataclass(frozen=True)
class MemoryQuery:
    """What a caller asks for — INTENT, not implementation (requirement 5).

    ``strategy`` is a preference, not a command: ``MemoryService`` reconciles
    it against the resolved provider's declared capabilities and may
    deterministically downgrade it (never silently invents a different one
    without recording that it did — see ``MemoryResult.strategy_used``).
    """

    text: str = ""
    memory_type: MemoryType | None = None
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    limit: int = 10
    metadata_filter: Mapping[str, str] = field(default_factory=dict)
    key: str | None = None  # set => an exact-key lookup, overrides strategy


@dataclass(frozen=True)
class ProviderMetadata:
    """Static provider metadata (mirrors ``app.agents.models.AgentMetadata``'s
    shape/spirit for the memory domain)."""

    version: str
    author: str
    supported_types: tuple[MemoryType, ...]
    supported_strategies: tuple[RetrievalStrategy, ...]
    backing_system: str  # "graphify" | "agentdb" | "sqlite-events" | ...
    read_only: bool = False


@dataclass(frozen=True)
class MemoryResult:
    """What ``MemoryService.retrieve``/``search`` return. Telemetry fields are
    first-class DATA (requirement 10), and errors are REPORTED here, never
    raised (requirement 11) — mirrors ``ExecutionResult`` (W3) and
    ``DispatcherResult`` (W2)'s "never raise" discipline, one more layer down.
    """

    records: tuple[MemoryRecord, ...]
    provider_used: str | None
    strategy_used: RetrievalStrategy | None
    cache_hit: bool
    duration_ms: float
    trace_id: str
    error: str | None = None
    error_type: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class MemoryOperationResult:
    """What ``store``/``update``/``delete``/``exists`` return — leaner than
    ``MemoryResult`` (no records/strategy), same "never raise" discipline."""

    success: bool
    provider_used: str | None
    duration_ms: float
    trace_id: str
    error: str | None = None
    error_type: str | None = None
    exists: bool | None = None  # populated only by `exists()`


@dataclass(frozen=True)
class CacheStats:
    """Cache statistics (requirement 9)."""

    hits: int
    misses: int
    size: int

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


@dataclass(frozen=True)
class ExecutionMemoryBundle:
    """What the Agent Runtime injects into ``ExecutionContext`` (requirement
    6): session / execution / project / long-term memory. Immutable, built
    fresh per execution — never a global."""

    session: tuple[MemoryRecord, ...] = ()
    execution: tuple[MemoryRecord, ...] = ()
    project: tuple[MemoryRecord, ...] = ()
    long_term: tuple[MemoryRecord, ...] = ()
