"""Integration tests: the Synthesis Engine wired against REAL W7
(ConsultingEngine), W8 (Knowledge Library), W9 (Organization Layer), and the
Memory Platform (checkpoint/resume)."""

from __future__ import annotations

import asyncio

import pytest

from app import config, db
from app.consulting.engine import ConsultingEngine
from app.consulting.models import EngagementCategory
from app.knowledge.execution import execute_framework
from app.knowledge.integration import apply_framework_result
from app.knowledge.models import FrameworkExecutionRequest
from app.knowledge.registry import default_framework_registry
from app.organization.errors import UnknownRoleError
from app.organization.registry import default_organization_registry
from app.synthesis import tracking as stracking
from app.synthesis.errors import SynthesisError, UnknownRecommendationError
from app.synthesis.integration import (
    assign_finding_owner,
    checkpoint_synthesis,
    create_finding_from_framework_result,
    request_recommendation_approval,
    resume_synthesis,
)
from app.synthesis.state import SynthesisState


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "synthesis-test.db")
    db.reset_for_tests()
    yield


def _built_engagement():
    engine = ConsultingEngine()
    cstate = engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="t1"
    )
    kreg = default_framework_registry()
    five_forces = kreg.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        findings=("Market rated 3.2/5 attractive",),
    )
    result = execute_framework(five_forces, req)
    created_evidence = apply_framework_result(cstate, result)
    return cstate, result, created_evidence


def test_create_finding_from_framework_result_bridges_w8_into_synthesis():
    cstate, result, created_evidence = _built_engagement()
    syn = SynthesisState(engagement_state=cstate)
    finding = create_finding_from_framework_result(
        syn,
        result,
        tuple(e.id for e in created_evidence),
        business_impact="market opportunity",
    )
    assert finding.related_frameworks == ("five_forces",)
    assert finding.confidence == result.confidence
    assert finding.id in syn.findings


def test_create_finding_from_framework_result_rejects_failed_execution():
    cstate, _result, _ev = _built_engagement()
    syn = SynthesisState(engagement_state=cstate)
    five_forces = default_framework_registry().get("five_forces")
    failed_result = execute_framework(five_forces, FrameworkExecutionRequest())
    assert not failed_result.success
    with pytest.raises(SynthesisError):
        create_finding_from_framework_result(syn, failed_result, ())


def test_assign_finding_owner_validates_against_real_organization_registry():
    cstate, result, created_evidence = _built_engagement()
    syn = SynthesisState(engagement_state=cstate)
    finding = create_finding_from_framework_result(
        syn, result, tuple(e.id for e in created_evidence)
    )
    oreg = default_organization_registry()
    updated = assign_finding_owner(syn, finding.id, "financial_analyst", oreg)
    assert updated.owner == "financial_analyst"

    with pytest.raises(UnknownRoleError):
        assign_finding_owner(syn, finding.id, "not_a_real_role", oreg)


def test_request_recommendation_approval_uses_real_governance_and_escalates():
    cstate, result, created_evidence = _built_engagement()
    syn = SynthesisState(engagement_state=cstate)
    finding = create_finding_from_framework_result(
        syn, result, tuple(e.id for e in created_evidence)
    )
    rec = stracking.create_recommendation(
        syn,
        "Enter market",
        "rationale",
        (finding.id,),
        tuple(e.id for e in created_evidence),
        # financial_analyst only holds hypothesis/assumption authority -> escalates
        owner="financial_analyst",
    )
    oreg = default_organization_registry()
    updated, outcome = request_recommendation_approval(syn, rec.id, oreg)
    assert outcome.escalated
    assert outcome.approved_by_role_id == "principal"
    assert updated.approval_status.value == "approved"


def test_request_recommendation_approval_rejects_unknown_recommendation():
    cstate, _result, _ev = _built_engagement()
    syn = SynthesisState(engagement_state=cstate)
    oreg = default_organization_registry()
    with pytest.raises(UnknownRecommendationError):
        request_recommendation_approval(syn, "srec-ghost", oreg)


def test_checkpoint_and_resume_round_trips_through_the_real_memory_platform():
    cstate, result, created_evidence = _built_engagement()
    syn = SynthesisState(engagement_state=cstate)
    finding = create_finding_from_framework_result(
        syn, result, tuple(e.id for e in created_evidence), business_impact="x"
    )
    stracking.create_recommendation(
        syn,
        "Enter market",
        "rationale",
        (finding.id,),
        tuple(e.id for e in created_evidence),
    )

    checkpoint_result = _run(checkpoint_synthesis(syn))
    assert checkpoint_result.success

    resumed = _run(resume_synthesis("e1"))
    assert len(resumed.findings) == 1
    assert len(resumed.recommendations) == 1
    assert next(iter(resumed.findings.values())).related_frameworks == ("five_forces",)
    assert resumed.engagement_state.category == cstate.category


def test_resume_without_a_prior_checkpoint_raises():
    with pytest.raises(SynthesisError):
        _run(resume_synthesis("never-checkpointed"))
