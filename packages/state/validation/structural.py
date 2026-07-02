"""Structural rules — state-shape well-formedness (ADR-002 §Invariants)."""

from __future__ import annotations

from state.models import EngagementState
from state.sections.enums import GapStatus
from state.validation._util import analysis_blocks
from state.validation.types import (
    Finding,
    ValidationGroup,
    ValidationRule,
    ViolationSeverity,
)


def _leaf_nodes_have_owner(state: EngagementState) -> list[Finding]:
    parents = {node.parent for node in state.issue_tree if node.parent}
    findings: list[Finding] = []
    for index, node in enumerate(state.issue_tree):
        if node.id not in parents and not node.owner:
            findings.append(
                Finding(
                    path=f"issue_tree[{index}].owner",
                    message=f"issue-tree leaf {node.id!r} has no owner",
                    object_id=node.id,
                )
            )
    return findings


def _findings_have_evidence(state: EngagementState) -> list[Finding]:
    findings: list[Finding] = []
    for attr, block in analysis_blocks(state):
        for index, finding in enumerate(block.findings):
            if not finding.evidence_refs:
                findings.append(
                    Finding(
                        path=f"{attr}.findings[{index}].evidence_refs",
                        message=f"finding {finding.id!r} references no evidence",
                        object_id=finding.id,
                    )
                )
    return findings


def _resolved_gaps_are_complete(state: EngagementState) -> list[Finding]:
    findings: list[Finding] = []
    for index, gap in enumerate(state.information_gaps):
        if gap.status is GapStatus.ANSWERED and not gap.resolution:
            findings.append(
                Finding(
                    path=f"information_gaps[{index}].resolution",
                    message=f"answered gap {gap.id!r} has no resolution",
                    object_id=gap.id,
                )
            )
        if gap.status is GapStatus.ASSUMED and not gap.assumption_ref:
            findings.append(
                Finding(
                    path=f"information_gaps[{index}].assumption_ref",
                    message=f"assumed gap {gap.id!r} has no assumption_ref",
                    object_id=gap.id,
                )
            )
    return findings


RULES = [
    ValidationRule(
        "STRUCT-001",
        ValidationGroup.STRUCTURAL,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules / §12",
        "Every issue-tree leaf has an owner.",
        _leaf_nodes_have_owner,
    ),
    ValidationRule(
        "STRUCT-002",
        ValidationGroup.STRUCTURAL,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "Every specialist finding references at least one evidence item.",
        _findings_have_evidence,
    ),
    ValidationRule(
        "STRUCT-003",
        ValidationGroup.STRUCTURAL,
        ViolationSeverity.ERROR,
        "ADR-002 §8",
        "Answered gaps have a resolution; assumed gaps have an assumption_ref.",
        _resolved_gaps_are_complete,
    ),
]
