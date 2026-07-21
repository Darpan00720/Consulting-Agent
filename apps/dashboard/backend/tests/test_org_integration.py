"""Integration tests: the Organization Layer wired against a REAL
``ConsultingEngine`` (W7) and a REAL ``FrameworkRegistry`` (W8)."""

from __future__ import annotations

import pytest

from app.consulting.engine import ConsultingEngine
from app.consulting.models import EngagementCategory
from app.consulting.state import ProblemDefinition
from app.knowledge.models import FrameworkExecutionRequest
from app.knowledge.registry import default_framework_registry
from app.organization.collaboration import CollaborationLog
from app.organization.errors import RoleNotEligibleError
from app.organization.integration import execute_role_framework, request_work_from_role
from app.organization.models import RequestKind
from app.organization.registry import default_organization_registry


def _engagement():
    engine = ConsultingEngine()
    state = engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="t1"
    )
    state.problem = ProblemDefinition(
        objective="Assess entering the healthcare SaaS market in APAC",
        scope=("APAC",),
        stakeholders=("CEO",),
    )
    return engine, state


def test_request_work_from_role_logs_a_traceable_task():
    log = CollaborationLog()
    oreg = default_organization_registry()
    financial_analyst = oreg.get("financial_analyst")
    request = request_work_from_role(
        log, financial_analyst, "Build DCF", "please build a DCF model"
    )
    assert request.kind is RequestKind.TASK
    assert request.to_role == "financial_analyst"
    assert request.from_role == "workflow_engine"
    assert request in log.requests_for_role("financial_analyst")


def test_execute_role_framework_feeds_the_real_engagement_state():
    _, state = _engagement()
    oreg = default_organization_registry()
    kreg = default_framework_registry()
    financial_analyst = oreg.get("financial_analyst")

    req = FrameworkExecutionRequest(
        provided_inputs=("cash flow projections", "discount rate"),
        provided_evidence=("financial statements",),
        findings=("NPV of $4.2M supports the business case",),
    )
    result = execute_role_framework(state, financial_analyst, kreg, "dcf", req)

    assert result.success
    assert len(state.evidence) == 1
    assert "NPV of $4.2M supports the business case" in state.analysis_findings


def test_execute_role_framework_rejects_engagement_type_mismatch():
    _, state = _engagement()  # MARKET_ENTRY
    oreg = default_organization_registry()
    kreg = default_framework_registry()
    financial_analyst = oreg.get("financial_analyst")
    # force an engagement type this role doesn't support
    import dataclasses

    unsupported_state = dataclasses.replace(
        state, category=EngagementCategory.CHANGE_MANAGEMENT
    )
    with pytest.raises(RoleNotEligibleError):
        execute_role_framework(
            unsupported_state,
            financial_analyst,
            kreg,
            "dcf",
            FrameworkExecutionRequest(),
        )


def test_execute_role_framework_rejects_framework_mismatch():
    _, state = _engagement()
    oreg = default_organization_registry()
    kreg = default_framework_registry()
    strategy_consultant = oreg.get("strategy_consultant")
    with pytest.raises(RoleNotEligibleError):
        execute_role_framework(
            state, strategy_consultant, kreg, "dcf", FrameworkExecutionRequest()
        )


def test_end_to_end_request_then_execute():
    """The full requested flow: the Workflow Engine requests work from a
    role (logged, traceable), and the role invokes a framework through the
    EXISTING Knowledge Library."""
    _, state = _engagement()
    oreg = default_organization_registry()
    kreg = default_framework_registry()
    log = CollaborationLog()
    financial_analyst = oreg.get("financial_analyst")

    request = request_work_from_role(
        log, financial_analyst, "Build DCF", "please build a DCF model"
    )
    log.respond(request.id, "acknowledged, starting DCF build")

    result = execute_role_framework(
        state,
        financial_analyst,
        kreg,
        "dcf",
        FrameworkExecutionRequest(
            provided_inputs=("cash flow projections", "discount rate"),
            provided_evidence=("financial statements",),
            findings=("NPV supports entry",),
        ),
    )
    assert result.success
    assert log.get(request.id).status.value == "closed"
    assert len(state.evidence) == 1
