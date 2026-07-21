"""Hallucination Detection (requester's "Hallucination Detection" section, 8
named checks). "Reports must reference the exact offending artifacts" is
enforced structurally: every ``HallucinationFinding.ref_ids`` below is a
real id (or content string) pulled from the replayed state, never a
generic message.

**4 checks reuse ``app.synthesis.consistency.validate_consistency``**
(relabeled into this module's own taxonomy) since they need the live
``SynthesisState`` graph the same way consistency validation already
walks it: ``UNSUPPORTED_RECOMMENDATION``, ``CONTRADICTORY_REASONING``,
``BROKEN_TRACEABILITY``, ``UNSUPPORTED_CONCLUSION``. **4 are genuinely
new** for this layer: ``UNSUPPORTED_FINDING`` and ``MISSING_ASSUMPTIONS``
(gaps ``app.synthesis.consistency`` doesn't check — it validates
recommendations' and insights'/opportunities' support, never a finding's
own confidence or its declared assumptions) and ``INVENTED_EVIDENCE``/
``INVENTED_METRIC`` (checks that only make sense one layer up, comparing
replayed content back to the benchmark case's recorded ground truth).

The 4 state-dependent checks need the live ``SynthesisState`` a replay
built (see ``app.evaluation.replay.replay_case_with_state``) — a flattened
``CaseReplayResult`` alone doesn't carry evidence ids, assumptions, or the
insight/opportunity graph. When ``state`` isn't supplied, those checks are
skipped (not silently reported as "clean") — only the two checks that work
from flattened data alone (``INVENTED_EVIDENCE``, ``INVENTED_METRIC``)
still run.
"""

from __future__ import annotations

from app.synthesis.consistency import validate_consistency
from app.synthesis.models import ConsistencyIssueType
from app.synthesis.state import SynthesisState

from .models import (
    BenchmarkCase,
    CaseReplayResult,
    HallucinationFinding,
    HallucinationType,
)

_LOW_CONFIDENCE_THRESHOLD = 0.4

_ALLOWED_QUALITY_METRIC_KEYS = frozenset(
    {
        "synthesis_overall_score",
        "traceability",
        "logical_consistency",
        "evidence_coverage",
        "confidence",
        "recommendation_completeness",
        "trade_off_analysis",
        "business_impact",
        "implementation_feasibility",
    }
)

_UR = HallucinationType.UNSUPPORTED_RECOMMENDATION
_CR = HallucinationType.CONTRADICTORY_REASONING
_BT = HallucinationType.BROKEN_TRACEABILITY
_UC = HallucinationType.UNSUPPORTED_CONCLUSION

_CONSISTENCY_TO_HALLUCINATION = {
    ConsistencyIssueType.UNSUPPORTED_RECOMMENDATION: _UR,
    ConsistencyIssueType.CONTRADICTORY_RECOMMENDATIONS: _CR,
    ConsistencyIssueType.CIRCULAR_REASONING: _CR,
    ConsistencyIssueType.MISSING_EVIDENCE: _BT,
    ConsistencyIssueType.LOW_CONFIDENCE_CONCLUSION: _UC,
}


def _from_consistency(state: SynthesisState) -> list[HallucinationFinding]:
    findings = []
    for issue in validate_consistency(state):
        hallucination_type = _CONSISTENCY_TO_HALLUCINATION.get(issue.issue_type)
        if hallucination_type is None:
            continue  # DUPLICATE_FINDING/ORPHAN_INSIGHT/CONFLICTING_ASSUMPTIONS
            # are real consistency concerns but not hallucination-shaped ones
        findings.append(
            HallucinationFinding(
                hallucination_type=hallucination_type,
                ref_ids=issue.ref_ids,
                detail=issue.detail,
            )
        )
    return findings


def _unsupported_findings(state: SynthesisState) -> list[HallucinationFinding]:
    """A gap ``app.synthesis.consistency`` doesn't check: it validates
    recommendation/insight/opportunity confidence, never a finding's own."""
    return [
        HallucinationFinding(
            hallucination_type=HallucinationType.UNSUPPORTED_FINDING,
            ref_ids=(finding.id,),
            detail=(
                f"finding confidence {finding.confidence:.2f} below "
                f"threshold {_LOW_CONFIDENCE_THRESHOLD:.2f}"
            ),
        )
        for finding in state.findings.values()
        if finding.confidence < _LOW_CONFIDENCE_THRESHOLD
    ]


def _missing_assumptions(state: SynthesisState) -> list[HallucinationFinding]:
    return [
        HallucinationFinding(
            hallucination_type=HallucinationType.MISSING_ASSUMPTIONS,
            ref_ids=(finding.id,),
            detail="finding declares zero assumptions",
        )
        for finding in state.findings.values()
        if not finding.assumptions
    ]


def _invented_evidence(
    case: BenchmarkCase, replay: CaseReplayResult
) -> list[HallucinationFinding]:
    grounded = frozenset(case.expected_findings) | frozenset(case.available_data)
    invented = [f for f in replay.findings if f not in grounded]
    if not invented:
        return []
    return [
        HallucinationFinding(
            hallucination_type=HallucinationType.INVENTED_EVIDENCE,
            ref_ids=tuple(invented),
            detail=(
                "replay recorded finding/evidence content not present in the "
                "case's expected_findings or available_data"
            ),
        )
    ]


def _invented_metrics(
    case: BenchmarkCase, replay: CaseReplayResult
) -> list[HallucinationFinding]:
    invented = [
        k for k in replay.quality_metrics if k not in _ALLOWED_QUALITY_METRIC_KEYS
    ]
    if not invented:
        return []
    return [
        HallucinationFinding(
            hallucination_type=HallucinationType.INVENTED_METRIC,
            ref_ids=tuple(invented),
            detail=(
                "quality_metrics contains keys not produced by any known quality check"
            ),
        )
    ]


def detect_hallucinations(
    case: BenchmarkCase,
    replay: CaseReplayResult,
    *,
    state: SynthesisState | None = None,
) -> tuple[HallucinationFinding, ...]:
    """Never raises: zero findings is a normal, good outcome. Every
    ``HallucinationFinding.ref_ids`` names the exact offending finding/
    recommendation/content, per the requester's own requirement."""
    findings: list[HallucinationFinding] = []
    findings.extend(_invented_evidence(case, replay))
    findings.extend(_invented_metrics(case, replay))
    if state is not None:
        findings.extend(_from_consistency(state))
        findings.extend(_unsupported_findings(state))
        findings.extend(_missing_assumptions(state))
    return tuple(findings)
