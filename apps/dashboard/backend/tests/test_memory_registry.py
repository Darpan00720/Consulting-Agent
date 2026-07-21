"""Tests for the Memory Registry (ADR-013 W4, requirement 3).

Registration, duplicate detection, removal, lookup, capability (type)
lookup, health, priority, default provider, and dynamic provider registration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.memory.models import (
    MemoryHealthResult,
    MemoryHealthState,
    MemoryType,
    ProviderMetadata,
    RetrievalStrategy,
)
from app.memory.registry import (
    DuplicateProviderError,
    MemoryRegistry,
    UnknownProviderError,
)


@dataclass
class StubProvider:
    id: str
    name: str = "Stub"
    version: str = "1.0.0"
    types: tuple[MemoryType, ...] = (MemoryType.KNOWLEDGE,)
    strategies: tuple[RetrievalStrategy, ...] = (RetrievalStrategy.EXACT,)
    health_state: MemoryHealthState = MemoryHealthState.HEALTHY

    def supported_types(self):
        return self.types

    def supported_strategies(self):
        return self.strategies

    async def store(self, record):
        pass

    async def retrieve(self, key, memory_type=None):
        return None

    async def search(self, query):
        return ()

    async def update(self, key, value, *, memory_type=None):
        pass

    async def delete(self, key, *, memory_type=None):
        pass

    async def exists(self, key, *, memory_type=None):
        return False

    async def health(self) -> MemoryHealthResult:
        return MemoryHealthResult(self.health_state)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            version=self.version,
            author="test",
            supported_types=self.types,
            supported_strategies=self.strategies,
            backing_system="stub",
        )


def _run(coro):
    return asyncio.run(coro)


# ---- Registration -----------------------------------------------------------


def test_register_and_get():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    assert reg.get("a").id == "a"


def test_duplicate_registration_raises():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    try:
        reg.register(StubProvider(id="a"))
        raise AssertionError("expected DuplicateProviderError")
    except DuplicateProviderError:
        pass


def test_duplicate_registration_allowed_with_replace():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a", name="v1"))
    reg.register(StubProvider(id="a", name="v2"), replace=True)
    assert reg.get("a").name == "v2"


def test_dynamic_provider_registration_after_startup():
    """A provider registered LATER (not at construction time) is immediately
    discoverable — no restart, no code change (requirement 3/12)."""
    reg = MemoryRegistry()
    reg.register(StubProvider(id="early"))
    assert {p.id for p in reg.discover()} == {"early"}
    reg.register(StubProvider(id="late"))
    assert {p.id for p in reg.discover()} == {"early", "late"}


# ---- Removal ------------------------------------------------------------


def test_provider_removal():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    reg.remove("a")
    assert reg.get("a") is None
    assert reg.discover() == ()


def test_removal_of_default_falls_back_to_next_priority():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"), priority=10, default=True)
    reg.register(StubProvider(id="b"), priority=20)
    reg.remove("a")
    assert reg.default_provider().id == "b"


def test_removal_of_only_provider_clears_default():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    reg.remove("a")
    assert reg.default_provider() is None


def test_removing_unknown_provider_is_a_noop():
    reg = MemoryRegistry()
    reg.remove("ghost")  # must not raise


# ---- Lookup / capability search --------------------------------------------


def test_lookup_unknown_provider_returns_none():
    reg = MemoryRegistry()
    assert reg.get("ghost") is None


def test_capability_lookup_by_memory_type():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="repo", types=(MemoryType.REPOSITORY,)))
    reg.register(StubProvider(id="know", types=(MemoryType.KNOWLEDGE,)))
    found = reg.find_by_type(MemoryType.REPOSITORY)
    assert [p.id for p in found] == ["repo"]


def test_capability_lookup_respects_priority_order():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="slow", types=(MemoryType.KNOWLEDGE,)), priority=50)
    reg.register(StubProvider(id="fast", types=(MemoryType.KNOWLEDGE,)), priority=10)
    found = reg.find_by_type(MemoryType.KNOWLEDGE)
    assert [p.id for p in found] == ["fast", "slow"]


# ---- Priority + default provider -------------------------------------------


def test_first_registered_becomes_default():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    reg.register(StubProvider(id="b"))
    assert reg.default_provider().id == "a"


def test_explicit_default_registration():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    reg.register(StubProvider(id="b"), default=True)
    assert reg.default_provider().id == "b"


def test_set_default_explicitly():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"))
    reg.register(StubProvider(id="b"))
    reg.set_default("b")
    assert reg.default_provider().id == "b"


def test_set_default_to_unknown_raises():
    reg = MemoryRegistry()
    try:
        reg.set_default("ghost")
        raise AssertionError("expected UnknownProviderError")
    except UnknownProviderError:
        pass


def test_priority_ordering():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="c"), priority=30)
    reg.register(StubProvider(id="a"), priority=10)
    reg.register(StubProvider(id="b"), priority=20)
    assert [p.id for p in reg.providers_by_priority()] == ["a", "b", "c"]


def test_set_priority_changes_ordering():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a"), priority=10)
    reg.register(StubProvider(id="b"), priority=20)
    reg.set_priority("a", 99)
    assert [p.id for p in reg.providers_by_priority()] == ["b", "a"]


def test_set_priority_on_unknown_raises():
    reg = MemoryRegistry()
    try:
        reg.set_priority("ghost", 1)
        raise AssertionError("expected UnknownProviderError")
    except UnknownProviderError:
        pass


# ---- Health -------------------------------------------------------------


def test_health_query_through_registry():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a", health_state=MemoryHealthState.DEGRADED))
    result = _run(reg.health("a"))
    assert result.state is MemoryHealthState.DEGRADED


def test_health_probe_exception_is_unavailable_not_a_crash():
    @dataclass
    class BrokenHealthProvider(StubProvider):
        async def health(self):
            raise RuntimeError("probe boom")

    reg = MemoryRegistry()
    reg.register(BrokenHealthProvider(id="broken"))
    result = _run(reg.health("broken"))  # must not raise
    assert result.state is MemoryHealthState.UNAVAILABLE
    assert "probe boom" in result.detail


def test_health_of_unregistered_provider_is_unknown():
    reg = MemoryRegistry()
    result = _run(reg.health("ghost"))
    assert result.state is MemoryHealthState.UNKNOWN


def test_last_health_is_cached_after_query():
    reg = MemoryRegistry()
    reg.register(StubProvider(id="a", health_state=MemoryHealthState.HEALTHY))
    assert reg.last_health("a") is None
    _run(reg.health("a"))
    assert reg.last_health("a").state is MemoryHealthState.HEALTHY
