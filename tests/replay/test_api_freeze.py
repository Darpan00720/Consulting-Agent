"""M1.9 Phase 7 API-freeze: the replay public surface is pinned exactly.

Mirrors the persistence freeze. These tests fail the moment the surface drifts —
a new/renamed export, a changed method set, a changed signature, or a redefined
error type. Behaviour is exercised elsewhere (replay/recovery/property suites);
here we pin *shape* only.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import replay as replay_pkg
from common.errors import StratAgentError
from replay import ReplayContract, ReplayEngine, ReplayError, recover, replay
from state import Engagement, EngagementState
from state.append import ReplayIntegrityError as FrozenReplayIntegrityError

_FROZEN_ALL = {
    "ReplayContract",
    "ReplayEngine",
    "ReplayError",
    "ReplayIntegrityError",
    "recover",
    "replay",
}


def test_public_all_is_frozen() -> None:
    assert set(replay_pkg.__all__) == _FROZEN_ALL
    assert len(replay_pkg.__all__) == len(set(replay_pkg.__all__))  # no dups
    for name in replay_pkg.__all__:
        assert hasattr(replay_pkg, name), name


def test_replay_engine_public_methods_are_frozen() -> None:
    public = {n for n in dir(ReplayEngine) if not n.startswith("_")}
    assert public == {"replay", "recover"}


def test_replay_engine_signatures_are_frozen() -> None:
    # param names + the non-generic types are pinned; the `log: Sequence[Event]`
    # generic (an Annotated discriminated union) is fragile to compare, so we
    # pin its parameter name only.
    rep = inspect.signature(ReplayEngine.replay)
    assert list(rep.parameters) == ["self", "log"]
    assert get_type_hints(ReplayEngine.replay)["return"] is Engagement

    rec = inspect.signature(ReplayEngine.recover)
    assert list(rec.parameters) == ["self", "log", "snapshot"]
    rec_hints = get_type_hints(ReplayEngine.recover)
    assert rec_hints["return"] is Engagement
    assert rec_hints["snapshot"] is EngagementState


def test_module_entry_points_are_frozen() -> None:
    assert list(inspect.signature(replay).parameters) == ["log"]
    assert get_type_hints(replay)["return"] is Engagement

    assert list(inspect.signature(recover).parameters) == ["log", "snapshot"]
    rec_hints = get_type_hints(recover)
    assert rec_hints["return"] is Engagement
    assert rec_hints["snapshot"] is EngagementState


def test_replay_contract_is_runtime_checkable_protocol() -> None:
    assert isinstance(ReplayEngine(), ReplayContract)  # structural conformance

    class _NotReplay:
        pass

    assert not isinstance(_NotReplay(), ReplayContract)


def test_error_hierarchy_is_frozen() -> None:
    # ReplayError is an additive orchestration base; the integrity error is the
    # frozen state.append object re-exported by identity (never a redefinition).
    assert issubclass(ReplayError, StratAgentError)
    assert replay_pkg.ReplayIntegrityError is FrozenReplayIntegrityError
    # replay defines no machine-code enum of its own
    assert not hasattr(replay_pkg, "ReplayErrorCode")
