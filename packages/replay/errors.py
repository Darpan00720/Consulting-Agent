"""Replay error taxonomy (M1.9 Phase 2 — skeleton wiring).

Replay is orchestration over frozen, pure seams, so its failure surface is
thin. Two families are wired here:

- :class:`ReplayError` — the base for replay *orchestration* failures (an
  unusable source, recovery misuse). A new, **additive** ``StratAgentError``
  that introduces **no** machine codes and does not touch the frozen
  replay-integrity taxonomy.
- :class:`ReplayIntegrityError` — re-exported **unchanged** from
  ``state.append`` (M1.7.4, frozen). Replay raises the frozen error object
  itself for at-rest integrity defects (bad log, stale/future/foreign
  snapshot); it never redefines or subclasses the frozen codes. Re-exporting
  gives replay consumers a single catch site.

Phase 2 is skeleton only — no code path raises :class:`ReplayError` yet.
"""

from __future__ import annotations

from common.errors import StratAgentError
from state.append import ReplayIntegrityError

__all__ = ["ReplayError", "ReplayIntegrityError"]


class ReplayError(StratAgentError):
    """Base for replay *orchestration* failures (not at-rest integrity).

    At-rest integrity defects surface as the frozen
    :class:`ReplayIntegrityError`; this base covers orchestration-level misuse
    the engine may add later (e.g. recovery requested on a fatal artifact).
    Additive only: no new error codes, no change to the frozen taxonomy.
    """
