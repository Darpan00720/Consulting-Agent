"""Tests for artifact generation — one test per artifact type named in the
"Consulting Artifacts" requirement, confirming each has a defined schema
derived from real engagement state."""

from __future__ import annotations

from app.consulting import tracking
from app.consulting.artifacts import generate_artifact
from app.consulting.models import (
    ArtifactType,
    ConsultingStage,
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.consulting.state import (
    AnalysisPlan,
    EngagementState,
    EngagementStatus,
    IssueNode,
    IssueTree,
    ProblemDefinition,
    RiskRegisterEntry,
    RoadmapPhase,
)
from app.consulting.state import Roadmap as _Roadmap


def _rich_state() -> EngagementState:
    state = EngagementState(
        engagement_id="e1",
        workflow_id="workflow.product_strategy",
        workflow_version="1.0.0",
        category=EngagementCategory.PRODUCT_STRATEGY,
        status=EngagementStatus.IN_PROGRESS,
        current_stage=ConsultingStage.EXECUTIVE_DELIVERABLE,
    )
    state.problem = ProblemDefinition(
        objective="Decide whether to launch product X",
        scope=("US market",),
        stakeholders=("CPO", "CFO"),
        success_metrics=("ARR",),
        risks=("cannibalization",),
        unknowns=("willingness to pay",),
    )
    h = tracking.create_hypothesis(state, "WTP exceeds $50/mo", 0.6, "survey data")
    state.issue_tree = IssueTree(
        root_id="root",
        nodes={
            "root": IssueNode(id="root", question="Should we launch?", parent_id=None)
        },
        mece_validated=True,
    )
    state.analysis_plan = AnalysisPlan(
        required_analyses=("pricing research",), required_frameworks=("Van Westendorp",)
    )
    ev = tracking.add_evidence(
        state,
        "customer survey",
        EvidenceSourceType.EXTERNAL_RESEARCH,
        EvidenceQuality.HIGH,
        0.8,
        content="62% would pay $50/mo",
        related_hypothesis_ids=(h.id,),
    )
    tracking.confirm_hypothesis(state, h.id, (ev.id,))
    state.analysis_findings.append("WTP confirmed at $50-65/mo range")
    tracking.create_recommendation(
        state,
        "Launch at $59/mo",
        (ev.id,),
        "$4M ARR in yr 1",
        ("competitor response",),
        ("premium positioning risk",),
        "medium",
        0.7,
    )
    state.roadmap = _Roadmap(
        phases=(
            RoadmapPhase(
                name="Beta launch", timeline="Q1", owners=("PM",), kpis=("signups",)
            ),
        )
    )
    state.risk_register.append(
        RiskRegisterEntry(
            risk="Competitor undercut",
            likelihood="medium",
            impact="high",
            mitigation="lock-in pricing",
        )
    )
    return state


def test_problem_statement_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.PROBLEM_STATEMENT)
    assert art.content["objective"] == state.problem.objective
    assert art.id in state.artifacts


def test_project_charter_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.PROJECT_CHARTER)
    assert art.content["stakeholders"] == ["CPO", "CFO"]


def test_issue_tree_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.ISSUE_TREE)
    assert art.content["mece_validated"] is True
    assert len(art.content["nodes"]) == 1


def test_hypothesis_log_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.HYPOTHESIS_LOG)
    assert len(art.content["hypotheses"]) == 1
    assert art.content["hypotheses"][0]["status"] == "confirmed"


def test_assumption_register_artifact():
    state = _rich_state()
    tracking.create_assumption(state, "desc", "owner", "source", 0.5)
    art = generate_artifact(state, ArtifactType.ASSUMPTION_REGISTER)
    assert len(art.content["assumptions"]) == 1


def test_analysis_plan_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.ANALYSIS_PLAN)
    assert art.content["required_frameworks"] == ["Van Westendorp"]


def test_interview_guide_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.INTERVIEW_GUIDE)
    assert art.content["stakeholders"] == ["CPO", "CFO"]


def test_research_summary_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.RESEARCH_SUMMARY)
    assert len(art.content["sources"]) == 1


def test_findings_report_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.FINDINGS_REPORT)
    assert art.content["findings"] == ["WTP confirmed at $50-65/mo range"]


def test_recommendation_matrix_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.RECOMMENDATION_MATRIX)
    assert len(art.content["recommendations"]) == 1
    assert art.content["recommendations"][0]["statement"] == "Launch at $59/mo"


def test_implementation_roadmap_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.IMPLEMENTATION_ROADMAP)
    assert art.content["phases"][0]["name"] == "Beta launch"


def test_risk_register_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.RISK_REGISTER)
    assert art.content["risks"][0]["risk"] == "Competitor undercut"


def test_executive_summary_artifact():
    state = _rich_state()
    art = generate_artifact(state, ArtifactType.EXECUTIVE_SUMMARY)
    assert art.content["strategic_recommendations"] == ["Launch at $59/mo"]
    assert art.content["implementation_roadmap_phase_count"] == 1


def test_every_artifact_has_a_schema_version():
    state = _rich_state()
    for artifact_type in ArtifactType:
        art = generate_artifact(state, artifact_type)
        assert art.schema_version
