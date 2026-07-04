"""StratAgent persistence — durable file-backed storage for engagements (M1.8).

A **sibling** to ``state`` (DD-1): persistence is the only IO-touching package
in the domain; ``state`` stays completely IO-free. Persistence **exclusively
owns** the ``engagements/<slug>/`` on-disk layout (DD-4) — no other package may
depend on the filesystem layout.

Approved private seam (P-DD-A): to read an engagement's committed log for
``save()``, persistence is the **sole approved consumer** of
``engagement._pipeline.committed()``. It introduces no new facade accessor and
does not change the frozen 10-method public API.

Public surface: :class:`EngagementStore` (save/load) and the persistence error
taxonomy. The implementation modules — ``paths`` (S1), ``format`` (S2: codec +
``Manifest``), ``atomic`` (S3: the sole atomic-IO authority), and ``store``'s
internals — remain internal.
"""

from persistence.errors import (
    CorruptArtifactError,
    IncompatibleVersionError,
    MissingArtifactError,
    PersistenceError,
    PersistenceErrorCode,
    TornWriteError,
)
from persistence.store import EngagementStore

__all__ = [
    "CorruptArtifactError",
    "EngagementStore",
    "IncompatibleVersionError",
    "MissingArtifactError",
    "PersistenceError",
    "PersistenceErrorCode",
    "TornWriteError",
]
