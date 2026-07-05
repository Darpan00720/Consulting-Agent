"""M1.9 Phase 2 replay-skeleton contract tests.

Skeleton only: these pin the public surface, the interface, the purity contract
(RP-016), and the frozen-dependency wiring. No behavioural replay is exercised
— replay is not implemented until Phase 3, so the reconstruction paths raise
``NotImplementedError``.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

import replay as replay_pkg
from common.errors import StratAgentError
from replay import ReplayContract, ReplayEngine, ReplayError, replay
from state import Engagement
from state.append import ReplayIntegrityError as FrozenReplayIntegrityError

_EXPECTED_SURFACE = {
    "ReplayContract",
    "ReplayEngine",
    "ReplayError",
    "ReplayIntegrityError",
    "replay",
}


# --- public API surface ------------------------------------------------------


def test_public_api_surface_is_frozen() -> None:
    assert set(replay_pkg.__all__) == _EXPECTED_SURFACE
    assert len(replay_pkg.__all__) == len(set(replay_pkg.__all__))  # no dups
    for name in replay_pkg.__all__:
        assert hasattr(replay_pkg, name), name


# --- ReplayEngine interface --------------------------------------------------


def test_replay_engine_interface() -> None:
    engine = ReplayEngine()
    assert isinstance(engine, ReplayContract)  # structural conformance
    assert list(inspect.signature(ReplayEngine.replay).parameters) == ["self", "log"]
    # an empty log is valid and replays to the empty engagement at version 0
    engagement = engine.replay([])
    assert isinstance(engagement, Engagement)
    assert engagement.current_version() == 0


# --- replay() contract function ----------------------------------------------


def test_replay_contract_function() -> None:
    assert list(inspect.signature(replay).parameters) == ["log"]
    # delegates to a default engine; empty log -> version-0 engagement
    assert replay([]).current_version() == 0


# --- ReplayContract protocol -------------------------------------------------


def test_replay_contract_protocol() -> None:
    # runtime_checkable structural protocol: presence of a replay() method is
    # the whole contract — a bare object does not conform, a replay-bearing one does.
    class _Conforming:
        def replay(self, log):  # a replay-bearing stand-in
            ...

    assert isinstance(_Conforming(), ReplayContract)
    assert not isinstance(object(), ReplayContract)


# --- purity contract (RP-016) ------------------------------------------------


def test_purity_contract_rp016() -> None:
    # RP-016: the engine is a frozen, stateless value — it cannot mutate engine
    # or global state, and equal instances are indistinguishable.
    assert dataclasses.is_dataclass(ReplayEngine)
    assert dataclasses.fields(ReplayEngine) == ()  # stateless: no fields
    assert ReplayEngine() == ReplayEngine()
    engine = ReplayEngine()
    with pytest.raises(dataclasses.FrozenInstanceError):
        engine.mutated = 1  # type: ignore[attr-defined]


# --- frozen dependencies -----------------------------------------------------


def test_frozen_dependencies() -> None:
    # replay re-exports the FROZEN integrity error object itself (identity),
    # never a redefinition; its orchestration base is a StratAgentError.
    assert replay_pkg.ReplayIntegrityError is FrozenReplayIntegrityError
    assert issubclass(ReplayError, StratAgentError)
    # replay defines no machine-code enum of its own (decision D-G: reuse the
    # frozen ReplayErrorCode, add no new codes)
    assert not hasattr(replay_pkg, "ReplayErrorCode")
