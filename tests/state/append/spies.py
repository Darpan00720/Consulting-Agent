"""Reusable append test doubles (M1.7.3-S4; designed for reuse in M1.8 tests)."""

from __future__ import annotations

from state.append import CandidateCommit, Committed, StateUpdater


class SpyStateUpdater(StateUpdater):
    """A StateUpdater that records commit activity; behavior unchanged."""

    def __init__(self, initial: Committed) -> None:
        super().__init__(initial)
        self.commit_count = 0
        self.last_candidate: CandidateCommit | None = None
        self.last_snapshot: Committed | None = None

    def commit(self, candidate: CandidateCommit) -> Committed:
        committed = super().commit(candidate)
        self.commit_count += 1
        self.last_candidate = candidate
        self.last_snapshot = committed
        return committed
