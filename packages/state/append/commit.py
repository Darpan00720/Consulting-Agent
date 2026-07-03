"""Committed snapshots + the single commit point (M1.7.3-S4, design §4/§6).

Module contract (architectural boundary): :class:`Committed` is the
exactly-one immutable object representing committed system state, and
:func:`make_committed` is the **only construction path** for it — for append
today and equally for replay, persistence restore, snapshot restore, and
recovery tomorrow (M1.8/M1.9). Those are *consumers* of ``make_committed``
and must never construct ``Committed`` directly (invariant P23).

``make_committed`` is a **pure function** (invariant P22): deterministic,
referentially transparent, no mutation, no IO, no clocks, no randomness, no
global state, and no interaction with :class:`StateUpdater`. Given the same
:class:`CandidateCommit` it always produces an identical ``Committed``. Its
only derivation — ``version`` — flows through S2's ``current_version`` (the
sanctioned arithmetic entry point), preserving invariant P18
(``version == current_version(log)``).

:class:`StateUpdater` owns *when state changes*: ``commit()`` is exactly
``make_committed`` + one reference assignment + return. Nothing else in the
system mutates committed data.

Ownership matrix (S4 plan §2): S1 errors · S2 arithmetic · S3 decisions ·
S4 orchestration · M1.5 projection · M1.6 validation.
"""

from __future__ import annotations

from dataclasses import dataclass

from state.append.versioning import current_version
from state.events import Event
from state.identifiers import EventId
from state.models import EngagementState
from state.validation import ValidationReport


@dataclass(frozen=True)
class Committed:
    """The committed system state: log, state, event ids, stored version.

    ``version`` is stored, never re-derived by consumers (S2 computed it at
    minting). Only :func:`make_committed` may construct instances (P21/P23).
    """

    log: tuple[Event, ...]
    state: EngagementState
    event_ids: frozenset[EventId]
    version: int


@dataclass(frozen=True)
class CandidateCommit:
    """The complete prepared-commit payload (invariant P20).

    ``events`` are the already-stamped immutable events about to become
    committed: persistence (M1.8) persists exactly these — never
    reconstructing them from ``log[-k:]``.
    """

    log: tuple[Event, ...]
    state: EngagementState
    event_ids: frozenset[EventId]
    validation_report: ValidationReport
    events: tuple[Event, ...]


def make_committed(candidate: CandidateCommit) -> Committed:
    """The single construction path for ``Committed`` snapshots (P22/P23).

    Pure: same candidate in, identical snapshot out — always. ``version`` is
    computed via S2's ``current_version`` and stored on the snapshot.
    """
    return Committed(
        log=candidate.log,
        state=candidate.state,
        event_ids=candidate.event_ids,
        version=current_version(candidate.log),
    )


class StateUpdater:
    """The commit point: holds the committed snapshot; swaps it atomically."""

    def __init__(self, initial: Committed) -> None:
        self._committed = initial

    def read(self) -> Committed:
        """The current committed snapshot (immutable)."""
        return self._committed

    def commit(self, candidate: CandidateCommit) -> Committed:
        """``make_committed`` + one reference assignment + return. Nothing else."""
        committed = make_committed(candidate)
        self._committed = committed
        return committed
