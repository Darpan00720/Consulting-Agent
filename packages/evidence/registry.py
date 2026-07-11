"""Provider registry — lifecycle, failure isolation, caching, traceability.

RC1.2, WI-4 / ADR-007. This is the single consumption seam for evidence
providers. It never lets one provider's failure break the others (isolation),
records which provider produced each result and which came from cache
(traceability), and enforces a per-call time budget (failure handling).

No providers are registered here; deployments attach them.
"""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import UTC, datetime

from evidence.cache import ProviderCache, cache_key
from evidence.errors import EvidenceProviderError, ProviderTimeoutError
from evidence.provider import (
    EvidenceProvider,
    ProviderQuery,
    ProviderResult,
    ProviderStatus,
)


@dataclass(frozen=True)
class FetchOutcome:
    """Result of a registry fetch — successes and failures, fully traceable.

    ``results`` are the merged healthy results (each carries its ``provider_id``).
    ``errors`` maps a failed provider_id to its error message. ``from_cache`` is
    the set of provider_ids served from cache. ``fetched_at`` timestamps the call.
    """

    results: tuple[ProviderResult, ...]
    errors: dict[str, str] = field(default_factory=dict)
    from_cache: frozenset[str] = frozenset()
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def ok(self) -> bool:
        """True if no provider failed."""
        return not self.errors


class ProviderRegistry:
    """Registers providers and fans a query out to them with isolation."""

    def __init__(
        self,
        *,
        cache: ProviderCache | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._providers: dict[str, EvidenceProvider] = {}
        self._status: dict[str, ProviderStatus] = {}
        self._cache = cache
        self._timeout = timeout_seconds

    # -- registration --------------------------------------------------------

    def register(self, provider: EvidenceProvider) -> None:
        """Register *provider*. Raises if its id collides with an existing one."""
        pid = provider.provider_id
        if pid in self._providers:
            raise EvidenceProviderError(f"provider_id already registered: {pid!r}")
        self._providers[pid] = provider
        self._status[pid] = ProviderStatus.UNINITIALIZED

    def unregister(self, provider_id: str) -> None:
        """Remove a provider (calls its ``shutdown`` if it was started)."""
        provider = self._providers.pop(provider_id, None)
        prior = self._status.pop(provider_id, None)
        if provider is not None and prior not in (
            None,
            ProviderStatus.UNINITIALIZED,
            ProviderStatus.CLOSED,
        ):
            # shutdown must never propagate
            with contextlib.suppress(Exception):
                provider.shutdown()

    def providers(self) -> tuple[str, ...]:
        """Registered provider ids, in registration order."""
        return tuple(self._providers)

    # -- lifecycle -----------------------------------------------------------

    def startup(self) -> None:
        """Start every provider; a failure marks it UNAVAILABLE, never raises."""
        for pid, provider in self._providers.items():
            try:
                provider.startup()
                self._status[pid] = provider.health()
            except Exception:  # noqa: BLE001 — isolate startup failure
                self._status[pid] = ProviderStatus.UNAVAILABLE

    def health(self) -> dict[str, ProviderStatus]:
        """Snapshot of each provider's current status."""
        return dict(self._status)

    def shutdown(self) -> None:
        """Shut every provider down; failures are swallowed (idempotent)."""
        for pid, provider in self._providers.items():
            with contextlib.suppress(Exception):
                provider.shutdown()
            self._status[pid] = ProviderStatus.CLOSED

    # -- fetch ---------------------------------------------------------------

    def fetch(
        self,
        query: ProviderQuery,
        *,
        provider_ids: Sequence[str] | None = None,
        use_cache: bool = True,
    ) -> FetchOutcome:
        """Fan *query* out to selected providers, isolating failures.

        Returns a :class:`FetchOutcome` merging healthy results; a provider that
        raises, times out, or is unavailable is recorded in ``errors`` and does
        not affect the others.
        """
        targets = self._resolve_targets(provider_ids)
        merged: list[ProviderResult] = []
        errors: dict[str, str] = {}
        from_cache: set[str] = set()

        for pid in targets:
            provider = self._providers[pid]
            if self._status.get(pid) in (
                ProviderStatus.UNAVAILABLE,
                ProviderStatus.CLOSED,
            ):
                errors[pid] = f"provider {pid!r} is {self._status[pid].value}"
                continue

            key = cache_key(pid, query)
            if use_cache and self._cache is not None:
                cached = self._cache.get(key)
                if cached is not None:
                    merged.extend(cached)
                    from_cache.add(pid)
                    continue

            try:
                results = self._call(provider, query)
            except ProviderTimeoutError as exc:
                self._status[pid] = ProviderStatus.DEGRADED
                errors[pid] = str(exc)
                continue
            except EvidenceProviderError as exc:
                self._status[pid] = ProviderStatus.DEGRADED
                errors[pid] = str(exc)
                continue
            except Exception as exc:  # noqa: BLE001 — unknown provider fault
                self._status[pid] = ProviderStatus.DEGRADED
                errors[pid] = f"unexpected error: {exc}"
                continue

            stamped = tuple(self._stamp(pid, r) for r in results)
            if use_cache and self._cache is not None:
                self._cache.set(key, stamped)
            merged.extend(stamped)
            self._status[pid] = ProviderStatus.READY

        return FetchOutcome(
            results=tuple(merged),
            errors=errors,
            from_cache=frozenset(from_cache),
        )

    # -- internals -----------------------------------------------------------

    def _resolve_targets(self, provider_ids: Sequence[str] | None) -> tuple[str, ...]:
        if provider_ids is None:
            return tuple(self._providers)
        missing = [p for p in provider_ids if p not in self._providers]
        if missing:
            raise EvidenceProviderError(f"unknown provider_id(s): {missing}")
        return tuple(provider_ids)

    def _call(
        self, provider: EvidenceProvider, query: ProviderQuery
    ) -> Sequence[ProviderResult]:
        """Invoke ``provider.fetch`` under a hard time budget."""
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(provider.fetch, query)
            try:
                return future.result(timeout=self._timeout)
            except FutureTimeoutError as exc:
                raise ProviderTimeoutError(
                    f"provider {provider.provider_id!r} exceeded"
                    f" {self._timeout}s budget"
                ) from exc

    @staticmethod
    def _stamp(provider_id: str, result: ProviderResult) -> ProviderResult:
        """Guarantee the result's provider_id matches its source (traceability)."""
        if result.provider_id == provider_id:
            return result
        return ProviderResult(
            claim=result.claim,
            source=result.source,
            confidence=result.confidence,
            provider_id=provider_id,
            as_of=result.as_of,
            value=result.value,
            url=result.url,
            raw=result.raw,
        )
