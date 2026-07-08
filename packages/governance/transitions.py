"""Lifecycle state-machine transition validator (ADR-002 §2 Lifecycle Status).

Enforces the allowed transition graph.  Terminal states (COMPLETED, FAILED,
ABORTED) cannot be left.  REPORTING is unreachable without both governance
gates having fired (enforced by :mod:`governance.gates`; the transition graph
here only encodes *structural* legality).

Allowed transitions (positive graph — everything else is forbidden):

  INTAKE          → CLASSIFYING
  CLASSIFYING     → GAP_ANALYSIS
  GAP_ANALYSIS    → PLANNING
  PLANNING        → FRAMING
  FRAMING         → ISSUE_TREE
  ISSUE_TREE      → KNOWLEDGE
  KNOWLEDGE       → ANALYSIS
  ANALYSIS        → EVIDENCE_VALIDATION
  EVIDENCE_VALIDATION → REVIEW
  REVIEW          → CHALLENGE            (if Reviewer verdict = approved)
  REVIEW          → ANALYSIS             (rework loop)
  CHALLENGE       → REPORTING            (if Challenger verdict = stands/caveats)
  CHALLENGE       → REVIEW               (rework loop — needs_rework)
  CHALLENGE       → ANALYSIS             (deep rework)
  REPORTING       → COMPLETED
  Any non-terminal → FAILED
  Any non-terminal → ABORTED
"""

from __future__ import annotations

from common.errors import StratAgentError
from state.enums import LifecycleStatus


class TransitionError(StratAgentError):
    """Raised when a lifecycle transition is not allowed."""


_L = LifecycleStatus

_TERMINAL: frozenset[LifecycleStatus] = frozenset(
    {_L.COMPLETED, _L.FAILED, _L.ABORTED}
)

_ALLOWED: frozenset[tuple[LifecycleStatus, LifecycleStatus]] = frozenset(
    {
        (_L.INTAKE, _L.CLASSIFYING),
        (_L.CLASSIFYING, _L.GAP_ANALYSIS),
        (_L.GAP_ANALYSIS, _L.PLANNING),
        (_L.PLANNING, _L.FRAMING),
        (_L.FRAMING, _L.ISSUE_TREE),
        (_L.ISSUE_TREE, _L.KNOWLEDGE),
        (_L.KNOWLEDGE, _L.ANALYSIS),
        (_L.ANALYSIS, _L.EVIDENCE_VALIDATION),
        (_L.EVIDENCE_VALIDATION, _L.REVIEW),
        (_L.REVIEW, _L.CHALLENGE),
        (_L.REVIEW, _L.ANALYSIS),
        (_L.CHALLENGE, _L.REPORTING),
        (_L.CHALLENGE, _L.REVIEW),
        (_L.CHALLENGE, _L.ANALYSIS),
        (_L.REPORTING, _L.COMPLETED),
    }
)


def is_transition_allowed(
    from_status: LifecycleStatus,
    to_status: LifecycleStatus,
) -> bool:
    """Return True if the transition from *from_status* to *to_status* is legal."""
    if from_status in _TERMINAL:
        return False
    if to_status in {_L.FAILED, _L.ABORTED}:
        return True
    return (from_status, to_status) in _ALLOWED


def validate_transition(
    from_status: LifecycleStatus,
    to_status: LifecycleStatus,
) -> None:
    """Raise :class:`TransitionError` if the transition is not allowed."""
    if not is_transition_allowed(from_status, to_status):
        raise TransitionError(
            f"Lifecycle transition {from_status.value!r} → {to_status.value!r}"
            " is not allowed"
        )
