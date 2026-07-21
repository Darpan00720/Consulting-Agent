"""Organizational metrics (requester's "Organizational Metrics" section) —
computed on demand from the real ``CollaborationLog``/``ReviewHistory``/
approval history, never a separately tracked counter that could drift (the
same lesson ``app.consulting.metrics`` already applied)."""

from __future__ import annotations

from app.organization.collaboration import CollaborationLog
from app.organization.models import (
    ApprovalOutcome,
    OrgMetrics,
    RequestKind,
    RequestStatus,
)
from app.organization.review import ReviewHistory


def compute_org_metrics(
    log: CollaborationLog,
    review_history: ReviewHistory,
    approval_outcomes: tuple[ApprovalOutcome, ...] = (),
) -> OrgMetrics:
    all_requests = log.all_requests()

    role_workload: dict[str, int] = {}
    for request in all_requests:
        role_workload[request.to_role] = role_workload.get(request.to_role, 0) + 1
    total_requests = len(all_requests) or 1
    utilization_by_role = {
        role_id: count / total_requests for role_id, count in role_workload.items()
    }

    handoff_count = len(all_requests)

    review_iterations_by_artifact = {
        artifact_ref: review_history.iteration_count(artifact_ref)
        for artifact_ref in {r.artifact_ref for r in review_history.all_results()}
    }

    approval_requests = [r for r in all_requests if r.kind is RequestKind.APPROVAL]
    responded_approvals = [
        r
        for r in approval_requests
        if r.responded_at is not None and r.status is not RequestStatus.OPEN
    ]
    if responded_approvals:
        average_approval_latency_s = sum(
            r.responded_at - r.created_at for r in responded_approvals
        ) / len(responded_approvals)
    else:
        average_approval_latency_s = 0.0

    all_reviews = review_history.all_results()
    if all_reviews:
        passed = sum(
            1
            for rr in all_reviews
            if rr.outcome.value in ("approved", "approved_with_comments")
        )
        quality_pass_rate = passed / len(all_reviews)
    else:
        quality_pass_rate = 0.0

    if approval_outcomes:
        escalation_frequency = sum(1 for a in approval_outcomes if a.escalated) / len(
            approval_outcomes
        )
    else:
        escalation_frequency = 0.0

    # Decision turnaround reuses the same approval-request timestamps —
    # ``ApprovalOutcome`` itself carries no timestamp (a pure governance
    # decision, not a collaboration record), so wall-clock turnaround is only
    # observable through the collaboration channel that carried the request.
    average_decision_turnaround_s = average_approval_latency_s

    return OrgMetrics(
        utilization_by_role=utilization_by_role,
        handoff_count=handoff_count,
        review_iterations_by_artifact=review_iterations_by_artifact,
        average_approval_latency_s=average_approval_latency_s,
        quality_pass_rate=quality_pass_rate,
        role_workload=role_workload,
        escalation_frequency=escalation_frequency,
        average_decision_turnaround_s=average_decision_turnaround_s,
    )
