"""Tests for the standard quality gates — each stage's mandatory checks, and
"workflow progression must stop if mandatory quality gates fail"."""

from __future__ import annotations

from app.consulting import tracking
from app.consulting.models import (
    ConsultingStage,
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.consulting.quality_gates import (
    evaluate_stage_gates,
    stage_gates_pass,
    standard_gates,
)
from app.consulting.state import (
    AnalysisPlan,
    EngagementState,
    EngagementStatus,
    IssueNode,
    IssueTree,
    ProblemDefinition,
    RoadmapPhase,
    validate_mece,
)
from app.consulting.state import Roadmap as _Roadmap

_GATES = standard_gates()


def _blank_state() -> EngagementState:
    return EngagementState(
        engagement_id="e1",
        workflow_id="workflow.growth_strategy",
        workflow_version="1.0.0",
        category=EngagementCategory.GROWTH_STRATEGY,
        status=EngagementStatus.IN_PROGRESS,
        current_stage=ConsultingStage.PROBLEM_DEFINITION,
    )


def test_problem_definition_gate_fails_when_empty():
    state = _blank_state()
    assert not stage_gates_pass(ConsultingStage.PROBLEM_DEFINITION, state, _GATES)


def test_problem_definition_gate_passes_when_complete():
    state = _blank_state()
    state.problem = ProblemDefinition(
        objective="Grow revenue 20%", scope=("APAC",), stakeholders=("CEO",)
    )
    assert stage_gates_pass(ConsultingStage.PROBLEM_DEFINITION, state, _GATES)


def test_hypothesis_gate_requires_rationale():
    state = _blank_state()
    state.hypotheses["h1"] = tracking.create_hypothesis(
        state, "New segment drives growth", 0.5, ""
    )
    # rationale is empty -> the rationale_recorded check must fail
    results = evaluate_stage_gates(
        ConsultingStage.HYPOTHESIS_DEVELOPMENT, state, _GATES
    )
    (gate,) = results
    checks = {c.name: c.passed for c in gate.checks}
    assert checks["hypotheses_documented"] is True
    assert checks["rationale_recorded"] is False
    assert not gate.passed


def test_issue_tree_gate_requires_mece_validated_flag():
    state = _blank_state()
    tree = IssueTree(
        root_id="root",
        nodes={"root": IssueNode(id="root", question="Q", parent_id=None)},
    )
    state.issue_tree = tree
    assert not stage_gates_pass(ConsultingStage.ISSUE_TREE_CONSTRUCTION, state, _GATES)
    ok, issues = validate_mece(tree)
    assert ok, issues
    tree.mece_validated = True
    assert stage_gates_pass(ConsultingStage.ISSUE_TREE_CONSTRUCTION, state, _GATES)


def test_analysis_planning_gate_requires_analyses_and_frameworks():
    state = _blank_state()
    assert not stage_gates_pass(ConsultingStage.ANALYSIS_PLANNING, state, _GATES)
    state.analysis_plan = AnalysisPlan(
        required_analyses=("market sizing",), required_frameworks=("TAM/SAM/SOM",)
    )
    assert stage_gates_pass(ConsultingStage.ANALYSIS_PLANNING, state, _GATES)


def test_evidence_collection_gate_requires_sufficient_quality():
    state = _blank_state()
    assert not stage_gates_pass(ConsultingStage.EVIDENCE_COLLECTION, state, _GATES)
    tracking.add_evidence(
        state,
        "industry report",
        EvidenceSourceType.EXTERNAL_RESEARCH,
        EvidenceQuality.LOW,
        0.3,
    )
    # only LOW-quality evidence -> still fails "sufficient quality"
    assert not stage_gates_pass(ConsultingStage.EVIDENCE_COLLECTION, state, _GATES)
    tracking.add_evidence(
        state,
        "primary research",
        EvidenceSourceType.EXTERNAL_RESEARCH,
        EvidenceQuality.HIGH,
        0.9,
    )
    assert stage_gates_pass(ConsultingStage.EVIDENCE_COLLECTION, state, _GATES)


def test_recommendations_gate_requires_evidence_tradeoffs_and_confidence():
    state = _blank_state()
    ev = tracking.add_evidence(
        state, "model output", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.8
    )
    assert not stage_gates_pass(ConsultingStage.RECOMMENDATIONS, state, _GATES)
    tracking.create_recommendation(
        state, "Do X", (ev.id,), "impact", ("risk",), ("tradeoff",), "low", 0.7
    )
    assert stage_gates_pass(ConsultingStage.RECOMMENDATIONS, state, _GATES)


def test_implementation_roadmap_gate_requires_kpis():
    state = _blank_state()
    state.roadmap = _Roadmap(
        phases=(RoadmapPhase(name="Phase 1", timeline="Q1", owners=("Ops",)),)
    )
    # no kpis defined on any phase
    assert not stage_gates_pass(ConsultingStage.IMPLEMENTATION_ROADMAP, state, _GATES)
    state.roadmap = _Roadmap(
        phases=(
            RoadmapPhase(
                name="Phase 1", timeline="Q1", owners=("Ops",), kpis=("cost/unit",)
            ),
        )
    )
    assert stage_gates_pass(ConsultingStage.IMPLEMENTATION_ROADMAP, state, _GATES)


def test_executive_deliverable_gate_checks_referential_integrity():
    state = _blank_state()
    ev = tracking.add_evidence(
        state, "source", EvidenceSourceType.INTERNAL_MEMORY, EvidenceQuality.HIGH, 0.9
    )
    tracking.create_recommendation(
        state, "Do X", (ev.id,), "impact", ("risk",), ("tradeoff",), "low", 0.7
    )
    state.roadmap = _Roadmap(
        phases=(RoadmapPhase(name="P1", timeline="Q1", owners=("Ops",), kpis=("kpi",)),)
    )
    assert stage_gates_pass(ConsultingStage.EXECUTIVE_DELIVERABLE, state, _GATES)
