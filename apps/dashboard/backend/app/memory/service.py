"""Memory Service (requirement 5/6/9/10/11) — the orchestration layer.

Resolves WHICH provider serves a call (explicit id → registry priority for the
query's memory type → registry default), decides the retrieval STRATEGY
(requirement 5 — "agents request intent, not implementation"), wraps every
call with caching (requirement 9) and telemetry (requirement 10), and maps
every failure into the typed error model (requirement 11) — a raw provider
exception never escapes this Service, the same discipline
``AgentRuntime``/``Dispatcher``/``Workflow Router`` already commit to, one more
layer down.

Deliberately imports nothing from ``app.agents``/``app.workflow`` at runtime —
this is the lower layer; ``app.agents`` builds an ``ExecutionMemoryBundle`` by
calling INTO this Service (opt-in, additive — see ``app.agents.runtime``).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.memory.cache import MemoryCache
from app.memory.errors import MemoryError, ProviderUnavailable, UnsupportedOperation
from app.memory.models import (
    MemoryOperationResult,
    MemoryQuery,
    MemoryRecord,
    MemoryResult,
    MemoryType,
    RetrievalStrategy,
)
from app.memory.provider import MemoryProvider
from app.memory.registry import MemoryRegistry

log = logging.getLogger(__name__)

# Deterministic downgrade order when a query's preferred strategy isn't
# supported by the resolved provider (requirement 5) — the same
# "fixed-priority-table" tie-break discipline used everywhere else in this
# program (ADR-012's category priority, W1's classification tie-break).
_STRATEGY_FALLBACK_ORDER: tuple[RetrievalStrategy, ...] = (
    RetrievalStrategy.HYBRID,
    RetrievalStrategy.SEMANTIC,
    RetrievalStrategy.METADATA,
    RetrievalStrategy.EXACT,
    RetrievalStrategy.PROVIDER_NATIVE,
)


class MemoryService:
    """The single entry point agents/Runtime use for memory. Stateless beyond
    its registry + cache — safe to share one instance (``default_service()``)."""

    def __init__(
        self, registry: MemoryRegistry, cache: MemoryCache | None = None
    ) -> None:
        self.registry = registry
        self.cache = cache or MemoryCache()

    # ---- provider resolution --------------------------------------------

    def _resolve_provider(
        self, memory_type: MemoryType | None, provider_id: str | None
    ) -> MemoryProvider | None:
        if provider_id is not None:
            return self.registry.get(provider_id)
        if memory_type is not None:
            candidates = self.registry.find_by_type(memory_type)
            if candidates:
                return candidates[0]  # highest priority declaring this type
        return self.registry.default_provider()

    def _resolve_strategy(
        self, query: MemoryQuery, provider: MemoryProvider
    ) -> RetrievalStrategy | None:
        """Requirement 5: the Service chooses, never the agent. An exact-key
        query is unambiguous — always EXACT. Otherwise honor the query's
        preferred strategy if the provider supports it; deterministically
        downgrade through ``_STRATEGY_FALLBACK_ORDER`` otherwise. Returns
        ``None`` only if the provider supports NOTHING in that order."""
        if query.key is not None:
            return (
                RetrievalStrategy.EXACT
                if RetrievalStrategy.EXACT in provider.supported_strategies()
                else None
            )
        supported = provider.supported_strategies()
        if query.strategy in supported:
            return query.strategy
        for candidate in _STRATEGY_FALLBACK_ORDER:
            if candidate in supported:
                return candidate
        return None

    # ---- store / update / delete / exists (write-ish ops) --------------

    async def store(
        self,
        record: MemoryRecord,
        *,
        provider_id: str | None = None,
        trace_id: str = "",
    ) -> MemoryOperationResult:
        return await self._write_op(
            "store",
            record.memory_type,
            provider_id,
            trace_id,
            lambda p: p.store(record),
            invalidate_key=record.key,
        )

    async def update(
        self,
        key: str,
        value: Any,
        *,
        memory_type: MemoryType | None = None,
        provider_id: str | None = None,
        trace_id: str = "",
    ) -> MemoryOperationResult:
        return await self._write_op(
            "update",
            memory_type,
            provider_id,
            trace_id,
            lambda p: p.update(key, value, memory_type=memory_type),
            invalidate_key=key,
        )

    async def delete(
        self,
        key: str,
        *,
        memory_type: MemoryType | None = None,
        provider_id: str | None = None,
        trace_id: str = "",
    ) -> MemoryOperationResult:
        return await self._write_op(
            "delete",
            memory_type,
            provider_id,
            trace_id,
            lambda p: p.delete(key, memory_type=memory_type),
            invalidate_key=key,
        )

    async def exists(
        self,
        key: str,
        *,
        memory_type: MemoryType | None = None,
        provider_id: str | None = None,
        trace_id: str = "",
    ) -> MemoryOperationResult:
        start = time.monotonic()
        provider = self._resolve_provider(memory_type, provider_id)
        if provider is None:
            return self._op_error(
                start,
                None,
                trace_id,
                ProviderUnavailable("no provider resolved"),
                "exists",
            )
        try:
            found = await provider.exists(key, memory_type=memory_type)
        except Exception as exc:  # noqa: BLE001 — never let a raw exception escape
            return self._op_error(
                start, provider.id, trace_id, _map_error(exc), "exists"
            )
        result = MemoryOperationResult(
            success=True,
            provider_used=provider.id,
            duration_ms=(time.monotonic() - start) * 1000,
            trace_id=trace_id,
            exists=found,
        )
        _log_operation(
            "exists", result, cache_hit=False, result_count=1 if found else 0
        )
        return result

    async def _write_op(
        self,
        operation: str,
        memory_type: MemoryType | None,
        provider_id: str | None,
        trace_id: str,
        call,
        *,
        invalidate_key: str,
    ) -> MemoryOperationResult:
        start = time.monotonic()
        provider = self._resolve_provider(memory_type, provider_id)
        if provider is None:
            return self._op_error(
                start,
                None,
                trace_id,
                ProviderUnavailable("no provider resolved"),
                operation,
            )
        try:
            await call(provider)
        except Exception as exc:  # noqa: BLE001 — never let a raw exception escape
            return self._op_error(
                start, provider.id, trace_id, _map_error(exc), operation
            )
        # A write must not serve a stale cached read afterwards.
        for op in ("retrieve", "search"):
            self.cache.invalidate(self.cache.make_key(provider.id, op, invalidate_key))
        result = MemoryOperationResult(
            success=True,
            provider_used=provider.id,
            duration_ms=(time.monotonic() - start) * 1000,
            trace_id=trace_id,
        )
        _log_operation(operation, result, cache_hit=False, result_count=1)
        return result

    def _op_error(
        self,
        start: float,
        provider_id: str | None,
        trace_id: str,
        error: MemoryError,
        operation: str,
    ) -> MemoryOperationResult:
        result = MemoryOperationResult(
            success=False,
            provider_used=provider_id,
            duration_ms=(time.monotonic() - start) * 1000,
            trace_id=trace_id,
            error=str(error),
            error_type=type(error).__name__,
        )
        _log_operation(operation, result, cache_hit=False, result_count=0)
        return result

    # ---- retrieve / search (read ops, cached) --------------------------

    async def retrieve(
        self,
        key: str,
        memory_type: MemoryType | None = None,
        *,
        provider_id: str | None = None,
        trace_id: str = "",
        use_cache: bool = True,
        ttl_s: float | None = None,
    ) -> MemoryResult:
        start = time.monotonic()
        provider = self._resolve_provider(memory_type, provider_id)
        if provider is None:
            return self._result_error(
                start, None, None, trace_id, ProviderUnavailable("no provider resolved")
            )

        cache_key = self.cache.make_key(provider.id, "retrieve", key)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                result = MemoryResult(
                    records=(cached,) if cached is not None else (),
                    provider_used=provider.id,
                    strategy_used=RetrievalStrategy.EXACT,
                    cache_hit=True,
                    duration_ms=(time.monotonic() - start) * 1000,
                    trace_id=trace_id,
                )
                _log_operation(
                    "retrieve", result, cache_hit=True, result_count=len(result.records)
                )
                return result

        try:
            record = await provider.retrieve(key, memory_type)
        except Exception as exc:  # noqa: BLE001 — never let a raw exception escape
            return self._result_error(
                start, provider.id, None, trace_id, _map_error(exc)
            )

        records = (record,) if record is not None else ()
        if use_cache and record is not None:
            self.cache.set(cache_key, record, ttl_s)
        result = MemoryResult(
            records=records,
            provider_used=provider.id,
            strategy_used=RetrievalStrategy.EXACT,
            cache_hit=False,
            duration_ms=(time.monotonic() - start) * 1000,
            trace_id=trace_id,
        )
        _log_operation("retrieve", result, cache_hit=False, result_count=len(records))
        return result

    async def search(
        self,
        query: MemoryQuery,
        *,
        provider_id: str | None = None,
        trace_id: str = "",
        use_cache: bool = True,
        ttl_s: float | None = None,
    ) -> MemoryResult:
        start = time.monotonic()
        provider = self._resolve_provider(query.memory_type, provider_id)
        if provider is None:
            return self._result_error(
                start, None, None, trace_id, ProviderUnavailable("no provider resolved")
            )

        strategy = self._resolve_strategy(query, provider)
        if strategy is None:
            return self._result_error(
                start,
                provider.id,
                None,
                trace_id,
                UnsupportedOperation(
                    f"{provider.id} supports none of the requested/fallback strategies"
                ),
            )

        cache_key = self.cache.make_key(
            provider.id, "search", _query_cache_fingerprint(query, strategy)
        )
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                result = MemoryResult(
                    records=cached,
                    provider_used=provider.id,
                    strategy_used=strategy,
                    cache_hit=True,
                    duration_ms=(time.monotonic() - start) * 1000,
                    trace_id=trace_id,
                )
                _log_operation(
                    "search", result, cache_hit=True, result_count=len(cached)
                )
                return result

        resolved_query = (
            query if query.strategy == strategy else _with_strategy(query, strategy)
        )
        try:
            records = await provider.search(resolved_query)
        except Exception as exc:  # noqa: BLE001 — never let a raw exception escape
            return self._result_error(
                start, provider.id, strategy, trace_id, _map_error(exc)
            )

        if use_cache:
            self.cache.set(cache_key, records, ttl_s)
        result = MemoryResult(
            records=records,
            provider_used=provider.id,
            strategy_used=strategy,
            cache_hit=False,
            duration_ms=(time.monotonic() - start) * 1000,
            trace_id=trace_id,
        )
        _log_operation("search", result, cache_hit=False, result_count=len(records))
        return result

    def _result_error(
        self,
        start: float,
        provider_id: str | None,
        strategy: RetrievalStrategy | None,
        trace_id: str,
        error: MemoryError,
    ) -> MemoryResult:
        result = MemoryResult(
            records=(),
            provider_used=provider_id,
            strategy_used=strategy,
            cache_hit=False,
            duration_ms=(time.monotonic() - start) * 1000,
            trace_id=trace_id,
            error=str(error),
            error_type=type(error).__name__,
        )
        _log_operation("search", result, cache_hit=False, result_count=0)
        return result


def _with_strategy(query: MemoryQuery, strategy: RetrievalStrategy) -> MemoryQuery:
    from dataclasses import replace

    return replace(query, strategy=strategy)


def _query_cache_fingerprint(query: MemoryQuery, strategy: RetrievalStrategy) -> str:
    """A cache key MUST uniquely identify every field that affects the
    result. Bug caught by test (W4): the original key used only
    ``strategy:text:limit`` — two queries differing solely in ``memory_type``
    or ``metadata_filter`` (e.g. the Runtime's session vs. execution memory
    fetches, same empty text/limit) collided and returned each other's
    results. Every field ``MemoryQuery`` carries that a provider's ``search``
    can act on is included here."""
    memory_type = query.memory_type.value if query.memory_type else ""
    filters = ",".join(f"{k}={v}" for k, v in sorted(query.metadata_filter.items()))
    key = query.key or ""
    return f"{strategy.value}:{memory_type}:{query.text}:{query.limit}:{filters}:{key}"


def _map_error(exc: Exception) -> MemoryError:
    """Map an arbitrary raised exception into the typed error model
    (requirement 11) — a provider that already raises a typed MemoryError
    passes through unchanged; anything else becomes a QueryFailure."""
    if isinstance(exc, MemoryError):
        return exc
    from app.memory.errors import QueryFailure

    return QueryFailure(f"{type(exc).__name__}: {exc}")


def _log_operation(
    operation: str,
    result: MemoryResult | MemoryOperationResult,
    *,
    cache_hit: bool,
    result_count: int,
) -> None:
    """One telemetry line per operation (requirement 10): provider, operation,
    latency, cache hit/miss, result count, trace_id. ``trace_id`` is always the
    caller-supplied one — never invented — so this correlates with Runtime/
    Dispatcher/Router telemetry without a shared global (requirement 10's "no
    duplicated telemetry")."""
    log.debug(
        "memory-op trace_id=%s provider=%s operation=%s duration_ms=%.1f "
        "cache_hit=%s result_count=%d success=%s error_type=%s",
        result.trace_id,
        result.provider_used,
        operation,
        result.duration_ms,
        cache_hit,
        result_count,
        result.success,
        result.error_type,
    )


_service: MemoryService | None = None


def default_service() -> MemoryService:
    """Lazy singleton over the built-in registry (mirrors
    ``app.agents.runtime.default_runtime()``)."""
    global _service
    if _service is None:
        from app.memory.adapters import default_memory_registry

        _service = MemoryService(default_memory_registry())
    return _service


def reset_service() -> None:
    """Rebuild on next use (tests) — mirrors ``providers.reset_chain()``."""
    global _service
    _service = None
