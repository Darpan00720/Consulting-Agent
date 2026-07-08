"""Tests for planning-phase precondition gate validators.

All tests are deterministic and filesystem-free. Each test constructs a
minimal EngagementState and asserts the gate returns the expected result.
"""

from __future__ import annotations

from common.values import ConfidenceScore  # noqa: F401 — exported for test clarity
from planning import (
    GateCheckResult,
    check_enter_analysis,
    check_enter_governance,
    check_enter_planning,
    check_enter_reporting,
)
from state.identifiers import EngagementId, IssueNodeId
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.enums import (
    AnalysisStatus,
    CaseArchetype,
    ChallengeVerdict,
    IssueNodeStatus,
    ReviewVerdict,
)
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.planning import EngagementPlan, IssueNode, PlanStep
from state.sections.scoping import CaseClassification, ProblemDefinition

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _meta() -> EngagementMetadata:
    return EngagementMetadata(
        engagement_id=EngagementId("eng_test"),
        tenant_id="t_test",
        slug="test-engagement",
    )


def _bare_state() -> EngagementState:
    return EngagementState(metadata=_meta())


def _classified_state() -> EngagementState:
    state = _bare_state()
    return state.model_copy(
        update={
            "problem": ProblemDefinition(
                raw_input="Client profits have fallen 30%.",
                real_question="Is the profit decline driven by price or volume?",
            ),
            "classification": CaseClassification(
                primary_archetype=CaseArchetype.PROFITABILITY,
                confidence=0.9,
            ),
        }
    )


def _node(
    question: str,
    owner: str | None = "financial-analyst",
    parent: str | None = None,
    nid: str | None = None,
    status: IssueNodeStatus = IssueNodeStatus.OPEN,
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


def _plan_with_steps() -> EngagementPlan:
    return EngagementPlan(
        steps=[
            PlanStep(
                description="Run financial analysis",
                agent="financial-analyst",
            )
        ]
    )


def _reviewer_approved() -> ReviewerNotes:
    return ReviewerNotes(verdict=ReviewVerdict.APPROVED)


def _challenger_stands() -> ChallengeNotes:
    return ChallengeNotes(verdict=ChallengeVerdict.STANDS)


def _financial_block() -> AnalysisBlock:
    return AnalysisBlock(
        owner="financial-analyst",
        findings=[
            Finding(
                question="Is margin declining due to price?",
                answer="Yes, price fell 5%.",
                evidence_refs=["ev_001"],
                confidence=0.8,
            )
        ],
        status=AnalysisStatus.COMPLETE,
    )


# ---------------------------------------------------------------------------
# check_enter_planning
# ---------------------------------------------------------------------------


class TestCheckEnterPlanning:
    def test_no_classification_fails(self) -> None:
        result = check_enter_planning(_bare_state())
        assert not result.passed
        assert "Case Classifier" in result.reason

    def test_no_real_question_fails(self) -> None:
        state = _bare_state().model_copy(
            update={
                "classification": CaseClassification(
                    primary_archetype=CaseArchetype.PROFITABILITY,
                    confidence=0.9,
                ),
                "problem": ProblemDefinition(
                    raw_input="Problem.", real_question=None
                ),
            }
        )
        result = check_enter_planning(state)
        assert not result.passed

    def test_classified_with_question_passes(self) -> None:
        result = check_enter_planning(_classified_state())
        assert result.passed
        assert result.reason == "ok"


# ---------------------------------------------------------------------------
# check_enter_analysis
# ---------------------------------------------------------------------------


class TestCheckEnterAnalysis:
    def test_no_issue_tree_fails(self) -> None:
        result = check_enter_analysis(_classified_state())
        assert not result.passed
        assert "issue_tree" in result.reason

    def test_no_plan_fails(self) -> None:
        root = _node("Is profit declining?", owner=None, nid="root")
        leaf = _node(
            "Is price declining?", owner="financial-analyst", parent="root"
        )
        state = _classified_state().model_copy(
            update={"issue_tree": [root, leaf]}
        )
        result = check_enter_analysis(state)
        assert not result.passed
        assert "plan" in result.reason.lower()

    def test_leaf_without_owner_fails(self) -> None:
        root = _node("Is profit declining?", owner=None, nid="root")
        leaf = _node(
            "Is price declining?", owner=None, parent="root"
        )
        state = _classified_state().model_copy(
            update={
                "issue_tree": [root, leaf],
                "plan": _plan_with_steps(),
            }
        )
        result = check_enter_analysis(state)
        assert not result.passed
        assert "owner" in result.reason.lower()

    def test_fully_owned_tree_with_plan_passes(self) -> None:
        root = _node("Is profit declining?", owner=None, nid="root")
        leaf = _node(
            "Is price declining?", owner="financial-analyst", parent="root"
        )
        state = _classified_state().model_copy(
            update={
                "issue_tree": [root, leaf],
                "plan": _plan_with_steps(),
            }
        )
        result = check_enter_analysis(state)
        assert result.passed, result.reason


# ---------------------------------------------------------------------------
# check_enter_governance
# ---------------------------------------------------------------------------


class TestCheckEnterGovernance:
    def test_no_issue_tree_fails(self) -> None:
        result = check_enter_governance(_classified_state())
        assert not result.passed

    def test_unanswered_leaves_fail(self) -> None:
        root = _node("Is profit declining?", owner=None, nid="root")
        leaf = _node(
            "Is price declining?",
            owner="financial-analyst",
            parent="root",
            status=IssueNodeStatus.OPEN,
        )
        state = _classified_state().model_copy(
            update={"issue_tree": [root, leaf]}
        )
        result = check_enter_governance(state)
        assert not result.passed
        assert "not yet answered" in result.reason

    def test_answered_leaves_but_no_analysis_fails(self) -> None:
        root = _node("Is profit declining?", owner=None, nid="root")
        leaf = _node(
            "Is price declining?",
            owner="financial-analyst",
            parent="root",
            status=IssueNodeStatus.ANSWERED,
        )
        state = _classified_state().model_copy(
            update={"issue_tree": [root, leaf]}
        )
        result = check_enter_governance(state)
        assert not result.passed
        assert "analysis" in result.reason.lower()

    def test_answered_leaves_with_analysis_passes(self) -> None:
        root = _node("Is profit declining?", owner=None, nid="root")
        leaf = _node(
            "Is price declining?",
            owner="financial-analyst",
            parent="root",
            status=IssueNodeStatus.ANSWERED,
        )
        state = _classified_state().model_copy(
            update={
                "issue_tree": [root, leaf],
                "financial_analysis": _financial_block(),
            }
        )
        result = check_enter_governance(state)
        assert result.passed, result.reason


# ---------------------------------------------------------------------------
# check_enter_reporting
# ---------------------------------------------------------------------------


class TestCheckEnterReporting:
    def test_no_reviewer_notes_fails(self) -> None:
        result = check_enter_reporting(_classified_state())
        assert not result.passed
        assert "reviewer_notes" in result.reason

    def test_reviewer_needs_rework_fails(self) -> None:
        state = _classified_state().model_copy(
            update={
                "reviewer_notes": ReviewerNotes(
                    verdict=ReviewVerdict.NEEDS_REWORK
                )
            }
        )
        result = check_enter_reporting(state)
        assert not result.passed
        assert "approved" in result.reason

    def test_no_challenge_notes_fails(self) -> None:
        state = _classified_state().model_copy(
            update={"reviewer_notes": _reviewer_approved()}
        )
        result = check_enter_reporting(state)
        assert not result.passed
        assert "challenge_notes" in result.reason

    def test_challenger_needs_rework_fails(self) -> None:
        state = _classified_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": ChallengeNotes(
                    verdict=ChallengeVerdict.NEEDS_REWORK
                ),
            }
        )
        result = check_enter_reporting(state)
        assert not result.passed

    def test_both_gates_cleared_passes(self) -> None:
        state = _classified_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": _challenger_stands(),
            }
        )
        result = check_enter_reporting(state)
        assert result.passed, result.reason

    def test_stands_with_caveats_also_passes(self) -> None:
        state = _classified_state().model_copy(
            update={
                "reviewer_notes": _reviewer_approved(),
                "challenge_notes": ChallengeNotes(
                    verdict=ChallengeVerdict.STANDS_WITH_CAVEATS
                ),
            }
        )
        result = check_enter_reporting(state)
        assert result.passed, result.reason


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_gate_check_result_type() -> None:
    result = check_enter_planning(_bare_state())
    assert isinstance(result, GateCheckResult)
    assert isinstance(result.passed, bool)
    assert isinstance(result.reason, str)
