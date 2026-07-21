"""Tests for the Memory Service (ADR-013 W4, requirement 5/9/10/11).

Retrieval strategy selection, memory types, caching, telemetry, error
mapping, and fallback-provider resolution.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.memory.cache import MemoryCache
from app.memory.models import (
    MemoryHealthResult,
    MemoryHealthState,
    MemoryQuery,
    MemoryRecord,
    MemoryType,
    ProviderMetadata,
    RetrievalStrategy,
)
from app.memory.registry import MemoryRegistry
from app.memory.service import MemoryService


def _run(coro):
    return asyncio.run(coro)


@dataclass
class FakeProvider:
    id: str
    types: tuple[MemoryType, ...] = (MemoryType.KNOWLEDGE,)
    strategies: tuple[RetrievalStrategy, ...] = (RetrievalStrategy.EXACT,)
    behavior: str = "ok"  # ok | raise | not_found
    store_calls: list = field(default_factory=list)
    search_calls: list = field(default_factory=list)
    _data: dict = field(default_factory=dict)

    def supported_types(self):
        return self.types

    def supported_strategies(self):
        return self.strategies

    async def store(self, record: MemoryRecord) -> None:
        self.store_calls.append(record)
        if self.behavior == "raise":
            raise RuntimeError("store boom")
        self._data[record.key] = record

    async def retrieve(self, key, memory_type=None):
        if self.behavior == "raise":
            raise RuntimeError("retrieve boom")
        return self._data.get(key)

    async def search(self, query: MemoryQuery):
        self.search_calls.append(query)
        if self.behavior == "raise":
            raise RuntimeError("search boom")
        return tuple(self._data.values())[: query.limit]

    async def update(self, key, value, *, memory_type=None):
        if self.behavior == "raise":
            raise RuntimeError("update boom")
        self._data[key] = MemoryRecord(
            key=key, value=value, memory_type=memory_type or self.types[0]
        )

    async def delete(self, key, *, memory_type=None):
        if self.behavior == "raise":
            raise RuntimeError("delete boom")
        self._data.pop(key, None)

    async def exists(self, key, *, memory_type=None):
        if self.behavior == "raise":
            raise RuntimeError("exists boom")
        return key in self._data

    async def health(self) -> MemoryHealthResult:
        return MemoryHealthResult(MemoryHealthState.HEALTHY)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            version="1.0.0",
            author="test",
            supported_types=self.types,
            supported_strategies=self.strategies,
            backing_system="fake",
        )


def _svc(*providers, cache=None) -> MemoryService:
    reg = MemoryRegistry()
    for i, p in enumerate(providers):
        reg.register(p, priority=i * 10)
    return MemoryService(reg, cache=cache)


# ---- Basic store/retrieve ---------------------------------------------------


def test_store_and_retrieve():
    svc = _svc(FakeProvider(id="a"))
    record = MemoryRecord(key="k1", value="v1", memory_type=MemoryType.KNOWLEDGE)
    store_result = _run(svc.store(record, trace_id="t1"))
    assert store_result.success is True
    result = _run(svc.retrieve("k1", MemoryType.KNOWLEDGE, trace_id="t1"))
    assert result.success is True
    assert result.records[0].value == "v1"


def test_retrieve_missing_key_returns_empty_not_error():
    svc = _svc(FakeProvider(id="a"))
    result = _run(svc.retrieve("ghost", MemoryType.KNOWLEDGE, trace_id="t1"))
    assert result.success is True
    assert result.records == ()


# ---- Memory types (requirement 4) -----------------------------------------


def test_store_routes_by_memory_type_to_declaring_provider():
    repo_provider = FakeProvider(id="repo", types=(MemoryType.REPOSITORY,))
    know_provider = FakeProvider(id="know", types=(MemoryType.KNOWLEDGE,))
    svc = _svc(repo_provider, know_provider)
    _run(
        svc.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.REPOSITORY),
            trace_id="t",
        )
    )
    assert len(repo_provider.store_calls) == 1
    assert len(know_provider.store_calls) == 0


# ---- Retrieval strategies (requirement 5) ----------------------------------


def test_exact_key_query_always_uses_exact_strategy():
    provider = FakeProvider(
        id="a", strategies=(RetrievalStrategy.EXACT, RetrievalStrategy.HYBRID)
    )
    svc = _svc(provider)
    result = _run(svc.search(MemoryQuery(key="k1"), trace_id="t"))
    assert result.strategy_used is RetrievalStrategy.EXACT


def test_preferred_strategy_honored_when_supported():
    provider = FakeProvider(id="a", strategies=(RetrievalStrategy.SEMANTIC,))
    svc = _svc(provider)
    result = _run(
        svc.search(
            MemoryQuery(text="x", strategy=RetrievalStrategy.SEMANTIC), trace_id="t"
        )
    )
    assert result.strategy_used is RetrievalStrategy.SEMANTIC


def test_unsupported_strategy_downgrades_deterministically():
    """Provider doesn't support HYBRID (the query's ask) but supports EXACT —
    the fallback order picks EXACT deterministically."""
    provider = FakeProvider(id="a", strategies=(RetrievalStrategy.EXACT,))
    svc = _svc(provider)
    result = _run(
        svc.search(
            MemoryQuery(text="x", strategy=RetrievalStrategy.HYBRID), trace_id="t"
        )
    )
    assert result.strategy_used is RetrievalStrategy.EXACT
    assert result.success is True


def test_no_supported_strategy_at_all_is_unsupported_operation():
    provider = FakeProvider(id="a", strategies=())
    svc = _svc(provider)
    result = _run(svc.search(MemoryQuery(text="x"), trace_id="t"))
    assert result.success is False
    assert result.error_type == "UnsupportedOperation"


def test_agents_request_intent_provider_receives_reconciled_strategy():
    """Requirement 5: 'agents request intent, not implementation' — the
    provider's search() receives the Service's RESOLVED query, not the
    caller's raw preference."""
    provider = FakeProvider(id="a", strategies=(RetrievalStrategy.METADATA,))
    svc = _svc(provider)
    _run(
        svc.search(
            MemoryQuery(text="x", strategy=RetrievalStrategy.SEMANTIC), trace_id="t"
        )
    )
    assert provider.search_calls[0].strategy is RetrievalStrategy.METADATA


# ---- Caching (requirement 9) -----------------------------------------------


def test_retrieve_is_cached_on_second_call():
    provider = FakeProvider(id="a")
    svc = _svc(provider)
    _run(
        svc.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.KNOWLEDGE),
            trace_id="t",
        )
    )
    r1 = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    r2 = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert r1.cache_hit is False
    assert r2.cache_hit is True


def test_cache_can_be_bypassed_per_call():
    provider = FakeProvider(id="a")
    svc = _svc(provider)
    _run(
        svc.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.KNOWLEDGE),
            trace_id="t",
        )
    )
    _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    r2 = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t", use_cache=False))
    assert r2.cache_hit is False


def test_write_invalidates_the_cached_read():
    provider = FakeProvider(id="a")
    svc = _svc(provider)
    _run(
        svc.store(
            MemoryRecord(key="k", value="v1", memory_type=MemoryType.KNOWLEDGE),
            trace_id="t",
        )
    )
    _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))  # populates cache
    _run(svc.update("k", "v2", memory_type=MemoryType.KNOWLEDGE, trace_id="t"))
    r = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert r.cache_hit is False  # invalidated, re-fetched
    assert r.records[0].value == "v2"


def test_manual_cache_invalidation():
    cache = MemoryCache()
    provider = FakeProvider(id="a")
    svc = _svc(provider, cache=cache)
    _run(
        svc.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.KNOWLEDGE),
            trace_id="t",
        )
    )
    _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    cache.invalidate(cache.make_key("a", "retrieve", "k"))
    r = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert r.cache_hit is False


def test_provider_scoped_invalidation():
    cache = MemoryCache()
    cache.set("a::retrieve::k1", "v1")
    cache.set("a::search::k2", "v2")
    cache.set("b::retrieve::k3", "v3")
    cache.invalidate_provider("a")
    assert cache.get("a::retrieve::k1") is None
    assert cache.get("a::search::k2") is None
    assert cache.get("b::retrieve::k3") == "v3"


def test_cache_ttl_expiry():
    cache = MemoryCache(default_ttl_s=0.01)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    import time

    time.sleep(0.02)
    assert cache.get("k") is None


def test_cache_statistics():
    cache = MemoryCache()
    cache.set("k", "v")
    cache.get("k")  # hit
    cache.get("k")  # hit
    cache.get("ghost")  # miss
    stats = cache.stats()
    assert stats.hits == 2
    assert stats.misses == 1
    assert stats.size == 1
    assert 0.6 < stats.hit_rate < 0.7


# ---- Telemetry (requirement 10) --------------------------------------------


def test_telemetry_log_line_has_required_fields(caplog):
    provider = FakeProvider(id="a")
    svc = _svc(provider)
    with caplog.at_level("DEBUG", logger="app.memory.service"):
        _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="trace-99"))
    line = next(r.getMessage() for r in caplog.records if "memory-op" in r.getMessage())
    assert "trace_id=trace-99" in line
    assert "provider=a" in line
    assert "operation=retrieve" in line
    assert "cache_hit=False" in line
    assert "result_count=0" in line


def test_telemetry_reflects_cache_hit(caplog):
    provider = FakeProvider(id="a")
    svc = _svc(provider)
    _run(
        svc.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.KNOWLEDGE),
            trace_id="t",
        )
    )
    _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    with caplog.at_level("DEBUG", logger="app.memory.service"):
        _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    line = next(r.getMessage() for r in caplog.records if "memory-op" in r.getMessage())
    assert "cache_hit=True" in line


# ---- Error mapping (requirement 11) ----------------------------------------


def test_raised_exception_is_mapped_never_raw():
    provider = FakeProvider(id="a", behavior="raise")
    svc = _svc(provider)
    result = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert result.success is False
    assert result.error_type == "QueryFailure"
    assert "retrieve boom" in result.error


def test_no_provider_resolved_is_provider_unavailable():
    svc = _svc()  # empty registry
    result = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert result.error_type == "ProviderUnavailable"


def test_write_op_errors_are_mapped_too():
    provider = FakeProvider(id="a", behavior="raise")
    svc = _svc(provider)
    result = _run(
        svc.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.KNOWLEDGE),
            trace_id="t",
        )
    )
    assert result.success is False
    assert result.error_type == "QueryFailure"


def test_service_never_raises_a_raw_exception():
    """The whole point of requirement 11: an exploding provider must never
    propagate as a Python exception out of the Service."""
    provider = FakeProvider(id="a", behavior="raise")
    svc = _svc(provider)
    # No try/except needed here — if this raises, the test itself fails loudly.
    _run(svc.search(MemoryQuery(text="x"), trace_id="t"))
    _run(svc.update("k", "v", memory_type=MemoryType.KNOWLEDGE, trace_id="t"))
    _run(svc.delete("k", memory_type=MemoryType.KNOWLEDGE, trace_id="t"))
    _run(svc.exists("k", memory_type=MemoryType.KNOWLEDGE, trace_id="t"))


def test_typed_memory_error_raised_by_provider_passes_through_unchanged():
    from app.memory.errors import PermissionDenied

    @dataclass
    class DeniedProvider(FakeProvider):
        async def retrieve(self, key, memory_type=None):
            raise PermissionDenied("not authorized")

    svc = _svc(DeniedProvider(id="a"))
    result = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert result.error_type == "PermissionDenied"


# ---- Provider resolution / explicit provider_id + fallback -----------------


def test_explicit_provider_id_overrides_type_based_resolution():
    p1 = FakeProvider(id="p1", types=(MemoryType.KNOWLEDGE,))
    p2 = FakeProvider(id="p2", types=(MemoryType.KNOWLEDGE,))
    svc = _svc(p1, p2)
    result = _run(
        svc.retrieve("k", MemoryType.KNOWLEDGE, provider_id="p2", trace_id="t")
    )
    assert result.provider_used == "p2"


def test_falls_back_to_default_provider_when_no_type_declares_it():
    default = FakeProvider(id="default", types=(MemoryType.CACHE,))
    svc = _svc(default)
    result = _run(
        svc.retrieve("k", MemoryType.RESEARCH, trace_id="t")
    )  # nothing declares RESEARCH
    assert result.provider_used == "default"


def test_highest_priority_provider_wins_among_multiple_declaring_the_type():
    low = FakeProvider(id="low", types=(MemoryType.KNOWLEDGE,))
    high = FakeProvider(id="high", types=(MemoryType.KNOWLEDGE,))
    reg = MemoryRegistry()
    reg.register(low, priority=99)
    reg.register(high, priority=1)
    svc = MemoryService(reg)
    result = _run(svc.retrieve("k", MemoryType.KNOWLEDGE, trace_id="t"))
    assert result.provider_used == "high"
