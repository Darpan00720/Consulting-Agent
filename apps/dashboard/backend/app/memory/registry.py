"""Memory Registry (requirement 3).

Provider registration, removal, lookup, capability (type) lookup, health
lookup, priority, and a default provider — the platform's provider catalog.
``MemoryService`` never hardcodes provider instances; it resolves via this
registry, which is what keeps "add a memory backend" a pure data operation
(requirement 12: plugin-friendly, no switch/if-else, no Service/Runtime code
change).
"""

from __future__ import annotations

import logging

from app.memory.errors import MemoryError
from app.memory.models import MemoryHealthResult, MemoryHealthState, MemoryType
from app.memory.provider import MemoryProvider

log = logging.getLogger(__name__)


class DuplicateProviderError(MemoryError):
    """Registering the same provider id twice without ``replace=True``."""


class UnknownProviderError(MemoryError):
    """Looked up / removed a provider id that was never registered."""


class MemoryRegistry:
    """In-process provider catalog. Not a singleton by construction — tests
    build their own; ``adapters.default_memory_registry()`` provides the
    production instance seeded with the three built-in adapters."""

    def __init__(self) -> None:
        self._providers: dict[str, MemoryProvider] = {}
        self._priority: dict[str, int] = {}  # lower number = higher priority
        self._default: str | None = None
        self._last_health: dict[str, MemoryHealthResult] = {}

    # ---- registration -------------------------------------------------

    def register(
        self,
        provider: MemoryProvider,
        *,
        priority: int = 100,
        default: bool = False,
        replace: bool = False,
    ) -> None:
        """Duplicate detection (requirement 3): the same provider id twice is
        an error unless the caller explicitly opts into replacement."""
        if provider.id in self._providers and not replace:
            raise DuplicateProviderError(f"provider '{provider.id}' already registered")
        self._providers[provider.id] = provider
        self._priority[provider.id] = priority
        if default or self._default is None:
            self._default = provider.id
        log.debug(
            "memory-registry register id=%s priority=%d default=%s",
            provider.id,
            priority,
            provider.id == self._default,
        )

    def remove(self, provider_id: str) -> None:
        """Provider removal (requirement 3). Demotes the default to the
        next-highest-priority remaining provider, or clears it."""
        self._providers.pop(provider_id, None)
        self._priority.pop(provider_id, None)
        self._last_health.pop(provider_id, None)
        if self._default == provider_id:
            remaining = self.providers_by_priority()
            self._default = remaining[0].id if remaining else None
        log.debug("memory-registry remove id=%s", provider_id)

    # ---- lookup ---------------------------------------------------------

    def get(self, provider_id: str) -> MemoryProvider | None:
        return self._providers.get(provider_id)

    def priority_of(self, provider_id: str) -> int | None:
        return self._priority.get(provider_id)

    def set_priority(self, provider_id: str, priority: int) -> None:
        if provider_id not in self._providers:
            raise UnknownProviderError(f"provider '{provider_id}' is not registered")
        self._priority[provider_id] = priority

    def default_provider(self) -> MemoryProvider | None:
        return self._providers.get(self._default) if self._default else None

    def set_default(self, provider_id: str) -> None:
        if provider_id not in self._providers:
            raise UnknownProviderError(f"provider '{provider_id}' is not registered")
        self._default = provider_id

    # ---- discovery / capability lookup ---------------------------------

    def discover(self) -> tuple[MemoryProvider, ...]:
        return tuple(self._providers.values())

    def providers_by_priority(self) -> tuple[MemoryProvider, ...]:
        """Every registered provider, ascending priority (lower number first)."""
        return tuple(
            sorted(
                self._providers.values(), key=lambda p: self._priority.get(p.id, 100)
            )
        )

    def find_by_type(self, memory_type: MemoryType) -> tuple[MemoryProvider, ...]:
        """Capability lookup (requirement 3/4): providers declaring this
        memory type, in priority order."""
        return tuple(
            p
            for p in self.providers_by_priority()
            if memory_type in p.supported_types()
        )

    # ---- health ----------------------------------------------------------

    async def health(self, provider_id: str) -> MemoryHealthResult:
        provider = self._providers.get(provider_id)
        if provider is None:
            return MemoryHealthResult(
                MemoryHealthState.UNKNOWN, detail="not registered"
            )
        try:
            result = await provider.health()
        except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE, not a crash
            result = MemoryHealthResult(
                MemoryHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
            )
        self._last_health[provider_id] = result
        return result

    def last_health(self, provider_id: str) -> MemoryHealthResult | None:
        return self._last_health.get(provider_id)
