"""Persistence error contracts (M1.8-S1).

The persistence failure taxonomy, frozen here as the package's error skeleton
(the concrete families come from the approved M1.8 design §14 failure matrix).
Every failure carries a stable machine-readable ``error_code``
(``PersistenceErrorCode``); messages are human-readable and are never a
contract. The classes are defined at S1; later slices (S3 IO / S4 store) raise
them. The code namespace is additive-frozen — values are never reused or
renamed.

S1 defines no code paths that raise these — S1 is skeleton only (no IO). They
are the contract later slices honour, including PER-012 "No Partial Visibility"
(a torn / incomplete artifact set is ``TornWriteError`` / ``MissingArtifactError``
— never "partially persisted").
"""

from __future__ import annotations

from enum import StrEnum

from common.errors import StratAgentError


class PersistenceErrorCode(StrEnum):
    """Stable machine-readable codes for persistence failures (additive-frozen)."""

    MISSING_ARTIFACT = "missing_artifact"
    TORN_WRITE = "torn_write"
    CORRUPT_ARTIFACT = "corrupt_artifact"
    INCOMPATIBLE_VERSION = "incompatible_version"


class PersistenceError(StratAgentError):
    """Base for all persistence failures; always carries an ``error_code``."""

    def __init__(self, message: str, *, error_code: PersistenceErrorCode) -> None:
        self.error_code = error_code
        super().__init__(message)


class MissingArtifactError(PersistenceError):
    """A required persisted file or directory is absent."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=PersistenceErrorCode.MISSING_ARTIFACT)


class TornWriteError(PersistenceError):
    """An incomplete / inconsistent artifact set (PER-012: never "partial").

    A save that did not complete — a missing manifest, a manifest referencing
    absent files, a divergent log prefix, an interrupted write — is reported as
    "not persisted", never "partially persisted".
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=PersistenceErrorCode.TORN_WRITE)


class CorruptArtifactError(PersistenceError):
    """An artifact is present but unparseable or fails its checksum."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=PersistenceErrorCode.CORRUPT_ARTIFACT)


class IncompatibleVersionError(PersistenceError):
    """A persisted format / schema / projection version this code cannot read."""

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code=PersistenceErrorCode.INCOMPATIBLE_VERSION)
