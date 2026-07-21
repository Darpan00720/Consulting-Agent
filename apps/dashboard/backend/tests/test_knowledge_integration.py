"""Integration tests: the Knowledge Library wired against a REAL
``ConsultingEngine``/``EngagementState`` (ADR-013 W7), through the existing
``app.consulting.tracking`` API only."""

from __future__ import annotations

from app.consulting.engine import ConsultingEngine
from app.consulting.models import EngagementCategory
from app.consulting.state import ProblemDefinition
from app.knowledge.execution import execute_framework
from app.knowledge.integration import (
    apply_framework_result,
    select_frameworks_for_engagement,
)
from app.knowledge.models import FrameworkExecutionRequest
from app.knowledge.registry import default_framework_registry


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


def test_select_frameworks_for_engagement_uses_real_engagement_state():
    _, state = _engagement()
    kreg = default_framework_registry()
    result = select_frameworks_for_engagement(state, kreg, industry="healthcare")
    assert len(result.recommended) > 0
    assert all(
        state.category in kreg.get(r.framework_id).supported_engagements
        for r in result.recommended
    )


def test_apply_framework_result_creates_real_evidence_via_existing_tracking():
    _, state = _engagement()
    kreg = default_framework_registry()
    five_forces = kreg.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        findings=("Market rated 3.2/5 attractive",),
        recommendations=("Differentiated entry required",),
    )
    result = execute_framework(five_forces, req)
    created = apply_framework_result(state, result)

    assert len(created) == 1
    assert created[0].source == "framework:five_forces"
    assert created[0].id in state.evidence
    assert "Market rated 3.2/5 attractive" in state.analysis_findings


def test_apply_framework_result_never_creates_an_engagement_recommendation():
    """Structural proof: even though the framework result carries analytical
    ``recommendations``, zero ``app.consulting`` Recommendations exist
    afterward — that transition is a deliberate, separate, evidence-linked
    call, never automatic."""
    _, state = _engagement()
    kreg = default_framework_registry()
    five_forces = kreg.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        findings=("x",),
        recommendations=("This looks like a strong recommendation",),
    )
    result = execute_framework(five_forces, req)
    apply_framework_result(state, result)
    assert len(state.recommendations) == 0


def test_apply_framework_result_is_a_no_op_on_failed_execution():
    _, state = _engagement()
    kreg = default_framework_registry()
    five_forces = kreg.get("five_forces")
    failed_result = execute_framework(five_forces, FrameworkExecutionRequest())
    assert not failed_result.success
    created = apply_framework_result(state, failed_result)
    assert created == ()
    assert len(state.evidence) == 0


def test_evidence_created_by_a_framework_can_feed_a_real_recommendation():
    """The full, legitimate downstream path: framework evidence -> (later,
    a separate judgment call) -> app.consulting.tracking.create_recommendation,
    which still enforces its own evidence-linkage invariant."""
    from app.consulting import tracking

    _, state = _engagement()
    kreg = default_framework_registry()
    five_forces = kreg.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        findings=("Industry moderately attractive",),
    )
    result = execute_framework(five_forces, req)
    (evidence,) = apply_framework_result(state, result)

    rec = tracking.create_recommendation(
        state,
        "Proceed with a differentiated market entry",
        (evidence.id,),
        "Est. $4M ARR in year 1",
        ("competitive response risk",),
        ("higher initial investment",),
        "medium",
        0.7,
    )
    assert rec.id in state.recommendations
    assert evidence.id in rec.supporting_evidence_ids
