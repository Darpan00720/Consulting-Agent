"""Tests for the governance gate validators (packages/governance/gates.py).

All tests are deterministic and filesystem-free.
"""

from __future__ import annotations

import pytest

from governance import (
    GateCheckResult,
    GovernanceGateError,
    check_challenger_can_run,
    check_reporting_gate,
    check_reviewer_can_run,
    enforce_challenger_gate,
    enforce_reporting_gate,
    enforce_reviewer_gate,
)
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta() -> EngagementMetadata:
    return EngagementMetadata(
        engagement_id=EngagementId("eng_gate_test"),
        tenant_id="t_test",
        slug="gate-test",
    )


def _base_state() -> EngagementState:
    return EngagementState(metadata=_meta())


def _node(
    question: str,
    owner: str | None = "financial-analyst",
    parent: str | None = None,
    status: IssueNodeStatus = IssueNodeStatus.ANSWERED,
    nid: str | None = None,
) -> IssueNode:
    kwargs: dict[str, object] = {
        "question": question,
        "owner": owner,
        "status": status,
    }
    if parent is not None:
        kwargs["parent"] = parent
    node = IssueNode(**kwargs)  # type: ignore[arg-type]
    if nid is not None:
        node = node.model_copy(update={"id": IssueNodeId(nid)})
    return node


def _analysis_block() -> AnalysisBlock:
    return AnalysisBlock(
        owner="financial-analyst",
        findings=[
            Finding(
                question="Is margin declining?",
                answer="Yes, by 5%.",
                evidence_refs=["ev_001"],
                confidence=0.8,
            )
        ],
        status=AnalysisStatus.COMPLETE,
    )


def _reviewer_approved() -> ReviewerNotes:
    return ReviewerNotes(verdict=ReviewVerdict.APPROVED)


def _challenger_stands() -> ChallengeNotes:
    return ChallengeNotes(verdict=ChallengeVerdict.STANDS)


def _state_ready_for_reviewer() -> EngagementState:
    root = _node(
        "Is profit declining?",
        owner=None,
        status=IssueNodeStatus.ANSWERED,
        nid="root",
    )
    leaf = _node(
        "Is price declining?",
        owner="financial-analyst",
        parent="root",
        status=IssueNodeStatus.ANSWERED,
    )
    return _base_state().model_copy(
        update={
            "issue_tree": [root, leaf],
            "financial_analysis": _analysis_block(),
        }
    )


# ---------------------------------------------------------------------------
# check_reviewer_can_run
# ---------------------------------------------------------------------------


class TestCheckReviewerCanRun:
    def test_empty_issue_tree_fails(self) -> None:
        result = check_reviewer_can_run(_base_state())
        assert not result.passed

    def test_unanswered_leaf_fails(self) -> None:
        leaf = _node(
            "Is price declining?",
            owner="financial-analyst",
            status=IssueNodeStatus.OPEN,
        )
        state = _base_state().model_copy(
            update={
                "issue_tree": [leaf],
                "financial_analysis": _analysis_block(),
            }
        )
        result = check_reviewer_can_run(state)
        assert not result.passed
        assert "answered" in result.reason.lower()

    def test_no_analysis_blocks_fails(self) -> None:
        leaf = _node(
            "Is price declining?",
            owner="financial-analyst",
            status=IssueNodeStatus.ANSWERED,
        )
        state = _base_state().model_copy(update={"issue_tree": [leaf]})
        result = check_reviewer_can_run(state)
        assert not result.passed
        assert "analysis" in result.reason.lower()

    def test_all_conditions_met_passes(self) -> None:
        result = check_reviewer_can_run(_state_ready_for_reviewer())
        assert result.passed, result.reason


# ---------------------------------------------------------------------------
# check_challenger_can_run
# ---------------------------------------------------------------------------


class TestCheckChallengerCanRun:
    def test_no_reviewer_notes_fails(self) -> None:
        result = check_challenger_can_run(_base_state())
        assert not result.passed
        assert "reviewer" in result.reason.lower()

    def test_reviewer_needs_rework_fails(self) -> None:
        state = _base_state().model_copy(
            update={
                "reviewer_notes": ReviewerNotes(
                    verdict=ReviewVerdict.NEEDS_REWORK
                )
            }
        )
        result = check_challenger_can_run(state)
        assert not result.passed

    def test_reviewer_approved_passes(self) -> None:
        state = _base_state().model_copy(
            update={"reviewer_notes": _reviewer_approved()}
        )
        result = check_challenger_can_run(state)
        assert result.passed, result.reason


# ---------------------------------------------------------------------------
# check_reporting_gate
# ---------------------------------------------------------------------------


class TestCheckReportingGate:
    def test_reviewer_not_approved_fails(self) -> None:
        state = _base_state().model_copy(
            update={
                "reviewer_notes": ReviewerNotes(
                    verdict=ReviewVerdict.NEEDS_REWORK
                ),
                "challenge_notes": _challenger_stands(),
            }
        )
        result = check_reporting_gate(state)
        assert not result.passed

    def test_challenger_needs_rework_fails(self) -> None:
        state = _base_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": ChallengeNotes(
                    verdict=ChallengeVerdict.NEEDS_REWORK
                ),
            }
        )
        result = check_reporting_gate(state)
        assert not result.passed

    def test_both_gates_pass(self) -> None:
        state = _base_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": _challenger_stands(),
            }
        )
        result = check_reporting_gate(state)
        assert result.passed, result.reason

    def test_stands_with_caveats_passes(self) -> None:
        state = _base_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": ChallengeNotes(
                    verdict=ChallengeVerdict.STANDS_WITH_CAVEATS
                ),
            }
        )
        result = check_reporting_gate(state)
        assert result.passed, result.reason

    def test_no_challenge_notes_fails(self) -> None:
        state = _base_state().model_copy(
            update={"reviewer_notes": _reviewer_approved()}
        )
        result = check_reporting_gate(state)
        assert not result.passed
        assert "challenge" in result.reason.lower()


# ---------------------------------------------------------------------------
# enforce_ variants raise GovernanceGateError
# ---------------------------------------------------------------------------


class TestEnforceGates:
    def test_enforce_reviewer_gate_raises_on_fail(self) -> None:
        with pytest.raises(GovernanceGateError):
            enforce_reviewer_gate(_base_state())

    def test_enforce_reviewer_gate_passes_silently(self) -> None:
        enforce_reviewer_gate(_state_ready_for_reviewer())

    def test_enforce_challenger_gate_raises_on_fail(self) -> None:
        with pytest.raises(GovernanceGateError):
            enforce_challenger_gate(_base_state())

    def test_enforce_challenger_gate_passes_silently(self) -> None:
        state = _base_state().model_copy(
            update={"reviewer_notes": _reviewer_approved()}
        )
        enforce_challenger_gate(state)

    def test_enforce_reporting_gate_raises_on_fail(self) -> None:
        with pytest.raises(GovernanceGateError):
            enforce_reporting_gate(_base_state())

    def test_enforce_reporting_gate_passes_silently(self) -> None:
        state = _base_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": _challenger_stands(),
            }
        )
        enforce_reporting_gate(state)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_gate_check_result_type() -> None:
    result = check_reviewer_can_run(_base_state())
    assert isinstance(result, GateCheckResult)
    assert isinstance(result.passed, bool)
    assert isinstance(result.reason, str)
