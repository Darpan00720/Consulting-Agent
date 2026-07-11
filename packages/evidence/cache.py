"""TTL cache for provider results (RC1.2, WI-4 / ADR-007).

Deterministic keys, bounded size, monotonic-clock TTL. The clock is injectable
so tests are not timing-sensitive. Caching is per (provider, query); the query
tuple fully determines the key.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import monotonic

from evidence.provider import ProviderQuery, ProviderResult


def cache_key(provider_id: str, query: ProviderQuery) -> str:
    """Return a deterministic cache key for (*provider_id*, *query*)."""
    filters = ";".join(f"{k}={v}" for k, v in sorted(query.filters.items()))
    return "|".join(
        (
            provider_id,
            query.text,
            query.archetype or "",
            query.tenant_id or "",
            str(query.max_results),
            filters,
        )
    )


@dataclass
class _Entry:
    results: tuple[ProviderResult, ...]
    expires_at: float


class ProviderCache:
    """Bounded TTL cache mapping cache keys to result tuples.

    Eviction is simple: expired entries are dropped on access, and when the
    cache is full the oldest-inserted entry is evicted (insertion-ordered dict).
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        max_entries: int = 512,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._store: dict[str, _Entry] = {}

    def get(self, key: str) -> tuple[ProviderResult, ...] | None:
        """Return cached results for *key*, or ``None`` if absent/expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._clock() >= entry.expires_at:
            del self._store[key]
            return None
        return entry.results

    def set(self, key: str, results: Sequence[ProviderResult]) -> None:
        """Cache *results* under *key*, evicting the oldest entry if full."""
        if key not in self._store and len(self._store) >= self._max:
            oldest = next(iter(self._store))
            del self._store[oldest]
        self._store[key] = _Entry(
            results=tuple(results),
            expires_at=self._clock() + self._ttl,
        )

    def invalidate(self, key: str | None = None) -> None:
        """Drop one key, or the whole cache when *key* is ``None``."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    def __len__(self) -> int:
        return len(self._store)
