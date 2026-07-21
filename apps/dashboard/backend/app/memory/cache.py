"""Cache abstraction (requirement 9).

Lives in ``MemoryService``, wrapping provider calls — never baked into an
agent or a provider adapter. Supports TTL expiry, manual per-key invalidation,
provider-scoped invalidation (evict everything cached for one provider, e.g.
after that provider reports itself stale/unhealthy), and cache statistics.

Keys are namespaced ``"{provider_id}::{operation}::{raw_key}"`` so
provider-scoped invalidation is a prefix scan, not a second index.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.memory.models import CacheStats

DEFAULT_TTL_S = 60.0


@dataclass
class _CacheEntry:
    value: object
    expires_at: float


class MemoryCache:
    """A tiny in-process TTL cache. One instance per ``MemoryService`` —
    intentionally not a global (no shared mutable state across services)."""

    def __init__(self, default_ttl_s: float = DEFAULT_TTL_S) -> None:
        self.default_ttl_s = default_ttl_s
        self._store: dict[str, _CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(provider_id: str, operation: str, raw_key: str) -> str:
        return f"{provider_id}::{operation}::{raw_key}"

    def get(self, key: str) -> object | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.expires_at < time.monotonic():
            del self._store[key]  # expired — evict, count as a miss
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: object, ttl_s: float | None = None) -> None:
        self._store[key] = _CacheEntry(
            value=value, expires_at=time.monotonic() + (ttl_s or self.default_ttl_s)
        )

    def invalidate(self, key: str) -> None:
        """Manual invalidation (requirement 9) — one specific cache key."""
        self._store.pop(key, None)

    def invalidate_provider(self, provider_id: str) -> None:
        """Provider invalidation (requirement 9) — every entry cached for one
        provider, e.g. after it reports UNAVAILABLE/DEGRADED."""
        prefix = f"{provider_id}::"
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> CacheStats:
        return CacheStats(hits=self._hits, misses=self._misses, size=len(self._store))
