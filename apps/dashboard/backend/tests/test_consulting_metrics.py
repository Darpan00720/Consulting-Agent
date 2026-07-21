"""Tests for ``compute_metrics`` across the metric categories the requester
named: workflow completion, stage duration, quality-gate pass rate,
hypothesis accuracy, assumption validation rate, evidence coverage,
recommendation confidence, engagement completeness."""

from __future__ import annotations

import pytest

from app.consulting import tracking
from app.consulting.engine import ConsultingEngine
from app.consulting.metrics import compute_metrics
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.consulting.state import ProblemDefinition


def test_metrics_on_a_freshly_started_engagement_are_all_zero_or_default():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.RISK_ASSESSMENT)
    workflow = engine.resolve_workflow(EngagementCategory.RISK_ASSESSMENT)
    m = compute_metrics(state, workflow)
    assert m.workflow_completion == 0.0
    assert m.quality_gate_pass_rate == 0.0
    assert m.hypothesis_accuracy == 0.0
    assert m.assumption_validation_rate == 0.0
    assert m.evidence_coverage == 0.0
    assert m.recommendation_confidence == 0.0


def test_workflow_completion_increments_as_stages_pass():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.RISK_ASSESSMENT)
    workflow = engine.resolve_workflow(EngagementCategory.RISK_ASSESSMENT)

    state.problem = ProblemDefinition(objective="x", scope=("a",), stakeholders=("b",))
    results = engine.advance_stage("e1")
    assert all(r.passed for r in results)

    m = compute_metrics(state, workflow)
    assert m.workflow_completion == 1 / 10
    assert m.quality_gate_pass_rate == 1.0
    assert "problem_definition" in m.stage_durations_s


def test_hypothesis_accuracy_reflects_confirm_vs_reject_ratio():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.RISK_ASSESSMENT)
    workflow = engine.resolve_workflow(EngagementCategory.RISK_ASSESSMENT)

    h1 = tracking.create_hypothesis(state, "A", 0.5, "r")
    h2 = tracking.create_hypothesis(state, "B", 0.5, "r")
    ev = tracking.add_evidence(
        state, "s", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
    )
    tracking.confirm_hypothesis(state, h1.id, (ev.id,))
    tracking.reject_hypothesis(state, h2.id, (ev.id,))

    m = compute_metrics(state, workflow)
    assert m.hypothesis_accuracy == 0.5
    assert m.evidence_coverage == 1.0


def test_recommendation_confidence_is_average_of_recommendations():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.RISK_ASSESSMENT)
    workflow = engine.resolve_workflow(EngagementCategory.RISK_ASSESSMENT)

    ev = tracking.add_evidence(
        state, "s", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
    )
    tracking.create_recommendation(
        state, "A", (ev.id,), "impact", (), ("t",), "low", 0.4
    )
    tracking.create_recommendation(
        state, "B", (ev.id,), "impact", (), ("t",), "low", 0.8
    )

    m = compute_metrics(state, workflow)
    assert m.recommendation_confidence == pytest.approx(0.6)


def test_engagement_completeness_is_a_composite_between_zero_and_one():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.RISK_ASSESSMENT)
    workflow = engine.resolve_workflow(EngagementCategory.RISK_ASSESSMENT)
    m = compute_metrics(state, workflow)
    assert 0.0 <= m.engagement_completeness <= 1.0
