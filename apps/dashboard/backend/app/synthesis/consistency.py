"""Consistency validation (requester's "Consistency Validation" section) —
all 8 named checks, each genuinely computable from real state, with honest
scope limits documented where a check would otherwise require semantic
judgment (contradiction/conflict detection is DECLARED by the caller, never
inferred via text analysis — the same limit ``app.knowledge.composition``
already drew for itself).
"""

from __future__ import annotations

from app.synthesis.models import ConsistencyIssue, ConsistencyIssueType
from app.synthesis.state import SynthesisState

_LOW_CONFIDENCE_THRESHOLD = 0.4


def _unsupported_recommendations(state: SynthesisState) -> list[ConsistencyIssue]:
    issues = []
    for rec in state.recommendations.values():
        if not rec.supporting_finding_ids or not rec.supporting_evidence_ids:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.UNSUPPORTED_RECOMMENDATION,
                    (rec.id,),
                    "recommendation lacks supporting findings and/or evidence",
                )
            )
    return issues


def _duplicate_findings(state: SynthesisState) -> list[ConsistencyIssue]:
    issues = []
    seen: dict[str, str] = {}
    for finding in state.findings.values():
        normalized = finding.statement.strip().lower()
        if normalized in seen:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.DUPLICATE_FINDING,
                    (seen[normalized], finding.id),
                    f"identical statement text: {finding.statement!r}",
                )
            )
        else:
            seen[normalized] = finding.id
    return issues


def _contradictory_recommendations(state: SynthesisState) -> list[ConsistencyIssue]:
    issues = []
    reported: set[frozenset] = set()
    for rec in state.recommendations.values():
        for other_id in rec.contradicts:
            other = state.recommendations.get(other_id)
            if other is None:
                continue
            pair = frozenset({rec.id, other_id})
            if pair in reported:
                continue
            reported.add(pair)
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.CONTRADICTORY_RECOMMENDATIONS,
                    (rec.id, other_id),
                    "recommendations declare a mutual contradiction",
                )
            )
    return issues


def _missing_evidence(state: SynthesisState) -> list[ConsistencyIssue]:
    issues = []
    evidence_ids = set(state.engagement_state.evidence.keys())
    for finding in state.findings.values():
        missing = set(finding.supporting_evidence_ids) - evidence_ids
        if missing:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.MISSING_EVIDENCE,
                    (finding.id,),
                    f"references missing evidence ids: {sorted(missing)}",
                )
            )
    for rec in state.recommendations.values():
        missing = set(rec.supporting_evidence_ids) - evidence_ids
        if missing:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.MISSING_EVIDENCE,
                    (rec.id,),
                    f"references missing evidence ids: {sorted(missing)}",
                )
            )
    return issues


def _conflicting_assumptions(state: SynthesisState) -> list[ConsistencyIssue]:
    """Advisory only: two findings sharing an identical assumption string are
    flagged for a human/analyst to verify consistency between them — this
    module cannot judge whether the shared assumption is actually being
    applied consistently, only that it's worth checking."""
    issues = []
    by_assumption: dict[str, list[str]] = {}
    for finding in state.findings.values():
        for assumption in finding.assumptions:
            by_assumption.setdefault(assumption, []).append(finding.id)
    for assumption, finding_ids in by_assumption.items():
        if len(finding_ids) > 1:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.CONFLICTING_ASSUMPTIONS,
                    tuple(finding_ids),
                    "shared assumption across findings, verify consistency: "
                    f"{assumption!r}",
                )
            )
    return issues


def _orphan_insights(state: SynthesisState) -> list[ConsistencyIssue]:
    referenced: set[str] = set()
    for opp in state.opportunities.values():
        referenced.update(opp.supporting_insight_ids)
    for rec in state.recommendations.values():
        referenced.update(rec.supporting_insight_ids)
    for insight in state.insights.values():
        referenced.update(insight.dependencies)

    issues = []
    for insight in state.insights.values():
        if insight.id not in referenced:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.ORPHAN_INSIGHT,
                    (insight.id,),
                    "insight is not referenced by any opportunity, "
                    "recommendation, or other insight",
                )
            )
    return issues


def _has_cycle(nodes: dict, get_deps) -> list[frozenset]:
    """Generic DFS cycle detector over a same-level dependency graph — the
    same technique ``app.knowledge.registry.resolve_dependency_order``
    already uses for framework dependencies, applied here to insight/
    opportunity self-references."""
    visiting: set[str] = set()
    done: set[str] = set()
    cycles: list[frozenset] = []

    def visit(node_id: str, path: tuple[str, ...]) -> None:
        if node_id in done:
            return
        if node_id in visiting:
            cycles.append(frozenset(path))
            return
        visiting.add(node_id)
        for dep in get_deps(nodes[node_id]):
            if dep in nodes:
                visit(dep, (*path, node_id))
        visiting.discard(node_id)
        done.add(node_id)

    for node_id in nodes:
        visit(node_id, ())
    return cycles


def _circular_reasoning(state: SynthesisState) -> list[ConsistencyIssue]:
    issues = []
    for cycle in _has_cycle(state.insights, lambda i: i.dependencies):
        issues.append(
            ConsistencyIssue(
                ConsistencyIssueType.CIRCULAR_REASONING,
                tuple(cycle),
                "circular insight dependency",
            )
        )
    for cycle in _has_cycle(state.opportunities, lambda o: o.dependencies):
        issues.append(
            ConsistencyIssue(
                ConsistencyIssueType.CIRCULAR_REASONING,
                tuple(cycle),
                "circular opportunity dependency",
            )
        )
    return issues


def _low_confidence_conclusions(
    state: SynthesisState, threshold: float
) -> list[ConsistencyIssue]:
    issues = []
    for insight in state.insights.values():
        if insight.confidence < threshold:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.LOW_CONFIDENCE_CONCLUSION,
                    (insight.id,),
                    f"insight confidence {insight.confidence:.2f} below "
                    f"threshold {threshold:.2f}",
                )
            )
    for opp in state.opportunities.values():
        if opp.confidence < threshold:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.LOW_CONFIDENCE_CONCLUSION,
                    (opp.id,),
                    f"opportunity confidence {opp.confidence:.2f} below "
                    f"threshold {threshold:.2f}",
                )
            )
    for rec in state.recommendations.values():
        if rec.confidence < threshold:
            issues.append(
                ConsistencyIssue(
                    ConsistencyIssueType.LOW_CONFIDENCE_CONCLUSION,
                    (rec.id,),
                    f"recommendation confidence {rec.confidence:.2f} below "
                    f"threshold {threshold:.2f}",
                )
            )
    return issues


def validate_consistency(
    state: SynthesisState,
    *,
    low_confidence_threshold: float = _LOW_CONFIDENCE_THRESHOLD,
) -> tuple[ConsistencyIssue, ...]:
    issues: list[ConsistencyIssue] = []
    issues.extend(_unsupported_recommendations(state))
    issues.extend(_duplicate_findings(state))
    issues.extend(_contradictory_recommendations(state))
    issues.extend(_missing_evidence(state))
    issues.extend(_conflicting_assumptions(state))
    issues.extend(_orphan_insights(state))
    issues.extend(_circular_reasoning(state))
    issues.extend(_low_confidence_conclusions(state, low_confidence_threshold))
    return tuple(issues)
