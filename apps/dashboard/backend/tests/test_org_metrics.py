"""Tests for organizational metrics computed from real collaboration/review
history."""

from __future__ import annotations

from app.organization.collaboration import CollaborationLog
from app.organization.governance import request_approval
from app.organization.metrics import compute_org_metrics
from app.organization.models import (
    DecisionType,
    RequestKind,
    ReviewChecklistInput,
    ReviewStage,
)
from app.organization.registry import default_organization_registry
from app.organization.review import ReviewHistory, submit_for_review


def test_metrics_on_empty_history_are_all_zero_or_default():
    log = CollaborationLog()
    history = ReviewHistory()
    metrics = compute_org_metrics(log, history)
    assert metrics.handoff_count == 0
    assert metrics.quality_pass_rate == 0.0
    assert metrics.escalation_frequency == 0.0
    assert metrics.utilization_by_role == {}


def test_handoff_count_and_role_workload_reflect_requests():
    log = CollaborationLog()
    log.create_request(
        RequestKind.TASK, "engagement_manager", "financial_analyst", "s", "c"
    )
    log.create_request(
        RequestKind.TASK, "engagement_manager", "financial_analyst", "s2", "c2"
    )
    log.create_request(
        RequestKind.TASK, "engagement_manager", "strategy_consultant", "s3", "c3"
    )
    metrics = compute_org_metrics(log, ReviewHistory())
    assert metrics.handoff_count == 3
    assert metrics.role_workload == {"financial_analyst": 2, "strategy_consultant": 1}
    assert metrics.utilization_by_role["financial_analyst"] == 2 / 3


def test_quality_pass_rate_reflects_review_outcomes():
    r = default_organization_registry()
    qa = r.get("qa_reviewer")
    history = ReviewHistory()
    history.record(
        submit_for_review("a1", ReviewStage.MANAGER, qa, ReviewChecklistInput())
    )
    history.record(
        submit_for_review(
            "a2", ReviewStage.MANAGER, qa, ReviewChecklistInput(logic_sound=False)
        )
    )
    metrics = compute_org_metrics(CollaborationLog(), history)
    assert metrics.quality_pass_rate == 0.5


def test_review_iterations_by_artifact_tracked():
    r = default_organization_registry()
    qa = r.get("qa_reviewer")
    history = ReviewHistory()
    history.record(
        submit_for_review(
            "a1", ReviewStage.MANAGER, qa, ReviewChecklistInput(logic_sound=False)
        )
    )
    history.record(
        submit_for_review("a1", ReviewStage.MANAGER, qa, ReviewChecklistInput())
    )
    metrics = compute_org_metrics(CollaborationLog(), history)
    assert metrics.review_iterations_by_artifact == {"a1": 2}


def test_escalation_frequency_reflects_approval_outcomes():
    r = default_organization_registry()
    outcomes = (
        request_approval(
            r, "financial_analyst", DecisionType.APPROVE_RECOMMENDATIONS
        ),  # escalated
        request_approval(
            r, "project_leader", DecisionType.APPROVE_FINDINGS
        ),  # not escalated
    )
    metrics = compute_org_metrics(CollaborationLog(), ReviewHistory(), outcomes)
    assert metrics.escalation_frequency == 0.5


def test_approval_latency_measured_from_approval_kind_requests():
    log = CollaborationLog()
    req = log.create_request(
        RequestKind.APPROVAL, "financial_analyst", "principal", "s", "c"
    )
    log.respond(req.id, "approved")
    metrics = compute_org_metrics(log, ReviewHistory())
    assert metrics.average_approval_latency_s >= 0.0
