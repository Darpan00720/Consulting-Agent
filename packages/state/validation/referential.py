"""Referential rules — ids resolve to existing objects (ADR-002 §Validation Rules)."""

from __future__ import annotations

from state.models import EngagementState
from state.validation._util import analysis_blocks, id_set
from state.validation.types import (
    Finding,
    ValidationGroup,
    ValidationRule,
    ViolationSeverity,
)


def _gap_assumption_refs_resolve(state: EngagementState) -> list[Finding]:
    known = id_set(state.assumptions)
    findings: list[Finding] = []
    for index, gap in enumerate(state.information_gaps):
        if gap.assumption_ref and gap.assumption_ref not in known:
            findings.append(
                Finding(
                    path=f"information_gaps[{index}].assumption_ref",
                    message=f"unknown assumption ref {gap.assumption_ref!r}",
                    object_id=gap.id,
                )
            )
    return findings


def _finding_refs_resolve(state: EngagementState) -> list[Finding]:
    evidence_ids = id_set(state.evidence)
    assumption_ids = id_set(state.assumptions)
    findings: list[Finding] = []
    for attr, block in analysis_blocks(state):
        for index, finding in enumerate(block.findings):
            for ref in finding.evidence_refs:
                if ref not in evidence_ids:
                    findings.append(
                        Finding(
                            path=f"{attr}.findings[{index}].evidence_refs",
                            message=f"unknown evidence ref {ref!r}",
                            object_id=finding.id,
                        )
                    )
            for ref in finding.assumption_refs:
                if ref not in assumption_ids:
                    findings.append(
                        Finding(
                            path=f"{attr}.findings[{index}].assumption_refs",
                            message=f"unknown assumption ref {ref!r}",
                            object_id=finding.id,
                        )
                    )
    return findings


def _issue_node_parents_resolve(state: EngagementState) -> list[Finding]:
    node_ids = id_set(state.issue_tree)
    findings: list[Finding] = []
    for index, node in enumerate(state.issue_tree):
        if node.parent and node.parent not in node_ids:
            findings.append(
                Finding(
                    path=f"issue_tree[{index}].parent",
                    message=f"node {node.id!r} has unknown parent {node.parent!r}",
                    object_id=node.id,
                )
            )
    return findings


def _issue_node_evidence_refs_resolve(state: EngagementState) -> list[Finding]:
    evidence_ids = id_set(state.evidence)
    findings: list[Finding] = []
    for index, node in enumerate(state.issue_tree):
        for ref in node.evidence_refs:
            if ref not in evidence_ids:
                findings.append(
                    Finding(
                        path=f"issue_tree[{index}].evidence_refs",
                        message=f"node {node.id!r} references unknown evidence {ref!r}",
                        object_id=node.id,
                    )
                )
    return findings


RULES = [
    ValidationRule(
        "REF-001",
        ValidationGroup.REFERENTIAL,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "Gap assumption_ref resolves to an existing assumption.",
        _gap_assumption_refs_resolve,
    ),
    ValidationRule(
        "REF-002",
        ValidationGroup.REFERENTIAL,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "Finding evidence_refs / assumption_refs resolve to existing objects.",
        _finding_refs_resolve,
    ),
    ValidationRule(
        "REF-003",
        ValidationGroup.REFERENTIAL,
        ViolationSeverity.ERROR,
        "ADR-002 §12",
        "Issue-tree node parent resolves to an existing node.",
        _issue_node_parents_resolve,
    ),
    ValidationRule(
        "REF-004",
        ValidationGroup.REFERENTIAL,
        ViolationSeverity.ERROR,
        "ADR-002 §12",
        "Issue-tree node evidence_refs resolve to existing evidence.",
        _issue_node_evidence_refs_resolve,
    ),
]
