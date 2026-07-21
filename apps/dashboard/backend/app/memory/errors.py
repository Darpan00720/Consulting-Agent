"""Memory error model (requirement 11).

``MemoryService`` maps every failure — a raised exception, a provider timeout,
a missing key — into one of these. A raw provider exception never escapes the
Service; callers only ever see a ``MemoryResult``/``MemoryOperationResult``
with ``error``/``error_type`` set (or one of these types if calling a
``MemoryProvider`` adapter directly).
"""

from __future__ import annotations


class MemoryError(Exception):
    """Base class for every Memory Platform error."""


class ProviderUnavailable(MemoryError):
    """The resolved provider is not currently usable."""


class QueryFailure(MemoryError):
    """The provider's own store/retrieve/search/update/delete logic failed."""


class Timeout(MemoryError):
    """The operation did not complete within its budget."""


class PermissionDenied(MemoryError):
    """The caller/provider is not authorized for this operation."""


class CorruptMemory(MemoryError):
    """A stored record could not be decoded/validated."""


class UnsupportedOperation(MemoryError):
    """The resolved provider does not support this memory type or strategy."""


class MemoryNotFound(MemoryError):
    """A ``retrieve``/``update``/``delete`` targeted a key that doesn't exist."""
