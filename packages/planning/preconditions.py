"""Precondition gate validators for planning-phase state transitions (ADR-002 §2).

Each function checks whether an engagement's current state satisfies the
entry conditions for the next lifecycle phase.  They return a
:class:`GateCheckResult` rather than raising, so callers can decide how to
handle a failing gate (log, escalate to human, retry, etc.).

Forbidden transitions from ADR-002:
  REPORTING unreachable without Reviewer approved + Challenger cleared.
  Entering ANALYSIS requires a non-empty, fully-owned issue tree + a plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.errors import StratAgentError
from state.models import EngagementState
from state.sections.enums import IssueNodeStatus


class PlanningGateError(StratAgentError):
    """Raised when a planning precondition is violated (caller opted to raise)."""


@dataclass(frozen=True)
class GateCheckResult:
    """Outcome of a precondition gate check."""

    passed: bool
    reason: str


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------


def check_enter_planning(state: EngagementState) -> GateCheckResult:
    """Case Classifier postcondition: classification + real_question present."""
    if state.classification is None:
        return GateCheckResult(
            False,
            "case_type not set — Case Classifier must run first",
        )
    if state.problem is None or not state.problem.real_question:
        return GateCheckResult(
            False,
            "real_question not set — Case Classifier must run first",
        )
    return GateCheckResult(True, "ok")


def check_enter_analysis(state: EngagementState) -> GateCheckResult:
    """Issue Tree Generator + Planner postcondition: tree with owned leaves + plan."""
    if not state.issue_tree:
        return GateCheckResult(
            False,
            "issue_tree is empty — Issue Tree Generator must run first",
        )
    if state.plan is None or not state.plan.steps:
        return GateCheckResult(
            False,
            "engagement_plan is empty — Planner must run first",
        )
    parent_ids: set[str] = {n.parent for n in state.issue_tree if n.parent is not None}
    leaves = [n for n in state.issue_tree if n.id not in parent_ids]
    unowned = [n for n in leaves if not n.owner]
    if unowned:
        return GateCheckResult(
            False,
            (
                f"{len(unowned)} leaf node(s) have no owner;"
                " assign owners before entering analysis"
            ),
        )
    return GateCheckResult(True, "ok")


def check_enter_governance(state: EngagementState) -> GateCheckResult:
    """Analysis completion gate: all leaf nodes answered + ≥1 analysis block."""
    if not state.issue_tree:
        return GateCheckResult(False, "issue_tree is empty")
    parent_ids: set[str] = {n.parent for n in state.issue_tree if n.parent is not None}
    leaves = [n for n in state.issue_tree if n.id not in parent_ids]
    unanswered = [n for n in leaves if n.status != IssueNodeStatus.ANSWERED]
    if unanswered:
        return GateCheckResult(
            False,
            f"{len(unanswered)} leaf node(s) not yet answered",
        )
    has_analysis = any(
        [
            state.financial_analysis,
            state.market_analysis,
            state.operations_analysis,
            state.strategy_analysis,
            state.risk_analysis,
        ]
    )
    if not has_analysis:
        return GateCheckResult(
            False,
            "no analysis blocks present — at least one specialist must run",
        )
    return GateCheckResult(True, "ok")


def check_enter_reporting(state: EngagementState) -> GateCheckResult:
    """Reporting gate: Reviewer approved AND Challenger cleared (ADR-002 §2)."""
    if state.reviewer_notes is None:
        return GateCheckResult(
            False,
            "reviewer_notes not set — Reviewer must run first",
        )
    if state.reviewer_notes.verdict is None:
        return GateCheckResult(False, "reviewer verdict not set")
    if state.reviewer_notes.verdict.value != "approved":
        return GateCheckResult(
            False,
            (
                f"reviewer verdict is {state.reviewer_notes.verdict.value!r},"
                " not 'approved'"
            ),
        )
    if state.challenge_notes is None:
        return GateCheckResult(
            False,
            "challenge_notes not set — Challenger must run first",
        )
    if state.challenge_notes.verdict is None:
        return GateCheckResult(False, "challenger verdict not set")
    allowed = {"stands", "stands_with_caveats"}
    if state.challenge_notes.verdict.value not in allowed:
        return GateCheckResult(
            False,
            (
                f"challenger verdict is"
                f" {state.challenge_notes.verdict.value!r},"
                f" must be one of {sorted(allowed)}"
            ),
        )
    return GateCheckResult(True, "ok")
