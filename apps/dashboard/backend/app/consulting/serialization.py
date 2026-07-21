"""``EngagementState`` <-> plain-dict (de)serialization, for checkpointing
through the EXISTING Memory Platform (``CheckpointAdapter``, which wraps
``app.db``'s JSON-backed event log). Split out from ``engine.py`` so the
(de)serialization schema is independently testable.

Serialization is the easy direction: every field in this package's dataclasses
is already JSON-shaped (str/float/bool/None/dict/list/tuple, with ``StrEnum``
members serializing as their plain string value for free since ``StrEnum`` IS
a ``str`` subclass) — so ``dataclasses.asdict`` alone produces a JSON-safe
tree. Deserialization needs the explicit, hand-written half below because
``json.loads`` has no way to know a given dict should become a ``Hypothesis``
rather than a plain dict, or that a given list should become a ``tuple``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.consulting.models import (
    Artifact,
    ArtifactType,
    Assumption,
    AssumptionStatus,
    ConsultingStage,
    Decision,
    EngagementCategory,
    Evidence,
    EvidenceQuality,
    EvidenceSourceType,
    Hypothesis,
    HypothesisRevision,
    HypothesisStatus,
    QualityGateCheckResult,
    QualityGateResult,
    Recommendation,
)
from app.consulting.state import (
    AnalysisPlan,
    EngagementState,
    EngagementStatus,
    IssueNode,
    IssueTree,
    ProblemDefinition,
    RiskRegisterEntry,
    Roadmap,
    RoadmapPhase,
    StageHistoryEntry,
    StageOutcome,
)


def serialize_state(state: EngagementState) -> dict[str, Any]:
    return dataclasses.asdict(state)


def _problem(d: dict) -> ProblemDefinition:
    return ProblemDefinition(
        objective=d["objective"],
        scope=tuple(d["scope"]),
        constraints=tuple(d["constraints"]),
        stakeholders=tuple(d["stakeholders"]),
        success_metrics=tuple(d["success_metrics"]),
        risks=tuple(d["risks"]),
        unknowns=tuple(d["unknowns"]),
    )


def _hyp_revision(d: dict) -> HypothesisRevision:
    return HypothesisRevision(
        statement=d["statement"],
        confidence=d["confidence"],
        note=d["note"],
        revised_at=d["revised_at"],
    )


def _hypothesis(d: dict) -> Hypothesis:
    return Hypothesis(
        id=d["id"],
        statement=d["statement"],
        confidence=d["confidence"],
        rationale=d["rationale"],
        status=HypothesisStatus(d["status"]),
        evidence_ids=tuple(d["evidence_ids"]),
        revisions=tuple(_hyp_revision(r) for r in d["revisions"]),
        created_at=d["created_at"],
    )


def _assumption(d: dict) -> Assumption:
    return Assumption(
        id=d["id"],
        description=d["description"],
        owner=d["owner"],
        source=d["source"],
        confidence=d["confidence"],
        validation_status=AssumptionStatus(d["validation_status"]),
        date_created=d["date_created"],
        date_validated=d["date_validated"],
        related_analyses=tuple(d["related_analyses"]),
    )


def _evidence(d: dict) -> Evidence:
    return Evidence(
        id=d["id"],
        source=d["source"],
        source_type=EvidenceSourceType(d["source_type"]),
        quality=EvidenceQuality(d["quality"]),
        confidence=d["confidence"],
        content=d["content"],
        timestamp=d["timestamp"],
        related_hypothesis_ids=tuple(d["related_hypothesis_ids"]),
        related_recommendation_ids=tuple(d["related_recommendation_ids"]),
    )


def _issue_node(d: dict) -> IssueNode:
    return IssueNode(
        id=d["id"],
        question=d["question"],
        parent_id=d["parent_id"],
        hypothesis_ids=tuple(d["hypothesis_ids"]),
        owner=d["owner"],
    )


def _issue_tree(d: dict | None) -> IssueTree | None:
    if d is None:
        return None
    return IssueTree(
        root_id=d["root_id"],
        nodes={k: _issue_node(v) for k, v in d["nodes"].items()},
        mece_validated=d["mece_validated"],
    )


def _analysis_plan(d: dict) -> AnalysisPlan:
    return AnalysisPlan(
        required_analyses=tuple(d["required_analyses"]),
        required_frameworks=tuple(d["required_frameworks"]),
        required_data=tuple(d["required_data"]),
        required_tools=tuple(d["required_tools"]),
        required_experts=tuple(d["required_experts"]),
        dependencies=tuple(d["dependencies"]),
    )


def _decision(d: dict) -> Decision:
    return Decision(
        id=d["id"],
        decision=d["decision"],
        reasoning=d["reasoning"],
        alternatives_considered=tuple(d["alternatives_considered"]),
        supporting_evidence_ids=tuple(d["supporting_evidence_ids"]),
        decision_owner=d["decision_owner"],
        confidence=d["confidence"],
        timestamp=d["timestamp"],
    )


def _recommendation(d: dict) -> Recommendation:
    return Recommendation(
        id=d["id"],
        statement=d["statement"],
        supporting_evidence_ids=tuple(d["supporting_evidence_ids"]),
        expected_impact=d["expected_impact"],
        risks=tuple(d["risks"]),
        tradeoffs=tuple(d["tradeoffs"]),
        implementation_effort=d["implementation_effort"],
        confidence=d["confidence"],
        created_at=d["created_at"],
    )


def _roadmap_phase(d: dict) -> RoadmapPhase:
    return RoadmapPhase(
        name=d["name"],
        timeline=d["timeline"],
        owners=tuple(d["owners"]),
        dependencies=tuple(d["dependencies"]),
        quick_win=d["quick_win"],
        kpis=tuple(d["kpis"]),
    )


def _roadmap(d: dict) -> Roadmap:
    return Roadmap(phases=tuple(_roadmap_phase(p) for p in d["phases"]))


def _risk_entry(d: dict) -> RiskRegisterEntry:
    return RiskRegisterEntry(
        risk=d["risk"],
        likelihood=d["likelihood"],
        impact=d["impact"],
        mitigation=d["mitigation"],
        owner=d["owner"],
    )


def _artifact(d: dict) -> Artifact:
    return Artifact(
        id=d["id"],
        type=ArtifactType(d["type"]),
        stage=ConsultingStage(d["stage"]),
        content=d["content"],
        schema_version=d["schema_version"],
        created_at=d["created_at"],
    )


def _gate_check(d: dict) -> QualityGateCheckResult:
    return QualityGateCheckResult(
        name=d["name"], passed=d["passed"], detail=d["detail"]
    )


def _gate_result(d: dict) -> QualityGateResult:
    return QualityGateResult(
        gate_id=d["gate_id"],
        stage=ConsultingStage(d["stage"]),
        mandatory=d["mandatory"],
        passed=d["passed"],
        checks=tuple(_gate_check(c) for c in d["checks"]),
    )


def _stage_history_entry(d: dict) -> StageHistoryEntry:
    return StageHistoryEntry(
        stage=ConsultingStage(d["stage"]),
        entered_at=d["entered_at"],
        exited_at=d["exited_at"],
        outcome=StageOutcome(d["outcome"]),
        gate_results=tuple(_gate_result(g) for g in d["gate_results"]),
    )


def deserialize_state(data: dict[str, Any]) -> EngagementState:
    return EngagementState(
        engagement_id=data["engagement_id"],
        workflow_id=data["workflow_id"],
        workflow_version=data["workflow_version"],
        category=EngagementCategory(data["category"]),
        trace_id=data["trace_id"],
        status=EngagementStatus(data["status"]),
        current_stage=ConsultingStage(data["current_stage"])
        if data["current_stage"]
        else None,
        stage_history=[_stage_history_entry(e) for e in data["stage_history"]],
        problem=_problem(data["problem"]),
        hypotheses={k: _hypothesis(v) for k, v in data["hypotheses"].items()},
        assumptions={k: _assumption(v) for k, v in data["assumptions"].items()},
        evidence={k: _evidence(v) for k, v in data["evidence"].items()},
        issue_tree=_issue_tree(data["issue_tree"]),
        analysis_plan=_analysis_plan(data["analysis_plan"]),
        analysis_findings=list(data["analysis_findings"]),
        decisions=[_decision(d) for d in data["decisions"]],
        recommendations={
            k: _recommendation(v) for k, v in data["recommendations"].items()
        },
        roadmap=_roadmap(data["roadmap"]),
        risk_register=[_risk_entry(r) for r in data["risk_register"]],
        artifacts={k: _artifact(v) for k, v in data["artifacts"].items()},
        created_at=data["created_at"],
    )
