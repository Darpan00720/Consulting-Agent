"""Tests for ``ConsultingEngine`` — stage progression + gate enforcement,
pause/resume, checkpoint/rollback (against the REAL Memory Platform ->
CheckpointAdapter -> app.db), and analysis execution routed through the REAL
Workflow Router + Dispatcher (the platform-integration proof, requirement
11/12)."""

from __future__ import annotations

import asyncio

import pytest

from app import config, db
from app.consulting import tracking
from app.consulting.engine import ConsultingEngine
from app.consulting.errors import UnknownEngagementError
from app.consulting.models import (
    ConsultingStage,
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.consulting.state import EngagementStatus, ProblemDefinition


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch, tmp_path):
    """Same isolation convention as ``tests/test_memory_adapters.py`` (W4) —
    required here too since ``ConsultingEngine.checkpoint``/``rollback`` go
    through the REAL ``CheckpointAdapter`` -> ``app.db``."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "consulting-test.db")
    db.reset_for_tests()
    yield


# ---- Stage progression + gate enforcement ----------------------------------


def test_start_engagement_enters_problem_definition():
    engine = ConsultingEngine()
    state = engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="t1"
    )
    assert state.current_stage is ConsultingStage.PROBLEM_DEFINITION
    assert state.status is EngagementStatus.IN_PROGRESS
    assert len(state.stage_history) == 1


def test_advance_stage_blocks_when_mandatory_gate_fails():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.MARKET_ENTRY)
    results = engine.advance_stage("e1")
    assert not all(r.passed for r in results)
    assert state.current_stage is ConsultingStage.PROBLEM_DEFINITION  # unchanged
    assert state.stage_history[-1].outcome.value == "blocked"


def test_advance_stage_progresses_when_gate_passes():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.MARKET_ENTRY)
    state.problem = ProblemDefinition(objective="x", scope=("a",), stakeholders=("b",))
    results = engine.advance_stage("e1")
    assert all(r.passed for r in results)
    assert state.current_stage is ConsultingStage.HYPOTHESIS_DEVELOPMENT
    assert state.stage_history[0].outcome.value == "passed"
    assert state.stage_history[0].exited_at is not None
    assert len(state.stage_history) == 2


def test_get_state_raises_for_unknown_engagement():
    engine = ConsultingEngine()
    with pytest.raises(UnknownEngagementError):
        engine.get_state("ghost")


def _drive_to_stage(
    engine: ConsultingEngine, engagement_id: str, target: ConsultingStage
) -> None:
    """Test helper: drive a fresh engagement through the minimum data needed
    to pass every gate up to (not including) ``target``."""
    state = engine.get_state(engagement_id)
    while state.current_stage is not None and state.current_stage is not target:
        stage = state.current_stage
        if stage is ConsultingStage.PROBLEM_DEFINITION:
            state.problem = ProblemDefinition(
                objective="x", scope=("a",), stakeholders=("b",)
            )
        elif stage is ConsultingStage.HYPOTHESIS_DEVELOPMENT:
            tracking.create_hypothesis(state, "H1", 0.5, "rationale")
        elif stage is ConsultingStage.ISSUE_TREE_CONSTRUCTION:
            from app.consulting.state import IssueNode, IssueTree

            state.issue_tree = IssueTree(
                root_id="root",
                nodes={"root": IssueNode(id="root", question="Q?", parent_id=None)},
                mece_validated=True,
            )
        elif stage is ConsultingStage.ANALYSIS_PLANNING:
            from app.consulting.state import AnalysisPlan

            state.analysis_plan = AnalysisPlan(
                required_analyses=("a",), required_frameworks=("f",)
            )
        elif stage is ConsultingStage.EVIDENCE_COLLECTION:
            tracking.add_evidence(
                state, "s", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
            )
        elif stage is ConsultingStage.ANALYSIS_EXECUTION:
            state.analysis_findings.append("finding 1")
        elif stage is ConsultingStage.SYNTHESIS:
            hyp_id = next(iter(state.hypotheses))
            ev_id = next(iter(state.evidence))
            tracking.confirm_hypothesis(state, hyp_id, (ev_id,))
        elif stage is ConsultingStage.RECOMMENDATIONS:
            ev_id = next(iter(state.evidence))
            tracking.create_recommendation(
                state, "Do X", (ev_id,), "impact", ("risk",), ("tradeoff",), "low", 0.7
            )
        elif stage is ConsultingStage.IMPLEMENTATION_ROADMAP:
            from app.consulting.state import Roadmap, RoadmapPhase

            state.roadmap = Roadmap(
                phases=(
                    RoadmapPhase(
                        name="P1", timeline="Q1", owners=("Ops",), kpis=("kpi",)
                    ),
                )
            )
        results = engine.advance_stage(engagement_id)
        assert all(r.passed for r in results), (stage, results)


def test_full_lifecycle_reaches_completed_and_generates_executive_summary():
    engine = ConsultingEngine()
    engine.start_engagement("e1", EngagementCategory.COST_REDUCTION)
    _drive_to_stage(engine, "e1", None)  # drive all the way through
    state = engine.get_state("e1")
    assert state.status is EngagementStatus.COMPLETED
    assert state.current_stage is None
    from app.consulting.models import ArtifactType

    assert any(
        a.type is ArtifactType.EXECUTIVE_SUMMARY for a in state.artifacts.values()
    )


# ---- Pause / resume (in-memory) --------------------------------------------


def test_pause_and_resume_in_memory():
    engine = ConsultingEngine()
    engine.start_engagement("e1", EngagementCategory.MARKET_ENTRY)
    engine.pause("e1")
    assert engine.get_state("e1").status is EngagementStatus.PAUSED
    resumed = engine.resume_in_memory("e1")
    assert resumed.status is EngagementStatus.IN_PROGRESS


# ---- Checkpoint / resume-from-checkpoint / rollback (REAL memory platform) -


def test_checkpoint_and_resume_from_checkpoint_round_trips_full_state():
    engine = ConsultingEngine()
    state = engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="tr-1"
    )
    state.problem = ProblemDefinition(
        objective="Enter APAC", scope=("Japan",), stakeholders=("CEO",)
    )
    engine.advance_stage("e1")
    tracking.create_hypothesis(
        state, "Local partner required", 0.6, "regulatory research"
    )

    result = _run(engine.checkpoint("e1"))
    assert result.success

    # Simulate a fresh process: a NEW engine with no in-memory state.
    fresh_engine = ConsultingEngine()
    restored = _run(fresh_engine.resume_from_checkpoint("e1"))
    assert restored.status is EngagementStatus.IN_PROGRESS
    assert restored.problem.objective == "Enter APAC"
    assert len(restored.hypotheses) == 1
    assert restored.current_stage is ConsultingStage.HYPOTHESIS_DEVELOPMENT


def test_resume_from_checkpoint_raises_when_none_exists():
    engine = ConsultingEngine()
    with pytest.raises(UnknownEngagementError):
        _run(engine.resume_from_checkpoint("never-checkpointed"))


def test_rollback_restores_state_as_of_an_earlier_stage():
    engine = ConsultingEngine()
    state = engine.start_engagement("e1", EngagementCategory.MARKET_ENTRY)
    state.problem = ProblemDefinition(objective="x", scope=("a",), stakeholders=("b",))
    engine.advance_stage("e1")  # now in hypothesis_development
    _run(engine.checkpoint("e1"))  # checkpoint AT hypothesis_development

    tracking.create_hypothesis(state, "H1", 0.5, "rationale")
    engine.advance_stage("e1")  # now in issue_tree_construction
    ev = tracking.add_evidence(
        state, "s", EvidenceSourceType.CALCULATION, EvidenceQuality.HIGH, 0.9
    )
    tracking.create_recommendation(
        state, "premature rec", (ev.id,), "impact", ("r",), ("t",), "low", 0.5
    )
    assert len(engine.get_state("e1").recommendations) == 1

    rolled_back = _run(engine.rollback("e1", ConsultingStage.HYPOTHESIS_DEVELOPMENT))
    assert rolled_back.current_stage is ConsultingStage.HYPOTHESIS_DEVELOPMENT
    assert len(rolled_back.recommendations) == 0  # didn't exist at that checkpoint
    assert rolled_back.status is EngagementStatus.IN_PROGRESS


def test_rollback_raises_when_no_checkpoint_for_that_stage():
    engine = ConsultingEngine()
    engine.start_engagement("e1", EngagementCategory.MARKET_ENTRY)
    with pytest.raises(UnknownEngagementError):
        _run(engine.rollback("e1", ConsultingStage.RECOMMENDATIONS))


# ---- Analysis execution — REAL Workflow Router + Dispatcher integration ----


def test_execute_stage_analysis_routes_through_the_real_consulting_guardrail():
    """The concrete integration proof (requirement 11): this engine does NOT
    call an agent directly — it goes through ``app.workflow.router.route`` +
    ``app.workflow.dispatcher.dispatch``, so the SAME consulting guardrail
    (ADR-013) that governs every other caller governs this one too."""
    engine = ConsultingEngine()
    engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="tr-analysis"
    )
    result = _run(
        engine.execute_stage_analysis("e1", "size the APAC market opportunity")
    )
    assert result.category == "business_consulting"
    assert result.target_used in ("consulting", None)  # None only if unavailable
    state = engine.get_state("e1")
    if result.output:
        assert result.output in state.analysis_findings
