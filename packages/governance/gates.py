"""Governance gate validators — Reviewer and Challenger (ADR-002 §2, ADR-005).

These enforce the two mandatory quality gates that must pass before the
Executive Report Writer may run.  No agent may self-approve its own output:
the Reviewer reviews the analysts' work; the Challenger reviews the full
recommendation.

Gate contracts (from ADR-002 §2 and ADR-005 Governance):
  Reviewer precondition:
    - Every leaf node in the issue tree is answered.
    - At least one analysis block is present.
  Reviewer postcondition (written by the Reviewer agent):
    - reviewer_notes.verdict ∈ {approved, needs_rework}.
  Challenger precondition:
    - reviewer_notes.verdict == approved.
  Challenger postcondition (written by the Challenger agent):
    - challenge_notes.verdict ∈ {stands, stands_with_caveats, needs_rework}.
  Reporting gate (both must clear):
    - reviewer approved AND challenger stands/stands_with_caveats.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.errors import StratAgentError
from state.models import EngagementState
from state.sections.enums import IssueNodeStatus


class GovernanceGateError(StratAgentError):
    """Raised when a governance gate precondition is violated."""


@dataclass(frozen=True)
class GateCheckResult:
    """Outcome of a governance gate check."""

    passed: bool
    reason: str


# ---------------------------------------------------------------------------
# Reviewer gate
# ---------------------------------------------------------------------------


def check_reviewer_can_run(state: EngagementState) -> GateCheckResult:
    """Verify that all Reviewer preconditions are met."""
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
            "no analysis blocks present — run at least one specialist analyst",
        )
    return GateCheckResult(True, "ok")


def enforce_reviewer_gate(state: EngagementState) -> None:
    """Raise :class:`GovernanceGateError` if Reviewer preconditions are not met."""
    result = check_reviewer_can_run(state)
    if not result.passed:
        raise GovernanceGateError(f"Reviewer gate failed: {result.reason}")


# ---------------------------------------------------------------------------
# Challenger gate
# ---------------------------------------------------------------------------


def check_challenger_can_run(state: EngagementState) -> GateCheckResult:
    """Verify that Reviewer has approved before Challenger runs."""
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
                " not 'approved' — Reviewer gate not cleared"
            ),
        )
    return GateCheckResult(True, "ok")


def enforce_challenger_gate(state: EngagementState) -> None:
    """Raise :class:`GovernanceGateError` if Challenger preconditions are not met."""
    result = check_challenger_can_run(state)
    if not result.passed:
        raise GovernanceGateError(f"Challenger gate failed: {result.reason}")


# ---------------------------------------------------------------------------
# Reporting gate (both gates must clear)
# ---------------------------------------------------------------------------


def check_reporting_gate(state: EngagementState) -> GateCheckResult:
    """Verify that both governance gates have cleared before Report Writer runs."""
    reviewer_result = check_challenger_can_run(state)  # implicitly checks reviewer
    if not reviewer_result.passed:
        return reviewer_result

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


def enforce_reporting_gate(state: EngagementState) -> None:
    """Raise :class:`GovernanceGateError` if reporting gate is not cleared."""
    result = check_reporting_gate(state)
    if not result.passed:
        raise GovernanceGateError(f"Reporting gate failed: {result.reason}")
