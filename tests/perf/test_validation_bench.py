"""M1.6 baseline validation benchmarks — small and large Engagement States.

Sized by state contents (evidence / findings / issue nodes), not event counts
(adjustment 6). Single measured run per size; baselines, not optimization targets.
"""

from __future__ import annotations

from typing import Any

import pytest

from state.ledgers import Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding
from state.sections.planning import IssueNode
from state.validation import validate


def _large_state(size: int) -> EngagementState:
    evidence = [
        Evidence(
            claim=f"c{i}", type=EvidenceType.CLIENT_FACT, confidence=0.5, validated=True
        )
        for i in range(size)
    ]
    findings = [
        Finding(question=f"q{i}", evidence_refs=[evidence[i].id]) for i in range(size)
    ]
    nodes = [
        IssueNode(question=f"n{i}", owner="analyst", evidence_refs=[evidence[i].id])
        for i in range(size)
    ]
    return EngagementState(
        metadata=EngagementMetadata(engagement_id="e", tenant_id="t", slug="s"),
        evidence=evidence,
        issue_tree=nodes,
        financial_analysis=AnalysisBlock(findings=findings),
    )


@pytest.mark.parametrize("size", [10, 100, 1000, 10000])
def test_validation_baseline(benchmark: Any, size: int) -> None:
    state = _large_state(size)
    report = benchmark.pedantic(validate, args=(state,), rounds=1, iterations=1)
    assert report.valid
