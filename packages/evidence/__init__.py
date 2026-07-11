"""Evidence Provider extension mechanism (RC1.2, WI-4 / ADR-007).

Public API for attaching optional external-evidence providers. This package
ships the *interface and machinery only* — no providers are populated. See
ADR-007 for the design and lifecycle.
"""

from __future__ import annotations

from evidence.cache import ProviderCache, cache_key
from evidence.errors import (
    EvidenceProviderError,
    ProviderConfigError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from evidence.provider import (
    EvidenceProvider,
    ProviderQuery,
    ProviderResult,
    ProviderStatus,
)
from evidence.registry import FetchOutcome, ProviderRegistry

__all__ = [
    # interface
    "EvidenceProvider",
    "ProviderQuery",
    "ProviderResult",
    "ProviderStatus",
    # registry + lifecycle
    "ProviderRegistry",
    "FetchOutcome",
    # caching
    "ProviderCache",
    "cache_key",
    # errors
    "EvidenceProviderError",
    "ProviderConfigError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
]
