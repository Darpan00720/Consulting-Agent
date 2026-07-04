"""M1.8-S5 API-freeze: the persistence public surface is pinned exactly.

Mirrors the M1.7.3-S6 facade freeze. These tests fail the moment the public
surface drifts — a new export, a renamed/removed method, or a changed
signature — so the contract cannot change silently. Behaviour is exercised
elsewhere (S4 invariants, S5 integration); here we pin *shape* only.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import persistence
from persistence import EngagementStore
from state import Engagement

# The frozen public surface: the error taxonomy (S1) + the EngagementStore
# entry point (S4). Exactly these seven names, nothing more.
_FROZEN_ALL = {
    "CorruptArtifactError",
    "EngagementStore",
    "IncompatibleVersionError",
    "MissingArtifactError",
    "PersistenceError",
    "PersistenceErrorCode",
    "TornWriteError",
}


def test_public_all_is_frozen() -> None:
    assert set(persistence.__all__) == _FROZEN_ALL
    # __all__ has no duplicates and every name resolves on the package
    assert len(persistence.__all__) == len(set(persistence.__all__))
    for name in persistence.__all__:
        assert hasattr(persistence, name), name


def test_engagement_store_public_methods_are_frozen() -> None:
    # only save / load are public; everything else on the class is private
    public = {n for n in dir(EngagementStore) if not n.startswith("_")}
    assert public == {"save", "load"}


def test_engagement_store_signatures_are_frozen() -> None:
    # parameter names + resolved type hints are pinned (annotation string form
    # is PEP-563/deferred, so we compare resolved types, not the raw repr)
    init = inspect.signature(EngagementStore.__init__)
    assert list(init.parameters) == ["self", "root"]
    assert get_type_hints(EngagementStore.__init__) == {
        "root": Path,
        "return": type(None),
    }

    save = inspect.signature(EngagementStore.save)
    assert list(save.parameters) == ["self", "engagement"]
    assert get_type_hints(EngagementStore.save) == {
        "engagement": Engagement,
        "return": type(None),
    }

    load = inspect.signature(EngagementStore.load)
    assert list(load.parameters) == ["self", "slug"]
    assert get_type_hints(EngagementStore.load) == {"slug": str, "return": Engagement}


def test_no_module_level_io_functions() -> None:
    # IO is orchestrated only through EngagementStore — never as free functions
    for banned in ("save", "load", "read", "write", "atomic_write"):
        assert not hasattr(persistence, banned), banned
