"""Integration tests: engagement lifecycle state machine (M7 / M8).

Validates the full ADR-002 LifecycleStatus transition graph:
  - Legal forward transitions
  - Rework loops (REVIEW → ANALYSIS, CHALLENGE → REVIEW, CHALLENGE → ANALYSIS)
  - Terminal state exits are forbidden
  - Any non-terminal → FAILED / ABORTED is always allowed
  - Governance preconditions hold at state boundaries
"""

from __future__ import annotations

import pytest

from governance import (
    GovernanceGateError,
    TransitionError,
    check_challenger_can_run,
    check_reporting_gate,
    check_reviewer_can_run,
    enforce_challenger_gate,
    enforce_reporting_gate,
    enforce_reviewer_gate,
    is_transition_allowed,
    validate_transition,
)
from state.enums import LifecycleStatus
from state.identifiers import EngagementId, IssueNodeId
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.enums import (
    AnalysisStatus,
    ChallengeVerdict,
    IssueNodeStatus,
    ReviewVerdict,
)
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.planning import IssueNode
from tests.fixtures.golden_state import make_golden_profitability_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS = LifecycleStatus


def _meta() -> EngagementMetadata:
    return EngagementMetadata(
        engagement_id=EngagementId("eng_lifecycle_test"),
        tenant_id="t_lifecycle",
        slug="lifecycle-test",
    )


def _base() -> EngagementState:
    return EngagementState(metadata=_meta())


def _leaf_answered(nid: str = "n_leaf") -> IssueNode:
    node = IssueNode(
        question="Is margin declining?",
        owner="financial-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer="Yes.",
    )
    return node.model_copy(update={"id": IssueNodeId(nid)})


def _analysis_block() -> AnalysisBlock:
    return AnalysisBlock(
        owner="financial-analyst",
        findings=[
            Finding(
                question="Is revenue declining?",
                answer="Yes.",
                evidence_refs=["ev_001"],
                confidence=0.9,
            )
        ],
        status=AnalysisStatus.COMPLETE,
    )


# ---------------------------------------------------------------------------
# Forward transitions — happy path
# ---------------------------------------------------------------------------

_FORWARD_PATH: list[tuple[LifecycleStatus, LifecycleStatus]] = [
    (_STATUS.INTAKE, _STATUS.CLASSIFYING),
    (_STATUS.CLASSIFYING, _STATUS.GAP_ANALYSIS),
    (_STATUS.GAP_ANALYSIS, _STATUS.PLANNING),
    (_STATUS.PLANNING, _STATUS.FRAMING),
    (_STATUS.FRAMING, _STATUS.ISSUE_TREE),
    (_STATUS.ISSUE_TREE, _STATUS.KNOWLEDGE),
    (_STATUS.KNOWLEDGE, _STATUS.ANALYSIS),
    (_STATUS.ANALYSIS, _STATUS.EVIDENCE_VALIDATION),
    (_STATUS.EVIDENCE_VALIDATION, _STATUS.REVIEW),
    (_STATUS.REVIEW, _STATUS.CHALLENGE),
    (_STATUS.CHALLENGE, _STATUS.REPORTING),
    (_STATUS.REPORTING, _STATUS.COMPLETED),
]


@pytest.mark.parametrize("from_s,to_s", _FORWARD_PATH)
def test_forward_path_is_allowed(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    assert is_transition_allowed(from_s, to_s), f"{from_s} → {to_s} should be allowed"


@pytest.mark.parametrize("from_s,to_s", _FORWARD_PATH)
def test_forward_path_validate_does_not_raise(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    validate_transition(from_s, to_s)  # must not raise


# ---------------------------------------------------------------------------
# Rework loops
# ---------------------------------------------------------------------------

_REWORK_LOOPS: list[tuple[LifecycleStatus, LifecycleStatus]] = [
    (_STATUS.REVIEW, _STATUS.ANALYSIS),
    (_STATUS.CHALLENGE, _STATUS.REVIEW),
    (_STATUS.CHALLENGE, _STATUS.ANALYSIS),
]


@pytest.mark.parametrize("from_s,to_s", _REWORK_LOOPS)
def test_rework_loops_are_allowed(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    assert is_transition_allowed(
        from_s, to_s
    ), f"Rework loop {from_s} → {to_s} should be allowed"


# ---------------------------------------------------------------------------
# Forbidden shortcuts (governance gate bypass)
# ---------------------------------------------------------------------------

_FORBIDDEN: list[tuple[LifecycleStatus, LifecycleStatus]] = [
    (_STATUS.INTAKE, _STATUS.ANALYSIS),
    (_STATUS.CLASSIFYING, _STATUS.REPORTING),
    (_STATUS.REVIEW, _STATUS.REPORTING),  # must go through CHALLENGE first
    (_STATUS.INTAKE, _STATUS.COMPLETED),
    (_STATUS.PLANNING, _STATUS.REVIEW),
    # must go through EVIDENCE_VALIDATION + REVIEW
    (_STATUS.ANALYSIS, _STATUS.CHALLENGE),
]


@pytest.mark.parametrize("from_s,to_s", _FORBIDDEN)
def test_forbidden_transitions_not_allowed(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    assert not is_transition_allowed(from_s, to_s)


@pytest.mark.parametrize("from_s,to_s", _FORBIDDEN)
def test_forbidden_transitions_raise_on_validate(
    from_s: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    with pytest.raises(TransitionError):
        validate_transition(from_s, to_s)


# ---------------------------------------------------------------------------
# Terminal states cannot be exited
# ---------------------------------------------------------------------------

_TERMINAL = [_STATUS.COMPLETED, _STATUS.FAILED, _STATUS.ABORTED]
_ALL_NON_TERMINAL = [s for s in LifecycleStatus if s not in _TERMINAL]


@pytest.mark.parametrize("terminal", _TERMINAL)
@pytest.mark.parametrize("to_s", [_STATUS.INTAKE, _STATUS.ANALYSIS, _STATUS.REPORTING])
def test_terminal_states_cannot_transition(
    terminal: LifecycleStatus, to_s: LifecycleStatus
) -> None:
    assert not is_transition_allowed(terminal, to_s)


# ---------------------------------------------------------------------------
# Any non-terminal → FAILED / ABORTED is always allowed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("from_s", _ALL_NON_TERMINAL)
def test_any_non_terminal_can_fail(from_s: LifecycleStatus) -> None:
    assert is_transition_allowed(from_s, _STATUS.FAILED)


@pytest.mark.parametrize("from_s", _ALL_NON_TERMINAL)
def test_any_non_terminal_can_abort(from_s: LifecycleStatus) -> None:
    assert is_transition_allowed(from_s, _STATUS.ABORTED)


# ---------------------------------------------------------------------------
# Governance gate preconditions
# ---------------------------------------------------------------------------


class TestReviewerGatePreconditions:
    def test_no_issue_tree_blocks_reviewer(self) -> None:
        result = check_reviewer_can_run(_base())
        assert not result.passed

    def test_no_analysis_blocks_reviewer(self) -> None:
        state = _base().model_copy(update={"issue_tree": [_leaf_answered()]})
        result = check_reviewer_can_run(state)
        assert not result.passed

    def test_all_preconditions_pass(self) -> None:
        state = _base().model_copy(
            update={
                "issue_tree": [_leaf_answered()],
                "financial_analysis": _analysis_block(),
            }
        )
        result = check_reviewer_can_run(state)
        assert result.passed, result.reason

    def test_enforce_raises_without_preconditions(self) -> None:
        with pytest.raises(GovernanceGateError):
            enforce_reviewer_gate(_base())


class TestChallengerGatePreconditions:
    def test_no_reviewer_verdict_blocks_challenger(self) -> None:
        result = check_challenger_can_run(_base())
        assert not result.passed

    def test_needs_rework_verdict_blocks_challenger(self) -> None:
        state = _base().model_copy(
            update={"reviewer_notes": ReviewerNotes(verdict=ReviewVerdict.NEEDS_REWORK)}
        )
        result = check_challenger_can_run(state)
        assert not result.passed

    def test_approved_verdict_allows_challenger(self) -> None:
        state = _base().model_copy(
            update={"reviewer_notes": ReviewerNotes(verdict=ReviewVerdict.APPROVED)}
        )
        result = check_challenger_can_run(state)
        assert result.passed, result.reason

    def test_enforce_raises_without_approval(self) -> None:
        with pytest.raises(GovernanceGateError):
            enforce_challenger_gate(_base())


class TestReportingGatePreconditions:
    def test_missing_both_gates_blocks_reporting(self) -> None:
        result = check_reporting_gate(_base())
        assert not result.passed

    def test_only_reviewer_approved_is_insufficient(self) -> None:
        state = _base().model_copy(
            update={"reviewer_notes": ReviewerNotes(verdict=ReviewVerdict.APPROVED)}
        )
        result = check_reporting_gate(state)
        assert not result.passed

    def test_stands_with_caveats_allows_reporting(self) -> None:
        state = _base().model_copy(
            update={
                "reviewer_notes": ReviewerNotes(verdict=ReviewVerdict.APPROVED),
                "challenge_notes": ChallengeNotes(
                    verdict=ChallengeVerdict.STANDS_WITH_CAVEATS
                ),
            }
        )
        result = check_reporting_gate(state)
        assert result.passed, result.reason

    def test_enforce_reporting_raises_without_gates(self) -> None:
        with pytest.raises(GovernanceGateError):
            enforce_reporting_gate(_base())


# ---------------------------------------------------------------------------
# Golden state satisfies all governance gates
# ---------------------------------------------------------------------------


def test_golden_state_passes_all_governance_gates() -> None:
    state = make_golden_profitability_state()
    assert check_reviewer_can_run(state).passed
    assert check_challenger_can_run(state).passed
    assert check_reporting_gate(state).passed


def test_golden_state_reviewer_approved() -> None:
    state = make_golden_profitability_state()
    assert state.reviewer_notes is not None
    assert state.reviewer_notes.verdict == ReviewVerdict.APPROVED


def test_golden_state_challenger_stands_with_caveats() -> None:
    state = make_golden_profitability_state()
    assert state.challenge_notes is not None
    assert state.challenge_notes.verdict == ChallengeVerdict.STANDS_WITH_CAVEATS


def test_golden_state_completed_status() -> None:
    state = make_golden_profitability_state()
    assert state.status == LifecycleStatus.COMPLETED
