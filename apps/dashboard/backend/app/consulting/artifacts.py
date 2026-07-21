"""Consulting artifact generation (requester's "Consulting Artifacts" section).

Each artifact is a schema'd snapshot DERIVED from ``EngagementState`` — this
module owns the schema and the derivation, never original content generation
(that is business-logic work an agent does via ``engine.execute_stage_analysis``;
an artifact here packages what the engagement has already recorded, it does
not invent findings).
"""

from __future__ import annotations

from app.consulting.models import (
    ARTIFACT_SCHEMA_VERSION,
    Artifact,
    ArtifactType,
    EvidenceSourceType,
    new_artifact_id,
)
from app.consulting.state import EngagementState

_STAGE_OF_ARTIFACT = {
    ArtifactType.PROBLEM_STATEMENT: "problem_definition",
    ArtifactType.PROJECT_CHARTER: "problem_definition",
    ArtifactType.ISSUE_TREE: "issue_tree_construction",
    ArtifactType.HYPOTHESIS_LOG: "hypothesis_development",
    ArtifactType.ASSUMPTION_REGISTER: "analysis_execution",
    ArtifactType.ANALYSIS_PLAN: "analysis_planning",
    ArtifactType.INTERVIEW_GUIDE: "analysis_planning",
    ArtifactType.RESEARCH_SUMMARY: "evidence_collection",
    ArtifactType.FINDINGS_REPORT: "synthesis",
    ArtifactType.RECOMMENDATION_MATRIX: "recommendations",
    ArtifactType.IMPLEMENTATION_ROADMAP: "implementation_roadmap",
    ArtifactType.RISK_REGISTER: "implementation_roadmap",
    ArtifactType.EXECUTIVE_SUMMARY: "executive_deliverable",
}


def _problem_statement(state: EngagementState) -> dict:
    p = state.problem
    return {
        "objective": p.objective,
        "scope": list(p.scope),
        "constraints": list(p.constraints),
        "risks": list(p.risks),
        "unknowns": list(p.unknowns),
    }


def _project_charter(state: EngagementState) -> dict:
    p = state.problem
    return {
        "category": state.category.value,
        "objective": p.objective,
        "stakeholders": list(p.stakeholders),
        "success_metrics": list(p.success_metrics),
        "scope": list(p.scope),
    }


def _issue_tree(state: EngagementState) -> dict:
    if state.issue_tree is None:
        return {"root_id": None, "nodes": [], "mece_validated": False}
    return {
        "root_id": state.issue_tree.root_id,
        "mece_validated": state.issue_tree.mece_validated,
        "nodes": [
            {
                "id": n.id,
                "question": n.question,
                "parent_id": n.parent_id,
                "hypothesis_ids": list(n.hypothesis_ids),
                "owner": n.owner,
            }
            for n in state.issue_tree.nodes.values()
        ],
    }


def _hypothesis_log(state: EngagementState) -> dict:
    return {
        "hypotheses": [
            {
                "id": h.id,
                "statement": h.statement,
                "confidence": h.confidence,
                "status": h.status.value,
                "evidence_ids": list(h.evidence_ids),
                "revision_count": len(h.revisions),
            }
            for h in state.hypotheses.values()
        ]
    }


def _assumption_register(state: EngagementState) -> dict:
    return {
        "assumptions": [
            {
                "id": a.id,
                "description": a.description,
                "owner": a.owner,
                "confidence": a.confidence,
                "validation_status": a.validation_status.value,
            }
            for a in state.assumptions.values()
        ]
    }


def _analysis_plan(state: EngagementState) -> dict:
    plan = state.analysis_plan
    return {
        "required_analyses": list(plan.required_analyses),
        "required_frameworks": list(plan.required_frameworks),
        "required_data": list(plan.required_data),
        "required_tools": list(plan.required_tools),
        "required_experts": list(plan.required_experts),
    }


def _interview_guide(state: EngagementState) -> dict:
    return {
        "stakeholders": list(state.problem.stakeholders),
        "open_unknowns": list(state.problem.unknowns),
    }


def _research_summary(state: EngagementState) -> dict:
    research = [
        e
        for e in state.evidence.values()
        if e.source_type
        in (EvidenceSourceType.EXTERNAL_RESEARCH, EvidenceSourceType.KNOWLEDGE_LIBRARY)
    ]
    return {
        "sources": [
            {
                "id": e.id,
                "source": e.source,
                "quality": e.quality.value,
                "confidence": e.confidence,
            }
            for e in research
        ]
    }


def _findings_report(state: EngagementState) -> dict:
    return {
        "findings": list(state.analysis_findings),
        "evidence_count": len(state.evidence),
        "hypotheses_resolved": [
            h.id for h in state.hypotheses.values() if h.status.value != "open"
        ],
    }


def _recommendation_matrix(state: EngagementState) -> dict:
    return {
        "recommendations": [
            {
                "id": r.id,
                "statement": r.statement,
                "expected_impact": r.expected_impact,
                "implementation_effort": r.implementation_effort,
                "confidence": r.confidence,
                "supporting_evidence_ids": list(r.supporting_evidence_ids),
            }
            for r in state.recommendations.values()
        ]
    }


def _implementation_roadmap(state: EngagementState) -> dict:
    return {
        "phases": [
            {
                "name": ph.name,
                "timeline": ph.timeline,
                "owners": list(ph.owners),
                "quick_win": ph.quick_win,
                "kpis": list(ph.kpis),
            }
            for ph in state.roadmap.phases
        ]
    }


def _risk_register(state: EngagementState) -> dict:
    return {
        "risks": [
            {
                "risk": r.risk,
                "likelihood": r.likelihood,
                "impact": r.impact,
                "mitigation": r.mitigation,
                "owner": r.owner,
            }
            for r in state.risk_register
        ]
    }


def _executive_summary(state: EngagementState) -> dict:
    recs = list(state.recommendations.values())
    return {
        "engagement_id": state.engagement_id,
        "category": state.category.value,
        "key_insights": list(state.analysis_findings)[:5],
        "strategic_recommendations": [r.statement for r in recs],
        "implementation_roadmap_phase_count": len(state.roadmap.phases),
        "appendices": ["hypothesis_log", "recommendation_matrix", "risk_register"],
    }


_GENERATORS = {
    ArtifactType.PROBLEM_STATEMENT: _problem_statement,
    ArtifactType.PROJECT_CHARTER: _project_charter,
    ArtifactType.ISSUE_TREE: _issue_tree,
    ArtifactType.HYPOTHESIS_LOG: _hypothesis_log,
    ArtifactType.ASSUMPTION_REGISTER: _assumption_register,
    ArtifactType.ANALYSIS_PLAN: _analysis_plan,
    ArtifactType.INTERVIEW_GUIDE: _interview_guide,
    ArtifactType.RESEARCH_SUMMARY: _research_summary,
    ArtifactType.FINDINGS_REPORT: _findings_report,
    ArtifactType.RECOMMENDATION_MATRIX: _recommendation_matrix,
    ArtifactType.IMPLEMENTATION_ROADMAP: _implementation_roadmap,
    ArtifactType.RISK_REGISTER: _risk_register,
    ArtifactType.EXECUTIVE_SUMMARY: _executive_summary,
}


def generate_artifact(state: EngagementState, artifact_type: ArtifactType) -> Artifact:
    """Build and store (into ``state.artifacts``) the named artifact from the
    engagement's current state."""
    from app.consulting.models import ConsultingStage

    content = _GENERATORS[artifact_type](state)
    artifact = Artifact(
        id=new_artifact_id(),
        type=artifact_type,
        stage=ConsultingStage(_STAGE_OF_ARTIFACT[artifact_type]),
        content=content,
        schema_version=ARTIFACT_SCHEMA_VERSION,
    )
    state.artifacts[artifact.id] = artifact
    return artifact
