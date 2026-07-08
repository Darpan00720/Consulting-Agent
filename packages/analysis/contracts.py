"""Analysis block contract validators (ADR-005 Analysis agent specs).

Every specialist analyst must produce evidence-backed findings.  These
validators check the post-conditions of an :class:`AnalysisBlock` so the
Reviewer agent can rely on structural guarantees rather than repeating the
same checks for each block.

Contract rules (from ADR-005 Analysis category):
  1. Block must have at least one finding.
  2. Every finding that carries an answer must cite ≥1 evidence or assumption ref.
  3. No finding may have an answer of None in a COMPLETE block.
  4. Block status must be COMPLETE before Reviewer runs.
  5. Block must declare an owner.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.errors import StratAgentError
from state.sections.analysis import AnalysisBlock
from state.sections.enums import AnalysisStatus


class AnalysisContractError(StratAgentError):
    """Raised when an analysis block violates its agent contract."""


@dataclass(frozen=True)
class FindingViolation:
    """A contract violation on a single finding."""

    finding_index: int
    rule: str
    detail: str


@dataclass(frozen=True)
class ContractReport:
    """Result of validating an analysis block against its contract."""

    valid: bool
    block_owner: str | None
    violations: tuple[FindingViolation, ...]


# Which agent owns each analysis section (ADR-005).
ANALYST_SECTION_OWNERS: dict[str, str] = {
    "financial_analysis": "financial-analyst",
    "market_analysis": "market-analyst",
    "operations_analysis": "operations-analyst",
    "strategy_analysis": "strategy-analyst",
    "risk_analysis": "risk-analyst",
}


def validate_analysis_block(block: AnalysisBlock) -> ContractReport:
    """Validate *block* against the ADR-005 analysis agent contract.

    Returns :class:`ContractReport`; does not raise.
    """
    violations: list[FindingViolation] = []

    # Rule 1 — block must have findings.
    if not block.findings:
        violations.append(
            FindingViolation(
                -1,
                "NO_FINDINGS",
                "Analysis block carries no findings",
            )
        )

    # Rule 2 — COMPLETE block must declare an owner.
    if block.status == AnalysisStatus.COMPLETE and not block.owner:
        violations.append(
            FindingViolation(
                -1,
                "NO_OWNER",
                "Completed analysis block has no owner agent",
            )
        )

    for idx, finding in enumerate(block.findings):
        # Rule 3 — answered findings need a source.
        if finding.answer is not None:
            has_refs = bool(finding.evidence_refs or finding.assumption_refs)
            if not has_refs:
                violations.append(
                    FindingViolation(
                        idx,
                        "UNEVIDENCED_ANSWER",
                        (
                            f"Finding {idx} has an answer but no evidence_refs"
                            " or assumption_refs"
                        ),
                    )
                )

        # Rule 4 — COMPLETE blocks must have all findings answered.
        if block.status == AnalysisStatus.COMPLETE and finding.answer is None:
            violations.append(
                FindingViolation(
                    idx,
                    "UNANSWERED_FINDING",
                    (
                        f"Finding {idx} ({finding.question[:50]!r}) is"
                        " unanswered in a COMPLETE block"
                    ),
                )
            )

    return ContractReport(
        valid=not violations,
        block_owner=block.owner,
        violations=tuple(violations),
    )
