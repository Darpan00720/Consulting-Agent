"""Engagement metrics (requester's "Metrics" section) — computed on demand
from ``EngagementState``, never tracked as separate mutable counters (a
single source of truth avoids the two-copies-drift bug class the Memory
Platform's cache fingerprinting fix (W4) already taught this codebase to
watch for).
"""

from __future__ import annotations

from app.consulting.models import (
    AssumptionStatus,
    EngagementMetrics,
    HypothesisStatus,
)
from app.consulting.state import EngagementState, StageOutcome
from app.consulting.workflow import WorkflowDefinition


def compute_metrics(
    state: EngagementState, workflow: WorkflowDefinition
) -> EngagementMetrics:
    total_required = len(workflow.required_stages)
    completed = sum(
        1 for entry in state.stage_history if entry.outcome is StageOutcome.PASSED
    )
    workflow_completion = completed / total_required if total_required else 0.0

    stage_durations_s = {
        entry.stage.value: (entry.exited_at - entry.entered_at)
        for entry in state.stage_history
        if entry.exited_at is not None
    }

    all_gate_results = [
        gr for entry in state.stage_history for gr in entry.gate_results
    ]
    mandatory_results = [gr for gr in all_gate_results if gr.mandatory]
    quality_gate_pass_rate = (
        sum(1 for gr in mandatory_results if gr.passed) / len(mandatory_results)
        if mandatory_results
        else 0.0
    )

    resolved_hyps = [
        h
        for h in state.hypotheses.values()
        if h.status in (HypothesisStatus.CONFIRMED, HypothesisStatus.REJECTED)
    ]
    hypothesis_accuracy = (
        sum(1 for h in resolved_hyps if h.status is HypothesisStatus.CONFIRMED)
        / len(resolved_hyps)
        if resolved_hyps
        else 0.0
    )

    assumption_validation_rate = (
        sum(
            1
            for a in state.assumptions.values()
            if a.validation_status is not AssumptionStatus.UNVALIDATED
        )
        / len(state.assumptions)
        if state.assumptions
        else 0.0
    )

    evidence_coverage = (
        sum(1 for h in state.hypotheses.values() if h.evidence_ids)
        / len(state.hypotheses)
        if state.hypotheses
        else 0.0
    )

    recommendation_confidence = (
        sum(r.confidence for r in state.recommendations.values())
        / len(state.recommendations)
        if state.recommendations
        else 0.0
    )

    engagement_completeness = (
        workflow_completion + quality_gate_pass_rate + evidence_coverage
    ) / 3

    return EngagementMetrics(
        workflow_completion=workflow_completion,
        stage_durations_s=stage_durations_s,
        quality_gate_pass_rate=quality_gate_pass_rate,
        hypothesis_accuracy=hypothesis_accuracy,
        assumption_validation_rate=assumption_validation_rate,
        evidence_coverage=evidence_coverage,
        recommendation_confidence=recommendation_confidence,
        engagement_completeness=engagement_completeness,
    )
