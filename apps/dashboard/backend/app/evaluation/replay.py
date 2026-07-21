"""Case Replay Engine (requester's "Case Replay Engine" section).

Chains the five prior consulting layers — Workflow (``app.consulting``) ->
Knowledge (``app.knowledge``) -> Organization (``app.organization``) ->
Synthesis (``app.synthesis``) -> Deliverables (``app.deliverables``) —
using ONLY each layer's existing public API, the same way every layer's own
``integration.py`` already bridges one hop. This module is the first to
walk the FULL chain in one place, but introduces no new orchestration
primitive: every step below is a direct call to a function that already
existed before W12.

**What "deterministic mode" honestly means here:** this evaluation platform
performs no consulting reasoning (a hard, repeated W12 constraint), so the
analytical CONTENT flowing through the chain cannot be invented by this
module. In deterministic mode (the only mode this module implements), the
replay uses the benchmark case's OWN recorded ``expected_findings``/
``expected_recommendations`` as that content — which makes a replay a test
of whether the PIPELINE assembles already-known-good content into a valid,
traceable chain end-to-end, not a test of whether an AI can independently
reproduce that content. Judging the latter is what a LIVE run plus
``app.evaluation.evaluation``/``human_evaluation``/``ai_evaluation`` is for,
scored against a case, separately from replay itself.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import ConsultingStage, EvidenceQuality, EvidenceSourceType
from app.deliverables.generator import generate_deliverable
from app.deliverables.models import Audience
from app.deliverables.registry import DeliverableRegistry, default_deliverable_registry
from app.knowledge.execution import execute_framework
from app.knowledge.models import FrameworkExecutionRequest
from app.knowledge.registry import FrameworkRegistry, default_framework_registry
from app.organization.allocation import allocate_team
from app.organization.models import (
    AllocationContext,
    ReviewChecklistInput,
    ReviewStage,
)
from app.organization.registry import (
    OrganizationRegistry,
    default_organization_registry,
)
from app.organization.review import ReviewHistory, submit_for_review
from app.synthesis import quality as squality
from app.synthesis import tracking as stracking
from app.synthesis.business_impact import assess_business_impact
from app.synthesis.models import (
    BusinessImpactDimension,
    BusinessImpactEstimate,
    TradeOffOption,
)
from app.synthesis.narrative import build_strategic_narrative
from app.synthesis.state import SynthesisState
from app.synthesis.tradeoff import compare_options

from .errors import ReplayFailedError
from .models import BenchmarkCase, CaseReplayResult, new_replay_id


@dataclass
class ReplayContext:
    """Bundles the real registries a replay walks through, so a case
    replay doesn't reconstruct the full 87-framework/25-role catalogs on
    every call. Injectable so tests can supply small, fixed registries."""

    framework_registry: FrameworkRegistry
    organization_registry: OrganizationRegistry
    deliverable_registry: DeliverableRegistry

    @classmethod
    def default(cls) -> ReplayContext:
        return cls(
            framework_registry=default_framework_registry(),
            organization_registry=default_organization_registry(),
            deliverable_registry=default_deliverable_registry(),
        )


def _distribute_round_robin(items: tuple[str, ...], buckets: tuple[str, ...]) -> dict:
    """Assign each of ``items`` to one of ``buckets`` in turn — used to
    spread a case's recorded findings across its recorded frameworks
    without inventing any new content."""
    assigned: dict[str, list[str]] = {b: [] for b in buckets}
    if not buckets:
        return assigned
    for i, item in enumerate(items):
        assigned[buckets[i % len(buckets)]].append(item)
    return assigned


def replay_case(
    case: BenchmarkCase,
    *,
    context: ReplayContext | None = None,
    deterministic: bool = True,
    engagement_id: str | None = None,
) -> CaseReplayResult:
    """Replay one benchmark case end to end. Raises ``ReplayFailedError``
    only for a genuine execution failure (a framework's mandatory quality
    gates rejecting the case's own declared readiness, or a case with no
    expected findings/recommendations to replay) — never for a normal, if
    unimpressive, outcome."""
    result, _syn = _replay_case_impl(
        case,
        context=context,
        deterministic=deterministic,
        engagement_id=engagement_id,
    )
    return result


def replay_case_with_state(
    case: BenchmarkCase,
    *,
    context: ReplayContext | None = None,
    deterministic: bool = True,
    engagement_id: str | None = None,
) -> tuple[CaseReplayResult, SynthesisState]:
    """Same replay as ``replay_case``, but also returns the live
    ``SynthesisState`` the replay built — needed by
    ``app.evaluation.hallucination``, which reuses
    ``app.synthesis.consistency.validate_consistency`` and therefore needs
    the actual state object, not just its flattened ``CaseReplayResult``
    summary."""
    return _replay_case_impl(
        case,
        context=context,
        deterministic=deterministic,
        engagement_id=engagement_id,
    )


def _replay_case_impl(
    case: BenchmarkCase,
    *,
    context: ReplayContext | None = None,
    deterministic: bool = True,
    engagement_id: str | None = None,
) -> tuple[CaseReplayResult, SynthesisState]:
    if not deterministic:
        raise ReplayFailedError(
            "app.evaluation.replay only implements deterministic replay; "
            "a live (non-deterministic) executor is not yet wired"
        )
    if not case.expected_findings:
        raise ReplayFailedError(f"case {case.case_id!r} declares no expected_findings")
    if not case.expected_recommendations:
        raise ReplayFailedError(
            f"case {case.case_id!r} declares no expected_recommendations"
        )

    ctx = context or ReplayContext.default()
    started = time.monotonic()
    engagement_id = engagement_id or f"replay::{case.case_id}::{case.version}"

    # ---- Workflow: start the engagement -------------------------------
    engine = ConsultingEngine()
    cstate = engine.start_engagement(
        engagement_id, case.engagement_type, trace_id=engagement_id
    )

    # ---- Knowledge: execute every framework the case expects -----------
    finding_buckets = _distribute_round_robin(
        case.expected_findings, case.expected_frameworks
    )
    selected_frameworks: list[str] = []
    for framework_id in case.expected_frameworks:
        framework = ctx.framework_registry.get(framework_id)
        request = FrameworkExecutionRequest(
            provided_inputs=framework.required_inputs,
            provided_evidence=framework.required_evidence,
            completed_dependency_ids=tuple(selected_frameworks),
            findings=tuple(finding_buckets.get(framework_id, ())),
            confidence=0.75,
        )
        result = execute_framework(framework, request)
        if not result.success:
            raise ReplayFailedError(
                f"case {case.case_id!r}: framework {framework_id!r} failed "
                f"execution readiness gates: {result.error}"
            )
        cstate.analysis_findings.extend(result.findings)
        selected_frameworks.append(framework_id)

    # ---- Organization: allocate a team ---------------------------------
    allocation = allocate_team(
        AllocationContext(
            engagement_type=case.engagement_type,
            workflow_stage=ConsultingStage.ANALYSIS_EXECUTION,
            frameworks_selected=tuple(selected_frameworks),
            industry=case.industry,
            company_size=case.company_size,
        ),
        ctx.organization_registry,
    )
    role_assignments = tuple(a.role_id for a in allocation.recommended_team)

    # ---- Synthesis: evidence -> finding -> recommendation --------------
    syn = SynthesisState(engagement_state=cstate)
    evidence_ids = tuple(
        ctracking.add_evidence(
            cstate,
            source=f"benchmark:{case.case_id}",
            source_type=EvidenceSourceType.STRUCTURED_DATA,
            quality=EvidenceQuality.HIGH,
            confidence=0.8,
            content=statement,
        ).id
        for statement in case.expected_findings
    )
    finding_ids = tuple(
        stracking.create_finding(
            syn, statement, (evidence_id,), 0.8, "benchmark replay"
        ).id
        for statement, evidence_id in zip(
            case.expected_findings, evidence_ids, strict=True
        )
    )
    recommendation_ids = tuple(
        stracking.create_recommendation(
            syn,
            statement,
            case.ground_truth,
            finding_ids,
            evidence_ids,
            expected_benefits=(case.ground_truth,),
            risk=f"principal execution risk for: {case.title}",
            kpis=("engagement_quality_score", "time_to_recommendation_days"),
            trade_offs=("status quo (do nothing)",),
            cost="see business case appendix",
        ).id
        for statement in case.expected_recommendations
    )

    for rec_id in recommendation_ids:
        assessment = assess_business_impact(
            rec_id,
            (
                BusinessImpactEstimate(
                    dimension=BusinessImpactDimension.STRATEGIC,
                    estimate=case.ground_truth,
                    confidence=0.7,
                ),
            ),
        )
        syn.business_impact_assessments[assessment.id] = assessment

    # ---- Synthesis: one implementation theme + trade-off + narrative --
    # Built generically from the case's own recorded content so that ANY
    # of the 20 deliverable types (some of which require an
    # implementation_roadmap, trade_off_analysis, or SCR section) can be
    # requested in ``expected_deliverables`` without per-case plumbing.
    stracking.create_implementation_theme(
        syn,
        f"Deliver: {case.title}",
        case.ground_truth,
        recommendation_ids,
    )
    trade_off_result = compare_options(
        (
            TradeOffOption(
                id="recommended",
                name=case.expected_recommendations[0],
                dimension_scores={"financial": 8.0, "risk": 6.0},
            ),
            TradeOffOption(
                id="status_quo",
                name="Do nothing",
                dimension_scores={"financial": 3.0, "risk": 3.0},
            ),
        )
    )
    syn.trade_off_results.append(trade_off_result)
    narrative = build_strategic_narrative(
        syn,
        case.problem_statement,
        case.expected_recommendations,
        (case.ground_truth,),
        tuple(r.risk for r in syn.recommendations.values() if r.risk),
        case.ground_truth,
    )

    # ---- Organization: one peer review pass ----------------------------
    review_history = ReviewHistory()
    peer_reviewer = next(
        (
            role
            for role in ctx.organization_registry.list()
            if ReviewStage.PEER in role.review_authority
        ),
        None,
    )
    if peer_reviewer is not None:
        review_history.record(
            submit_for_review(
                engagement_id, ReviewStage.PEER, peer_reviewer, ReviewChecklistInput()
            )
        )
    review_iterations = review_history.iteration_count(engagement_id)

    # ---- Deliverables: generate every deliverable the case expects -----
    deliverable_ids: list[str] = []
    deliverables_generated: list = []
    for deliverable_type in case.expected_deliverables:
        deliverable = generate_deliverable(
            deliverable_type,
            syn,
            Audience.CEO,
            ctx.deliverable_registry,
            narrative_id=narrative.id,
            trade_off_result=trade_off_result,
        )
        deliverable_ids.append(deliverable.id)
        deliverables_generated.append(deliverable_type)

    quality_report = squality.assess_quality(syn)
    quality_metrics = {
        "synthesis_overall_score": quality_report.overall_score,
        **{c.dimension.value: c.score for c in quality_report.checks},
    }

    result = CaseReplayResult(
        id=new_replay_id(),
        case_id=case.case_id,
        case_version=case.version,
        engagement_id=engagement_id,
        execution_time_s=time.monotonic() - started,
        selected_frameworks=tuple(selected_frameworks),
        role_assignments=role_assignments,
        review_iterations=review_iterations,
        findings=case.expected_findings,
        recommendations=case.expected_recommendations,
        deliverables_generated=tuple(deliverables_generated),
        quality_metrics=quality_metrics,
        deterministic=deterministic,
        deliverable_ids=tuple(deliverable_ids),
    )
    return result, syn
