"""Tests for the lifecycle state-machine transition validator.

All tests are deterministic and require no filesystem access.
"""

from __future__ import annotations

import pytest

from governance import TransitionError, is_transition_allowed, validate_transition
from state.enums import LifecycleStatus

_L = LifecycleStatus


# ---------------------------------------------------------------------------
# Allowed transitions (positive tests)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_s, to_s",
    [
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
        (_L.CHALLENGE, _L.REPORTING),
        (_L.REPORTING, _L.COMPLETED),
    ],
)
def test_happy_path_transitions_allowed(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    assert is_transition_allowed(from_s, to_s), f"{from_s} → {to_s} should be allowed"


# ---------------------------------------------------------------------------
# Rework loops
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_s, to_s",
    [
        (_L.REVIEW, _L.ANALYSIS),
        (_L.CHALLENGE, _L.REVIEW),
        (_L.CHALLENGE, _L.ANALYSIS),
    ],
)
def test_rework_loop_transitions_allowed(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    assert is_transition_allowed(from_s, to_s), (
        f"Rework loop {from_s} → {to_s} should be allowed"
    )


# ---------------------------------------------------------------------------
# Terminal → FAILED / ABORTED allowed from any non-terminal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_s",
    [
        _L.INTAKE,
        _L.CLASSIFYING,
        _L.GAP_ANALYSIS,
        _L.PLANNING,
        _L.ANALYSIS,
        _L.REVIEW,
        _L.CHALLENGE,
        _L.REPORTING,
    ],
)
def test_any_non_terminal_can_abort(from_s: LifecycleStatus) -> None:
    assert is_transition_allowed(from_s, _L.ABORTED)
    assert is_transition_allowed(from_s, _L.FAILED)


# ---------------------------------------------------------------------------
# Terminal states cannot be left
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "terminal",
    [_L.COMPLETED, _L.FAILED, _L.ABORTED],
)
def test_terminal_states_cannot_transition(terminal: LifecycleStatus) -> None:
    for to_s in LifecycleStatus:
        assert not is_transition_allowed(terminal, to_s), (
            f"Terminal {terminal} should not transition to {to_s}"
        )


# ---------------------------------------------------------------------------
# Forbidden: skipping governance gates
# ---------------------------------------------------------------------------


def test_review_cannot_jump_to_reporting() -> None:
    assert not is_transition_allowed(_L.REVIEW, _L.REPORTING)


def test_analysis_cannot_jump_to_reporting() -> None:
    assert not is_transition_allowed(_L.ANALYSIS, _L.REPORTING)


def test_intake_cannot_jump_to_reporting() -> None:
    assert not is_transition_allowed(_L.INTAKE, _L.REPORTING)


def test_intake_cannot_jump_to_completed() -> None:
    assert not is_transition_allowed(_L.INTAKE, _L.COMPLETED)


# ---------------------------------------------------------------------------
# validate_transition raises TransitionError on forbidden
# ---------------------------------------------------------------------------


def test_validate_transition_raises_on_forbidden() -> None:
    with pytest.raises(TransitionError, match="not allowed"):
        validate_transition(_L.INTAKE, _L.REPORTING)


def test_validate_transition_raises_on_terminal_exit() -> None:
    with pytest.raises(TransitionError):
        validate_transition(_L.COMPLETED, _L.REPORTING)


def test_validate_transition_passes_silently_on_allowed() -> None:
    validate_transition(_L.INTAKE, _L.CLASSIFYING)


def test_validate_transition_returns_none() -> None:
    result = validate_transition(_L.REVIEW, _L.CHALLENGE)
    assert result is None


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_query_same_result() -> None:
    r1 = is_transition_allowed(_L.REVIEW, _L.REPORTING)
    r2 = is_transition_allowed(_L.REVIEW, _L.REPORTING)
    assert r1 == r2
