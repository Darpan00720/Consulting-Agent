"""Evidence Provider interface (RC1.2, WI-4 / ADR-007).

**Extension mechanism only — no providers are populated here.**

An *Evidence Provider* is an optional, pluggable source of *external* evidence
(market sizes, benchmarks, transaction comparables, industry data) that a
deployment may attach later. The knowledge vault deliberately holds no
quantitative benchmarks (ADR-003, decision D-6); providers are the sanctioned
seam for supplying sourced numbers without inventing them.

A :class:`ProviderResult` carries full provenance so a caller can promote it
into the Engagement State Evidence Ledger as an ``EvidenceType.EXTERNAL_SOURCE``
record (ADR-002 §14) — which requires a ``source``, mirrored here.

Providers are consumed through :class:`evidence.registry.ProviderRegistry`,
which adds caching, per-provider failure isolation, and traceability. Nothing in
this module performs I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ProviderStatus(StrEnum):
    """Lifecycle/health state of a provider (see :class:`EvidenceProvider`)."""

    UNINITIALIZED = "uninitialized"  # registered, startup() not yet called
    READY = "ready"  # healthy, serving
    DEGRADED = "degraded"  # serving, but a recent call failed
    UNAVAILABLE = "unavailable"  # cannot serve (config/connectivity)
    CLOSED = "closed"  # shutdown() called; no longer usable


@dataclass(frozen=True)
class ProviderQuery:
    """Immutable request passed to a provider.

    ``archetype``/``tenant_id`` let a provider scope or authorize a lookup;
    ``filters`` is an opaque provider-specific map. The tuple of fields also
    forms the deterministic cache key (see :mod:`evidence.cache`).
    """

    text: str
    archetype: str | None = None
    tenant_id: str | None = None
    max_results: int = 5
    filters: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    """One sourced evidence item with provenance.

    Field names mirror :class:`state.ledgers.Evidence` so a result maps cleanly
    onto an ``EvidenceType.EXTERNAL_SOURCE`` record. ``source`` is mandatory —
    a provider result with no citation is not evidence.
    """

    claim: str
    source: str  # citation — mandatory (mirrors Evidence external_source rule)
    confidence: float  # [0.0, 1.0]
    provider_id: str  # which provider produced this (traceability)
    as_of: datetime | None = None  # freshness of the underlying datum
    value: str | None = None  # optional structured value (e.g. "$1.5B")
    url: str | None = None  # optional deep link to the source
    raw: Mapping[str, object] = field(default_factory=dict)  # provider payload


@runtime_checkable
class EvidenceProvider(Protocol):
    """The contract a provider must satisfy to be registered.

    Implementations are supplied by deployments, not by this package. Lifecycle:
    ``startup() → (health()/fetch())* → shutdown()``. Providers must be
    side-effect-free to import and must not raise from :meth:`health`.
    """

    @property
    def provider_id(self) -> str:
        """Stable, unique identifier (used for cache keys and traceability)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        ...

    def startup(self) -> None:
        """Acquire connections/credentials. May raise :class:`ProviderConfigError`."""
        ...

    def health(self) -> ProviderStatus:
        """Return current status. Must not raise."""
        ...

    def fetch(self, query: ProviderQuery) -> Sequence[ProviderResult]:
        """Return sourced results for *query*.

        May raise an :class:`evidence.errors.EvidenceProviderError` subclass;
        the registry isolates such failures.
        """
        ...

    def shutdown(self) -> None:
        """Release resources. Must be idempotent."""
        ...
