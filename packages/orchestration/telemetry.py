"""Orchestration ↔ telemetry bridge (v1.0 Observability — integration).

The Python emission points for the parts of the pipeline that *are* code: the
validation gate and the governance verdicts. Given an ``EngagementState`` these
derive the content counts (issue-tree size, assumption/evidence/finding counts,
verdicts) into telemetry ``metadata`` so the quality analytics can compute
reviewer pass rate, challenger intervention, unsupported findings, etc.

Layering: orchestration depends on telemetry (not the reverse). Nothing here
mutates state or the pure report gate — it only reads state and emits events.
"""

from __future__ import annotations

from orchestration.report_gate import ReportGateResult, run_report_gate
from state.models import EngagementState
from state.sections.analysis import AnalysisBlock
from telemetry.engagement import EngagementTracer
from telemetry.events import EventStatus, Phase, ValidationStatus


def _blocks(state: EngagementState) -> list[AnalysisBlock]:
    return [
        b
        for b in (
            state.financial_analysis,
            state.market_analysis,
            state.operations_analysis,
            state.strategy_analysis,
            state.risk_analysis,
        )
        if b is not None
    ]


def unsupported_finding_count(state: EngagementState) -> int:
    """Answered findings that cite neither evidence nor an assumption."""
    total = 0
    for block in _blocks(state):
        for finding in block.findings:
            if finding.answer is not None and not (
                finding.evidence_refs or finding.assumption_refs
            ):
                total += 1
    return total


def content_metadata(state: EngagementState) -> dict[str, object]:
    """Structural content counts + verdicts for telemetry metadata (no prose)."""
    rec = state.recommendations
    reviewer = state.reviewer_notes
    challenger = state.challenge_notes
    return {
        "issue_tree_size": len(state.issue_tree),
        "assumption_count": len(state.assumptions),
        "evidence_count": len(state.evidence),
        "recommendation_count": len(rec.next_steps) if rec else 0,
        "unsupported_finding_count": unsupported_finding_count(state),
        "reviewer_verdict": (
            reviewer.verdict.value if reviewer and reviewer.verdict else "not_run"
        ),
        "challenger_verdict": (
            challenger.verdict.value if challenger and challenger.verdict else "not_run"
        ),
    }


def record_governance(tracer: EngagementTracer, state: EngagementState) -> None:
    """Emit REVIEW and CHALLENGE events carrying the verdicts from *state*.

    Used on the replay/derivation path (and any time state carries verdicts but
    live spans were not captured) so quality analytics can compute pass/
    intervention/rework rates.
    """
    reviewer = state.reviewer_notes
    if reviewer and reviewer.verdict:
        tracer.record(
            agent_name="reviewer",
            phase=Phase.REVIEW,
            status=EventStatus.FINISHED,
            metadata={"verdict": reviewer.verdict.value},
        )
    challenger = state.challenge_notes
    if challenger and challenger.verdict:
        tracer.record(
            agent_name="challenger",
            phase=Phase.CHALLENGE,
            status=EventStatus.FINISHED,
            metadata={"verdict": challenger.verdict.value},
        )


def record_gate(
    tracer: EngagementTracer,
    state: EngagementState,
    result: ReportGateResult,
) -> None:
    """Emit the VALIDATION_GATE event for a gate *result* on *state*."""
    tracer.record(
        agent_name="report_gate",
        phase=Phase.VALIDATION_GATE,
        status=EventStatus.FINISHED if result.ok else EventStatus.FAILED,
        validation_status=(
            ValidationStatus.PASSED if result.ok else ValidationStatus.BLOCKED
        ),
        metadata={
            **content_metadata(state),
            "blocking_issues": len(result.issues),
        },
    )


def instrument_gate(
    tracer: EngagementTracer, state: EngagementState
) -> ReportGateResult:
    """Run the report gate and record its telemetry in one call."""
    result = run_report_gate(state)
    record_gate(tracer, state, result)
    return result
