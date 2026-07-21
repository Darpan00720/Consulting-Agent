"""Quality model (requester's "Quality Model" section) — 8 named
dimensions, each a real, computed score from ``SynthesisState``, never a
guess. Mirrors the "generic, data-driven quality gates" pattern
``app.consulting.quality_gates`` and ``app.knowledge.quality`` already
established one and two layers down.
"""

from __future__ import annotations

from app.synthesis.consistency import validate_consistency
from app.synthesis.models import (
    ConsistencyIssueType,
    QualityCheckResult,
    QualityDimension,
    QualityReport,
)
from app.synthesis.state import SynthesisState

_PASS_THRESHOLD = 0.6


def _traceability(state: SynthesisState) -> QualityCheckResult:
    recs = list(state.recommendations.values())
    if not recs:
        return QualityCheckResult(
            QualityDimension.TRACEABILITY, False, 0.0, "no recommendations"
        )
    traced = sum(
        1 for r in recs if r.supporting_finding_ids and r.supporting_evidence_ids
    )
    score = traced / len(recs)
    return QualityCheckResult(
        QualityDimension.TRACEABILITY,
        score >= _PASS_THRESHOLD,
        score,
        f"{traced}/{len(recs)} recommendations fully traced to findings+evidence",
    )


def _logical_consistency(state: SynthesisState) -> QualityCheckResult:
    issues = validate_consistency(state)
    blocking_types = {
        ConsistencyIssueType.CIRCULAR_REASONING,
        ConsistencyIssueType.CONTRADICTORY_RECOMMENDATIONS,
        ConsistencyIssueType.MISSING_EVIDENCE,
    }
    blocking = [i for i in issues if i.issue_type in blocking_types]
    passed = len(blocking) == 0
    score = 1.0 if passed else max(0.0, 1.0 - 0.25 * len(blocking))
    return QualityCheckResult(
        QualityDimension.LOGICAL_CONSISTENCY,
        passed,
        score,
        f"{len(blocking)} blocking consistency issue(s)"
        if blocking
        else "no blocking issues",
    )


def _evidence_coverage(state: SynthesisState) -> QualityCheckResult:
    all_evidence = set(state.engagement_state.evidence.keys())
    if not all_evidence:
        return QualityCheckResult(
            QualityDimension.EVIDENCE_COVERAGE, False, 0.0, "no evidence in engagement"
        )
    referenced: set[str] = set()
    for finding in state.findings.values():
        referenced.update(finding.supporting_evidence_ids)
    score = len(referenced & all_evidence) / len(all_evidence)
    return QualityCheckResult(
        QualityDimension.EVIDENCE_COVERAGE,
        score >= _PASS_THRESHOLD,
        score,
        f"{len(referenced & all_evidence)}/{len(all_evidence)} evidence "
        "items referenced by a finding",
    )


def _confidence(state: SynthesisState) -> QualityCheckResult:
    values = (
        [f.confidence for f in state.findings.values()]
        + [i.confidence for i in state.insights.values()]
        + [o.confidence for o in state.opportunities.values()]
        + [r.confidence for r in state.recommendations.values()]
    )
    if not values:
        return QualityCheckResult(
            QualityDimension.CONFIDENCE, False, 0.0, "no synthesis nodes yet"
        )
    avg = sum(values) / len(values)
    return QualityCheckResult(
        QualityDimension.CONFIDENCE,
        avg >= _PASS_THRESHOLD,
        avg,
        f"average confidence {avg:.2f}",
    )


def _recommendation_completeness(state: SynthesisState) -> QualityCheckResult:
    recs = list(state.recommendations.values())
    if not recs:
        return QualityCheckResult(
            QualityDimension.RECOMMENDATION_COMPLETENESS,
            False,
            0.0,
            "no recommendations",
        )
    complete = sum(
        1
        for r in recs
        if r.kpis and r.cost and r.risk and r.trade_offs and r.expected_benefits
    )
    score = complete / len(recs)
    return QualityCheckResult(
        QualityDimension.RECOMMENDATION_COMPLETENESS,
        score >= _PASS_THRESHOLD,
        score,
        f"{complete}/{len(recs)} recommendations have "
        "kpis/cost/risk/trade_offs/benefits",
    )


def _trade_off_analysis(state: SynthesisState) -> QualityCheckResult:
    count = len(state.trade_off_results)
    score = 1.0 if count > 0 else 0.0
    return QualityCheckResult(
        QualityDimension.TRADE_OFF_ANALYSIS,
        count > 0,
        score,
        f"{count} trade-off analysis/analyses recorded",
    )


def _business_impact(state: SynthesisState) -> QualityCheckResult:
    recs = list(state.recommendations.values())
    if not recs:
        return QualityCheckResult(
            QualityDimension.BUSINESS_IMPACT, False, 0.0, "no recommendations"
        )
    assessed_refs = {a.target_ref for a in state.business_impact_assessments.values()}
    covered = sum(1 for r in recs if r.id in assessed_refs)
    score = covered / len(recs)
    return QualityCheckResult(
        QualityDimension.BUSINESS_IMPACT,
        score >= _PASS_THRESHOLD,
        score,
        f"{covered}/{len(recs)} recommendations have a business impact assessment",
    )


def _implementation_feasibility(state: SynthesisState) -> QualityCheckResult:
    recs = list(state.recommendations.values())
    if not recs:
        return QualityCheckResult(
            QualityDimension.IMPLEMENTATION_FEASIBILITY,
            False,
            0.0,
            "no recommendations",
        )
    themed: set[str] = set()
    for theme in state.implementation_themes.values():
        themed.update(theme.supporting_recommendation_ids)
    covered = sum(1 for r in recs if r.id in themed)
    score = covered / len(recs)
    return QualityCheckResult(
        QualityDimension.IMPLEMENTATION_FEASIBILITY,
        score >= _PASS_THRESHOLD,
        score,
        f"{covered}/{len(recs)} recommendations covered by an implementation theme",
    )


_CHECKS = (
    _traceability,
    _logical_consistency,
    _evidence_coverage,
    _confidence,
    _recommendation_completeness,
    _trade_off_analysis,
    _business_impact,
    _implementation_feasibility,
)


def assess_quality(state: SynthesisState) -> QualityReport:
    checks = tuple(check_fn(state) for check_fn in _CHECKS)
    overall = sum(c.score for c in checks) / len(checks)
    return QualityReport(checks=checks, overall_score=overall)
