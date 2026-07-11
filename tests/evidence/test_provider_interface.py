"""Provider interface / registry / cache tests (RC1.2, WI-4 / ADR-007).

Exercises the extension mechanism with fake providers — the package ships no
real providers, so tests supply their own.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

import pytest

from evidence import (
    EvidenceProvider,
    EvidenceProviderError,
    FetchOutcome,
    ProviderCache,
    ProviderQuery,
    ProviderRegistry,
    ProviderResult,
    ProviderStatus,
    cache_key,
)
from evidence.errors import ProviderConfigError

# ---------------------------------------------------------------------------
# Fake providers (test-only)
# ---------------------------------------------------------------------------


class _HealthyProvider:
    def __init__(self, pid: str = "healthy", n: int = 2) -> None:
        self._pid = pid
        self._n = n
        self.fetch_calls = 0
        self.started = False
        self.closed = False

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def name(self) -> str:
        return f"Healthy {self._pid}"

    def startup(self) -> None:
        self.started = True

    def health(self) -> ProviderStatus:
        return ProviderStatus.READY

    def fetch(self, query: ProviderQuery) -> Sequence[ProviderResult]:
        self.fetch_calls += 1
        return [
            ProviderResult(
                claim=f"{query.text} datum {i}",
                source=f"src://{self._pid}/{i}",
                confidence=0.7,
                provider_id=self._pid,
            )
            for i in range(self._n)
        ]

    def shutdown(self) -> None:
        self.closed = True


class _FailingProvider:
    provider_id = "boom"
    name = "Failing"

    def startup(self) -> None:  # noqa: D401
        return None

    def health(self) -> ProviderStatus:
        return ProviderStatus.READY

    def fetch(self, query: ProviderQuery) -> Sequence[ProviderResult]:
        raise EvidenceProviderError("provider exploded")

    def shutdown(self) -> None:
        return None


class _SlowProvider:
    provider_id = "slow"
    name = "Slow"

    def __init__(self, delay: float = 0.2) -> None:
        self._delay = delay

    def startup(self) -> None:
        return None

    def health(self) -> ProviderStatus:
        return ProviderStatus.READY

    def fetch(self, query: ProviderQuery) -> Sequence[ProviderResult]:
        time.sleep(self._delay)
        return []

    def shutdown(self) -> None:
        return None


class _MislabeledProvider:
    """Returns results whose provider_id does not match — registry must stamp."""

    provider_id = "canonical"
    name = "Mislabeled"

    def startup(self) -> None:
        return None

    def health(self) -> ProviderStatus:
        return ProviderStatus.READY

    def fetch(self, query: ProviderQuery) -> Sequence[ProviderResult]:
        return [
            ProviderResult(claim="x", source="s", confidence=0.5, provider_id="WRONG")
        ]

    def shutdown(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(_HealthyProvider(), EvidenceProvider)


def test_provider_result_requires_source_field() -> None:
    r = ProviderResult(claim="c", source="s", confidence=0.9, provider_id="p")
    assert r.source == "s"  # mandatory citation present


# ---------------------------------------------------------------------------
# Registration & lifecycle
# ---------------------------------------------------------------------------


def test_register_and_order() -> None:
    reg = ProviderRegistry()
    reg.register(_HealthyProvider("a"))
    reg.register(_HealthyProvider("b"))
    assert reg.providers() == ("a", "b")


def test_duplicate_registration_raises() -> None:
    reg = ProviderRegistry()
    reg.register(_HealthyProvider("dup"))
    with pytest.raises(EvidenceProviderError):
        reg.register(_HealthyProvider("dup"))


def test_startup_sets_status_from_health() -> None:
    reg = ProviderRegistry()
    p = _HealthyProvider()
    reg.register(p)
    reg.startup()
    assert p.started is True
    assert reg.health()["healthy"] == ProviderStatus.READY


def test_shutdown_closes_all() -> None:
    reg = ProviderRegistry()
    p = _HealthyProvider()
    reg.register(p)
    reg.startup()
    reg.shutdown()
    assert p.closed is True
    assert reg.health()["healthy"] == ProviderStatus.CLOSED


def test_startup_failure_marks_unavailable_not_raises() -> None:
    class _BadStartup(_HealthyProvider):
        def startup(self) -> None:
            raise ProviderConfigError("no credentials")

    reg = ProviderRegistry()
    reg.register(_BadStartup("bad"))
    reg.startup()  # must not raise
    assert reg.health()["bad"] == ProviderStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Fetch: merging, traceability, isolation, timeout
# ---------------------------------------------------------------------------


def test_fetch_merges_and_stamps_results() -> None:
    reg = ProviderRegistry()
    reg.register(_HealthyProvider("a", n=2))
    reg.register(_HealthyProvider("b", n=1))
    out = reg.fetch(ProviderQuery(text="q"))
    assert isinstance(out, FetchOutcome)
    assert len(out.results) == 3
    assert {r.provider_id for r in out.results} == {"a", "b"}
    assert out.ok


def test_mislabeled_result_is_restamped() -> None:
    reg = ProviderRegistry()
    reg.register(_MislabeledProvider())
    out = reg.fetch(ProviderQuery(text="q"))
    assert out.results[0].provider_id == "canonical"  # not "WRONG"


def test_failing_provider_is_isolated() -> None:
    reg = ProviderRegistry()
    reg.register(_HealthyProvider("good", n=1))
    reg.register(_FailingProvider())
    out = reg.fetch(ProviderQuery(text="q"))
    assert len(out.results) == 1  # healthy result survives
    assert out.results[0].provider_id == "good"
    assert "boom" in out.errors
    assert not out.ok
    assert reg.health()["boom"] == ProviderStatus.DEGRADED


def test_slow_provider_times_out_and_is_isolated() -> None:
    reg = ProviderRegistry(timeout_seconds=0.05)
    reg.register(_HealthyProvider("good", n=1))
    reg.register(_SlowProvider(delay=0.2))
    out = reg.fetch(ProviderQuery(text="q"))
    assert len(out.results) == 1
    assert "slow" in out.errors
    assert "budget" in out.errors["slow"]
    assert reg.health()["slow"] == ProviderStatus.DEGRADED


def test_unknown_provider_id_in_targets_raises() -> None:
    reg = ProviderRegistry()
    reg.register(_HealthyProvider("a"))
    with pytest.raises(EvidenceProviderError):
        reg.fetch(ProviderQuery(text="q"), provider_ids=["a", "missing"])


def test_empty_registry_returns_no_results() -> None:
    reg = ProviderRegistry()
    out = reg.fetch(ProviderQuery(text="q"))
    assert out.results == ()
    assert out.ok


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic() -> None:
    q = ProviderQuery(text="hello", archetype="market-entry", filters={"a": "1"})
    assert cache_key("p", q) == cache_key("p", q)
    assert cache_key("p", q) != cache_key("other", q)


def test_cache_avoids_second_provider_call() -> None:
    reg = ProviderRegistry(cache=ProviderCache())
    p = _HealthyProvider("a", n=1)
    reg.register(p)
    q = ProviderQuery(text="q")
    first = reg.fetch(q)
    second = reg.fetch(q)
    assert p.fetch_calls == 1  # served from cache the second time
    assert "a" in second.from_cache
    assert first.results == second.results


def test_cache_ttl_expiry_with_injected_clock() -> None:
    clock = {"t": 1000.0}
    cache = ProviderCache(ttl_seconds=10.0, clock=lambda: clock["t"])
    result = ProviderResult(claim="c", source="s", confidence=0.5, provider_id="p")
    cache.set("k", (result,))
    assert cache.get("k") is not None
    clock["t"] = 1011.0  # advance past TTL
    assert cache.get("k") is None


def test_cache_eviction_when_full() -> None:
    cache = ProviderCache(max_entries=2)
    r = (ProviderResult(claim="c", source="s", confidence=0.5, provider_id="p"),)
    cache.set("k1", r)
    cache.set("k2", r)
    cache.set("k3", r)  # evicts oldest (k1)
    assert cache.get("k1") is None
    assert cache.get("k3") is not None
    assert len(cache) == 2


def test_cache_invalid_config_raises() -> None:
    with pytest.raises(ValueError):
        ProviderCache(ttl_seconds=0)
    with pytest.raises(ValueError):
        ProviderCache(max_entries=0)


def test_cache_invalidate_one_and_all() -> None:
    cache = ProviderCache()
    r = (ProviderResult(claim="c", source="s", confidence=0.5, provider_id="p"),)
    cache.set("k1", r)
    cache.set("k2", r)
    cache.invalidate("k1")
    assert cache.get("k1") is None
    assert cache.get("k2") is not None
    cache.invalidate()
    assert cache.get("k2") is None


# ---------------------------------------------------------------------------
# Registry edge cases
# ---------------------------------------------------------------------------


def test_registry_invalid_timeout_raises() -> None:
    with pytest.raises(ValueError):
        ProviderRegistry(timeout_seconds=0)


def test_unregister_started_provider_calls_shutdown() -> None:
    reg = ProviderRegistry()
    p = _HealthyProvider("a")
    reg.register(p)
    reg.startup()
    reg.unregister("a")
    assert p.closed is True
    assert reg.providers() == ()


def test_unregister_unknown_is_noop() -> None:
    reg = ProviderRegistry()
    reg.unregister("nope")  # must not raise
    assert reg.providers() == ()


def test_fetch_skips_closed_provider_with_error() -> None:
    reg = ProviderRegistry()
    p = _HealthyProvider("a", n=1)
    reg.register(p)
    reg.shutdown()  # marks CLOSED
    out = reg.fetch(ProviderQuery(text="q"))
    assert out.results == ()
    assert "a" in out.errors
    assert "closed" in out.errors["a"]


def test_explicit_provider_ids_scope_fetch() -> None:
    reg = ProviderRegistry()
    reg.register(_HealthyProvider("a", n=1))
    reg.register(_HealthyProvider("b", n=1))
    out = reg.fetch(ProviderQuery(text="q"), provider_ids=["a"])
    assert {r.provider_id for r in out.results} == {"a"}
