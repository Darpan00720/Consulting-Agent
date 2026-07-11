"""Telemetry ↔ orchestration integration tests (v1.0 Observability)."""

from __future__ import annotations

from orchestration.report_gate import run_report_gate
from orchestration.telemetry import (
    content_metadata,
    instrument_gate,
    record_gate,
    record_governance,
    unsupported_finding_count,
)
from telemetry import (
    EngagementTracer,
    EventStatus,
    MemorySink,
    Phase,
    ValidationStatus,
    quality_analytics,
)
from tests.fixtures.golden_state import make_golden_profitability_state


def test_content_metadata_from_state() -> None:
    state = make_golden_profitability_state()
    meta = content_metadata(state)
    assert meta["issue_tree_size"] == len(state.issue_tree)
    assert meta["evidence_count"] == len(state.evidence)
    assert meta["reviewer_verdict"] == "approved"
    assert meta["challenger_verdict"] == "stands_with_caveats"
    assert meta["unsupported_finding_count"] == 0  # golden is fully evidenced


def test_unsupported_finding_count_flags_unevidenced() -> None:
    state = make_golden_profitability_state()
    assert unsupported_finding_count(state) == 0


def test_record_gate_emits_validation_event() -> None:
    state = make_golden_profitability_state()
    tracer = EngagementTracer(state.metadata.engagement_id, sink=MemorySink())
    gate = run_report_gate(state)
    record_gate(tracer, state, gate)
    events = tracer.events()
    assert len(events) == 1
    ev = events[0]
    assert ev.phase is Phase.VALIDATION_GATE
    assert ev.validation_status is ValidationStatus.PASSED
    assert ev.status is EventStatus.FINISHED
    assert ev.metadata["issue_tree_size"] == len(state.issue_tree)


def test_instrument_gate_runs_and_records() -> None:
    state = make_golden_profitability_state()
    tracer = EngagementTracer(state.metadata.engagement_id, sink=MemorySink())
    result = instrument_gate(tracer, state)
    assert result.ok
    assert len(tracer.events()) == 1


def test_record_governance_enables_quality_metrics() -> None:
    state = make_golden_profitability_state()
    tracer = EngagementTracer(state.metadata.engagement_id, sink=MemorySink())
    record_governance(tracer, state)
    q = quality_analytics(tracer.events())
    assert q.reviewer_pass_rate == 1.0  # golden reviewer = approved
    assert q.challenger_intervention_rate == 1.0  # stands_with_caveats = intervention
    assert q.needs_rework_frequency == 0.0


def test_blocked_gate_records_failed_event() -> None:
    state = make_golden_profitability_state().model_copy(
        update={"reviewer_notes": None}
    )
    tracer = EngagementTracer(state.metadata.engagement_id, sink=MemorySink())
    gate = run_report_gate(state)
    record_gate(tracer, state, gate)
    ev = tracer.events()[0]
    assert ev.validation_status is ValidationStatus.BLOCKED
    assert ev.status is EventStatus.FAILED
