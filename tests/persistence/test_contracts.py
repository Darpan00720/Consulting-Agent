"""M1.8-S1 contract tests: persistence error taxonomy, path constants, exports.

S1 is skeleton only (no IO): these tests pin the *contracts* — the error
hierarchy/codes, the layout constants, and the curated package surface. PER-012
("No Partial Visibility") and the other runtime invariants require IO and are
tested with S4 (save/load), not here.
"""

from __future__ import annotations

import persistence
from common.errors import StratAgentError
from persistence import (
    CorruptArtifactError,
    IncompatibleVersionError,
    MissingArtifactError,
    PersistenceError,
    PersistenceErrorCode,
    TornWriteError,
    paths,
)

_CONCRETE = (
    (MissingArtifactError, PersistenceErrorCode.MISSING_ARTIFACT),
    (TornWriteError, PersistenceErrorCode.TORN_WRITE),
    (CorruptArtifactError, PersistenceErrorCode.CORRUPT_ARTIFACT),
    (IncompatibleVersionError, PersistenceErrorCode.INCOMPATIBLE_VERSION),
)


# --- error hierarchy + inheritance -------------------------------------------


def test_base_error_inherits_stratagent_error() -> None:
    assert issubclass(PersistenceError, StratAgentError)


def test_concrete_errors_inherit_persistence_error() -> None:
    for cls, _ in _CONCRETE:
        assert issubclass(cls, PersistenceError)
        assert issubclass(cls, StratAgentError)


# --- error codes -------------------------------------------------------------


def test_each_error_carries_its_code() -> None:
    for cls, code in _CONCRETE:
        err = cls("boom")
        assert err.error_code is code
        assert str(err) == "boom"


def test_base_error_requires_explicit_code() -> None:
    err = PersistenceError("x", error_code=PersistenceErrorCode.TORN_WRITE)
    assert err.error_code is PersistenceErrorCode.TORN_WRITE
    assert isinstance(err, StratAgentError)


# --- frozen namespace + serialization ----------------------------------------


def test_code_namespace_is_frozen() -> None:
    assert {c.value for c in PersistenceErrorCode} == {
        "missing_artifact",
        "torn_write",
        "corrupt_artifact",
        "incompatible_version",
    }


def test_codes_are_stable_strings() -> None:
    # StrEnum: the code serializes to its stable string value (the contract)
    assert PersistenceErrorCode.TORN_WRITE == "torn_write"
    assert str(PersistenceErrorCode.MISSING_ARTIFACT) == "missing_artifact"


# --- path constants ----------------------------------------------------------


def test_path_constants() -> None:
    assert paths.ENGAGEMENTS_DIRNAME == "engagements"
    assert paths.EVENTS_LOG_FILENAME == "events.log"
    assert paths.SNAPSHOT_FILENAME == "state.json"
    assert paths.MANIFEST_FILENAME == "manifest.json"
    assert paths.STORE_FORMAT_VERSION == 1


def test_paths_module_performs_no_io() -> None:
    # S1 constraint: paths.py is constants only — no filesystem functions leak in
    import inspect

    src = inspect.getsource(paths)
    for banned in ("open(", "Path(", "os.", "mkdir", "exists(", "write", "read"):
        assert banned not in src, f"paths.py must be IO-free; found {banned!r}"


# --- curated exports / no accidental public surface --------------------------


def test_public_surface_is_exactly_the_error_taxonomy() -> None:
    assert set(persistence.__all__) == {
        "CorruptArtifactError",
        "IncompatibleVersionError",
        "MissingArtifactError",
        "PersistenceError",
        "PersistenceErrorCode",
        "TornWriteError",
    }
    public = {n for n in dir(persistence) if not n.startswith("_")}
    # only the __all__ names + the (unavoidable) submodule attributes
    assert set(persistence.__all__) <= public


def test_store_and_io_not_yet_exposed() -> None:
    # EngagementStore / save / load arrive in later slices — not at S1
    assert not hasattr(persistence, "EngagementStore")
    assert not hasattr(persistence, "save")
    assert not hasattr(persistence, "load")
    assert "EngagementStore" not in persistence.__all__
