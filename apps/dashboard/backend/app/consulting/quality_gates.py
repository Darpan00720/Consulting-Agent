"""Standard quality gates (requester's "Quality Gates" section) — one gate per
stage, each running the named checks the requester's examples specified.
"Workflow progression must stop if mandatory quality gates fail" is enforced
by ``engine.ConsultingEngine.advance_stage`` calling ``stage_gates_pass``
before moving ``current_stage`` forward — never by a gate raising.
"""

from __future__ import annotations

from app.consulting.models import (
    ConsultingStage,
    EvidenceQuality,
    HypothesisStatus,
    QualityGateCheckResult,
    QualityGateResult,
)
from app.consulting.state import EngagementState
from app.consulting.workflow import QualityGate

_C = ConsultingStage


def _result(
    gate_id: str, stage: _C, mandatory: bool, checks: list[QualityGateCheckResult]
) -> QualityGateResult:
    return QualityGateResult(
        gate_id=gate_id,
        stage=stage,
        mandatory=mandatory,
        passed=all(c.passed for c in checks),
        checks=tuple(checks),
    )


def _check_problem_definition(state: EngagementState) -> QualityGateResult:
    p = state.problem
    checks = [
        QualityGateCheckResult("objective_defined", bool(p.objective.strip())),
        QualityGateCheckResult("scope_defined", bool(p.scope)),
        QualityGateCheckResult("stakeholders_defined", bool(p.stakeholders)),
    ]
    return _result("gate.problem_definition", _C.PROBLEM_DEFINITION, True, checks)


def _check_hypothesis_development(state: EngagementState) -> QualityGateResult:
    has_hypotheses = len(state.hypotheses) > 0
    checks = [
        QualityGateCheckResult("hypotheses_documented", has_hypotheses),
        QualityGateCheckResult(
            "rationale_recorded",
            has_hypotheses
            and all(h.rationale.strip() for h in state.hypotheses.values()),
        ),
    ]
    return _result(
        "gate.hypothesis_development", _C.HYPOTHESIS_DEVELOPMENT, True, checks
    )


def _check_issue_tree(state: EngagementState) -> QualityGateResult:
    checks = [
        QualityGateCheckResult(
            "mece_validated",
            state.issue_tree is not None and state.issue_tree.mece_validated,
        ),
    ]
    return _result("gate.issue_tree", _C.ISSUE_TREE_CONSTRUCTION, True, checks)


def _check_analysis_planning(state: EngagementState) -> QualityGateResult:
    plan = state.analysis_plan
    checks = [
        QualityGateCheckResult(
            "required_analyses_defined", bool(plan.required_analyses)
        ),
        QualityGateCheckResult(
            "required_frameworks_defined", bool(plan.required_frameworks)
        ),
    ]
    return _result("gate.analysis_planning", _C.ANALYSIS_PLANNING, True, checks)


def _check_evidence_collection(state: EngagementState) -> QualityGateResult:
    has_evidence = len(state.evidence) > 0
    sufficient_quality = any(
        e.quality in (EvidenceQuality.HIGH, EvidenceQuality.MEDIUM)
        for e in state.evidence.values()
    )
    checks = [
        QualityGateCheckResult("evidence_present", has_evidence),
        QualityGateCheckResult(
            "evidence_quality_sufficient", has_evidence and sufficient_quality
        ),
    ]
    return _result("gate.evidence_collection", _C.EVIDENCE_COLLECTION, True, checks)


def _check_analysis_execution(state: EngagementState) -> QualityGateResult:
    findings_tracked = len(state.analysis_findings) > 0
    assumptions_well_formed = all(
        a.owner.strip() and a.source.strip() for a in state.assumptions.values()
    )
    checks = [
        QualityGateCheckResult("intermediate_findings_tracked", findings_tracked),
        QualityGateCheckResult("assumptions_documented", assumptions_well_formed),
    ]
    return _result("gate.analysis_execution", _C.ANALYSIS_EXECUTION, True, checks)


def _check_synthesis(state: EngagementState) -> QualityGateResult:
    findings_combined = len(state.analysis_findings) > 0
    hypotheses_resolved = any(
        h.status is not HypothesisStatus.OPEN for h in state.hypotheses.values()
    )
    checks = [
        QualityGateCheckResult("findings_combined", findings_combined),
        QualityGateCheckResult("hypotheses_resolved", hypotheses_resolved),
    ]
    return _result("gate.synthesis", _C.SYNTHESIS, True, checks)


def _check_recommendations(state: EngagementState) -> QualityGateResult:
    recs = list(state.recommendations.values())
    has_recs = len(recs) > 0
    checks = [
        QualityGateCheckResult("recommendations_present", has_recs),
        QualityGateCheckResult(
            "evidence_linked", has_recs and all(r.supporting_evidence_ids for r in recs)
        ),
        QualityGateCheckResult(
            "tradeoffs_identified", has_recs and all(r.tradeoffs for r in recs)
        ),
        QualityGateCheckResult(
            "confidence_assigned", has_recs and all(r.confidence > 0 for r in recs)
        ),
    ]
    return _result("gate.recommendations", _C.RECOMMENDATIONS, True, checks)


def _check_implementation_roadmap(state: EngagementState) -> QualityGateResult:
    phases = state.roadmap.phases
    checks = [
        QualityGateCheckResult(
            "roadmap_complete",
            len(phases) > 0 and all(p.timeline and p.owners for p in phases),
        ),
        QualityGateCheckResult("kpis_defined", any(p.kpis for p in phases)),
    ]
    return _result(
        "gate.implementation_roadmap", _C.IMPLEMENTATION_ROADMAP, True, checks
    )


def _check_executive_deliverable(state: EngagementState) -> QualityGateResult:
    evidence_ids = set(state.evidence.keys())
    recs = list(state.recommendations.values())
    referenced_evidence_ok = all(
        set(r.supporting_evidence_ids) <= evidence_ids for r in recs
    )
    hyp_evidence_ok = all(
        set(h.evidence_ids) <= evidence_ids for h in state.hypotheses.values()
    )
    executive_ready = len(recs) > 0 and len(state.roadmap.phases) > 0
    checks = [
        QualityGateCheckResult(
            "internally_consistent", referenced_evidence_ok and hyp_evidence_ok
        ),
        QualityGateCheckResult("executive_ready", executive_ready),
    ]
    return _result("gate.executive_deliverable", _C.EXECUTIVE_DELIVERABLE, True, checks)


_CHECK_BY_STAGE = {
    _C.PROBLEM_DEFINITION: _check_problem_definition,
    _C.HYPOTHESIS_DEVELOPMENT: _check_hypothesis_development,
    _C.ISSUE_TREE_CONSTRUCTION: _check_issue_tree,
    _C.ANALYSIS_PLANNING: _check_analysis_planning,
    _C.EVIDENCE_COLLECTION: _check_evidence_collection,
    _C.ANALYSIS_EXECUTION: _check_analysis_execution,
    _C.SYNTHESIS: _check_synthesis,
    _C.RECOMMENDATIONS: _check_recommendations,
    _C.IMPLEMENTATION_ROADMAP: _check_implementation_roadmap,
    _C.EXECUTIVE_DELIVERABLE: _check_executive_deliverable,
}


def standard_gates() -> tuple[QualityGate, ...]:
    """One ``QualityGate`` per stage, wrapping the check functions above —
    what ``workflow.standard_workflow`` registers for every category."""
    gates = []
    for stage, fn in _CHECK_BY_STAGE.items():
        gate_id = f"gate.{stage.value}"
        label = stage.value.replace("_", " ")
        gates.append(
            QualityGate(
                id=gate_id,
                stage=stage,
                description=f"Standard completion checks for {label}",
                mandatory=True,
                check=fn,
            )
        )
    return tuple(gates)


def evaluate_stage_gates(
    stage: ConsultingStage, state: EngagementState, gates: tuple[QualityGate, ...]
) -> tuple[QualityGateResult, ...]:
    """Run every gate declared for ``stage`` (a workflow may declare zero —
    an optional stage with no mandatory gate is legal)."""
    return tuple(gate.check(state) for gate in gates if gate.stage is stage)


def stage_gates_pass(
    stage: ConsultingStage, state: EngagementState, gates: tuple[QualityGate, ...]
) -> bool:
    """True iff every MANDATORY gate for this stage passed. A non-mandatory
    gate failing never blocks progression — it is advisory."""
    results = evaluate_stage_gates(stage, state, gates)
    return all(r.passed for r in results if r.mandatory)
