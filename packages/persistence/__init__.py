"""StratAgent persistence — durable file-backed storage for engagements (M1.8).

A **sibling** to ``state`` (DD-1): persistence is the only IO-touching package
in the domain; ``state`` stays completely IO-free. Persistence **exclusively
owns** the ``engagements/<slug>/`` on-disk layout (DD-4) — no other package may
depend on the filesystem layout.

Approved private seam (P-DD-A): to read an engagement's committed log for
``save()``, persistence is the **sole approved consumer** of
``engagement._pipeline.committed()``. It introduces no new facade accessor and
does not change the frozen 10-method public API.

Public surface: only the persistence error taxonomy is exposed today (the S1
skeleton). ``EngagementStore`` and ``save``/``load`` arrive in later slices;
the implementation modules (``paths``, and the future ``format``/``atomic``/
``store``) remain internal.
"""

from persistence.errors import (
    CorruptArtifactError,
    IncompatibleVersionError,
    MissingArtifactError,
    PersistenceError,
    PersistenceErrorCode,
    TornWriteError,
)

__all__ = [
    "CorruptArtifactError",
    "IncompatibleVersionError",
    "MissingArtifactError",
    "PersistenceError",
    "PersistenceErrorCode",
    "TornWriteError",
]
