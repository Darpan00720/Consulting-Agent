"""Tests for the structured collaboration model — the only inter-role
channel."""

from __future__ import annotations

import pytest

from app.organization.collaboration import CollaborationLog
from app.organization.errors import UnknownRequestError
from app.organization.models import RequestKind, RequestStatus


def test_create_request_starts_open():
    log = CollaborationLog()
    req = log.create_request(
        RequestKind.ANALYSIS,
        "project_leader",
        "financial_analyst",
        "Run DCF",
        "please run",
    )
    assert req.status is RequestStatus.OPEN
    assert req.response is None


def test_respond_closes_by_default():
    log = CollaborationLog()
    req = log.create_request(
        RequestKind.CLARIFICATION,
        "financial_analyst",
        "industry_specialist",
        "q",
        "what discount rate?",
    )
    updated = log.respond(req.id, "use 10%")
    assert updated.status is RequestStatus.CLOSED
    assert updated.response == "use 10%"
    assert updated.responded_at is not None


def test_respond_without_close_leaves_responded_status():
    log = CollaborationLog()
    req = log.create_request(
        RequestKind.REVIEW, "project_leader", "qa_reviewer", "review this", "content"
    )
    updated = log.respond(req.id, "looks good", close=False)
    assert updated.status is RequestStatus.RESPONDED


def test_respond_to_unknown_request_raises():
    log = CollaborationLog()
    with pytest.raises(UnknownRequestError):
        log.respond("req-ghost", "x")


def test_get_unknown_request_raises():
    log = CollaborationLog()
    with pytest.raises(UnknownRequestError):
        log.get("req-ghost")


def test_requests_for_role_is_the_inbox():
    log = CollaborationLog()
    log.create_request(
        RequestKind.TASK, "engagement_manager", "financial_analyst", "s1", "c1"
    )
    log.create_request(
        RequestKind.INFORMATION, "principal", "financial_analyst", "s2", "c2"
    )
    log.create_request(
        RequestKind.TASK, "engagement_manager", "strategy_consultant", "s3", "c3"
    )
    inbox = log.requests_for_role("financial_analyst")
    assert len(inbox) == 2


def test_requests_from_role_is_the_outbox():
    log = CollaborationLog()
    log.create_request(
        RequestKind.TASK, "engagement_manager", "financial_analyst", "s1", "c1"
    )
    outbox = log.requests_from_role("engagement_manager")
    assert len(outbox) == 1


def test_open_requests_excludes_closed_ones():
    log = CollaborationLog()
    req1 = log.create_request(RequestKind.TASK, "a", "b", "s1", "c1")
    log.create_request(RequestKind.TASK, "a", "b", "s2", "c2")
    log.respond(req1.id, "done")
    assert len(log.open_requests()) == 1


def test_all_requests_are_traceable_by_from_and_to():
    log = CollaborationLog()
    req = log.create_request(
        RequestKind.APPROVAL,
        "financial_analyst",
        "principal",
        "approve",
        "please approve",
    )
    all_reqs = log.all_requests()
    assert len(all_reqs) == 1
    assert all_reqs[0].from_role == "financial_analyst"
    assert all_reqs[0].to_role == "principal"
    assert all_reqs[0].id == req.id
