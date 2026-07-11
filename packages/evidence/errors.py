"""Evidence Provider error hierarchy (RC1.2, WI-4 / ADR-007).

All provider failures derive from :class:`EvidenceProviderError` so the
registry can isolate a single provider's failure without breaking retrieval.
"""

from __future__ import annotations

from common.errors import StratAgentError


class EvidenceProviderError(StratAgentError):
    """Base class for all evidence-provider failures."""


class ProviderConfigError(EvidenceProviderError):
    """A provider was registered or started with invalid configuration."""


class ProviderUnavailableError(EvidenceProviderError):
    """A provider is (temporarily) unreachable or not ready to serve."""


class ProviderTimeoutError(EvidenceProviderError):
    """A provider did not return within its allotted time budget."""
