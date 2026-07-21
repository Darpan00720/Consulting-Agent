"""The seam into the Workflow Engine (W7), Knowledge Library (W8),
Organization Layer (W9), and Memory Platform — this module CALLS INTO their
existing public APIs; it does not modify a single line of any of them
(verified in ``tests/test_synthesis_architecture_compliance.py``).

Four bridges:

- ``create_finding_from_framework_result`` consumes a REAL
  ``app.knowledge.models.FrameworkExecutionResult`` (W8) — the Synthesis
  Engine's evidence for "consume outputs from ... frameworks."
- ``assign_finding_owner`` / ``request_recommendation_approval`` consume the
  REAL ``app.organization`` registry/governance (W9) — "consume outputs from
  ... consulting roles," including a genuine approval-authority check.
- ``checkpoint_synthesis`` / ``resume_synthesis`` persist through the
  EXISTING ``MemoryService``/``CheckpointAdapter`` (Memory Platform),
  reusing ``MemoryType.CONSULTING`` — no new memory type, no new
  persistence path.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.consulting.serialization import (
    deserialize_state as deserialize_engagement_state,
)
from app.consulting.serialization import serialize_state as serialize_engagement_state
from app.knowledge.models import FrameworkExecutionResult
from app.organization.governance import DelegationLedger, request_approval
from app.organization.models import DecisionType
from app.organization.registry import OrganizationRegistry
from app.synthesis.errors import SynthesisError, UnknownRecommendationError
from app.synthesis.models import ApprovalStatus, ConsultingStage, Finding, FindingStatus
from app.synthesis.state import SynthesisState
from app.synthesis.tracking import create_finding

_CHECKPOINT_KEY_SUFFIX = "synthesis::latest"


def create_finding_from_framework_result(
    state: SynthesisState,
    result: FrameworkExecutionResult,
    evidence_ids: tuple[str, ...],
    *,
    business_impact: str = "",
    affected_stakeholders: tuple[str, ...] = (),
    related_workflow_stages: tuple[ConsultingStage, ...] = (),
    owner: str = "",
) -> Finding:
    """Bridges a completed W8 framework execution into a real, evidence-
    linked Finding. ``evidence_ids`` must already exist in the underlying
    engagement (typically the ``Evidence`` records
    ``app.knowledge.integration.apply_framework_result`` created from this
    SAME ``result`` — the caller wires the two together, this function
    doesn't re-derive it, since guessing which evidence belongs to which
    finding is exactly the judgment call this package never makes)."""
    if not result.success:
        raise SynthesisError(
            "cannot build a finding from a failed framework execution "
            f"({result.framework_id})"
        )
    statement = "; ".join(result.findings) if result.findings else result.framework_id
    return create_finding(
        state,
        statement,
        evidence_ids,
        result.confidence,
        business_impact,
        affected_stakeholders=affected_stakeholders,
        related_frameworks=(result.framework_id,),
        related_workflow_stages=related_workflow_stages,
        owner=owner,
        status=FindingStatus.DRAFT,
    )


def assign_finding_owner(
    state: SynthesisState, finding_id: str, role_id: str, registry: OrganizationRegistry
) -> Finding:
    """Validates ``role_id`` against the REAL organization registry before
    assigning ownership — an unknown role raises (via ``registry.get``),
    the same referential-integrity discipline every mutator in this
    package already applies to its own chain."""
    registry.get(role_id)  # raises UnknownRoleError if not registered
    if finding_id not in state.findings:
        raise SynthesisError(f"no finding {finding_id!r} in this synthesis state")
    updated = dataclasses.replace(state.findings[finding_id], owner=role_id)
    state.findings[finding_id] = updated
    return updated


def request_recommendation_approval(
    state: SynthesisState,
    recommendation_id: str,
    registry: OrganizationRegistry,
    *,
    decision: DecisionType = DecisionType.APPROVE_RECOMMENDATIONS,
    delegations: DelegationLedger | None = None,
):
    """Delegates the ENTIRE approval decision to the real
    ``app.organization.governance.request_approval`` (escalation chain,
    delegation, everything) — this function only translates its
    ``ApprovalOutcome`` into the recommendation's own ``approval_status``
    field. Raises if the recommendation's ``owner`` isn't a real,
    registered role (``UnknownRoleError``, from the registry itself)."""
    if recommendation_id not in state.recommendations:
        raise UnknownRecommendationError(f"no recommendation {recommendation_id!r}")
    recommendation = state.recommendations[recommendation_id]
    if not recommendation.owner:
        raise SynthesisError(
            f"recommendation {recommendation_id!r} has no owner role assigned"
        )
    registry.get(recommendation.owner)  # raises UnknownRoleError if not registered

    outcome = request_approval(
        registry, recommendation.owner, decision, delegations=delegations
    )
    # ESCALATED means "still unresolved" (nobody in the reporting chain held
    # authority) — a resolution FOUND via escalation (outcome.escalated=True
    # but approved_by_role_id is set) is still a real approval, not a stall.
    new_status = (
        ApprovalStatus.ESCALATED
        if outcome.approved_by_role_id is None
        else ApprovalStatus.APPROVED
    )

    updated = dataclasses.replace(recommendation, approval_status=new_status)
    state.recommendations[recommendation_id] = updated
    return updated, outcome


# ---- Memory Platform checkpoint/resume (no new persistence path) ----------


def _checkpoint_key(engagement_id: str) -> str:
    return f"{engagement_id}::{_CHECKPOINT_KEY_SUFFIX}"


def serialize_synthesis_state(state: SynthesisState) -> dict[str, Any]:
    payload = dataclasses.asdict(state)
    payload["engagement_state"] = serialize_engagement_state(state.engagement_state)
    return payload


def deserialize_synthesis_state(data: dict[str, Any]) -> SynthesisState:
    from app.synthesis.models import (
        BusinessImpactAssessment,
        BusinessImpactEstimate,
        ImplementationTheme,
        Insight,
        Opportunity,
        Recommendation,
        StrategicNarrative,
        TradeOffOption,
        TradeOffResult,
    )
    from app.synthesis.models import (
        Finding as _Finding,
    )

    engagement_state = deserialize_engagement_state(data["engagement_state"])

    def _finding(d: dict) -> _Finding:
        d = dict(d)
        d["status"] = FindingStatus(d["status"])
        d["related_workflow_stages"] = tuple(
            ConsultingStage(s) for s in d["related_workflow_stages"]
        )
        for key in (
            "supporting_evidence_ids",
            "affected_stakeholders",
            "assumptions",
            "limitations",
            "related_frameworks",
        ):
            d[key] = tuple(d[key])
        return _Finding(**d)

    def _insight(d: dict) -> Insight:
        d = dict(d)
        for key in (
            "supporting_finding_ids",
            "drivers",
            "root_causes",
            "dependencies",
            "strategic_implications",
            "alternative_interpretations",
            "contradictory_evidence_ids",
        ):
            d[key] = tuple(d[key])
        return Insight(**d)

    def _opportunity(d: dict) -> Opportunity:
        from app.synthesis.models import TimeHorizon

        d = dict(d)
        d["time_horizon"] = TimeHorizon(d["time_horizon"])
        for key in ("supporting_insight_ids", "dependencies"):
            d[key] = tuple(d[key])
        return Opportunity(**d)

    def _recommendation(d: dict) -> Recommendation:
        d = dict(d)
        d["approval_status"] = ApprovalStatus(d["approval_status"])
        for key in (
            "supporting_opportunity_ids",
            "supporting_insight_ids",
            "supporting_finding_ids",
            "supporting_evidence_ids",
            "expected_benefits",
            "trade_offs",
            "kpis",
            "contradicts",
        ):
            d[key] = tuple(d[key])
        return Recommendation(**d)

    def _theme(d: dict) -> ImplementationTheme:
        d = dict(d)
        d["supporting_recommendation_ids"] = tuple(d["supporting_recommendation_ids"])
        d["workstreams"] = tuple(d["workstreams"])
        return ImplementationTheme(**d)

    def _narrative(d: dict) -> StrategicNarrative:
        d = dict(d)
        for key in (
            "key_finding_ids",
            "core_insight_ids",
            "strategic_choices",
            "recommendation_ids",
            "implementation_theme_ids",
            "expected_outcomes",
            "risks",
        ):
            d[key] = tuple(d[key])
        return StrategicNarrative(**d)

    def _bia(d: dict) -> BusinessImpactAssessment:
        from app.synthesis.models import BusinessImpactDimension

        d = dict(d)
        d["estimates"] = tuple(
            BusinessImpactEstimate(
                dimension=BusinessImpactDimension(e["dimension"]),
                estimate=e["estimate"],
                confidence=e["confidence"],
                estimated_value=e["estimated_value"],
                rationale=e["rationale"],
            )
            for e in d["estimates"]
        )
        return BusinessImpactAssessment(**d)

    def _trade_off(d: dict) -> TradeOffResult:
        d = dict(d)
        d["options"] = tuple(
            TradeOffOption(
                id=o["id"],
                name=o["name"],
                dimension_scores=o["dimension_scores"],
                notes=tuple(o["notes"]),
            )
            for o in d["options"]
        )
        d["ranked_option_ids"] = tuple(d["ranked_option_ids"])
        d["reasoning"] = tuple(d["reasoning"])
        return TradeOffResult(**d)

    return SynthesisState(
        engagement_state=engagement_state,
        findings={k: _finding(v) for k, v in data["findings"].items()},
        insights={k: _insight(v) for k, v in data["insights"].items()},
        opportunities={k: _opportunity(v) for k, v in data["opportunities"].items()},
        recommendations={
            k: _recommendation(v) for k, v in data["recommendations"].items()
        },
        implementation_themes={
            k: _theme(v) for k, v in data["implementation_themes"].items()
        },
        narratives={k: _narrative(v) for k, v in data["narratives"].items()},
        business_impact_assessments={
            k: _bia(v) for k, v in data["business_impact_assessments"].items()
        },
        trade_off_results=[_trade_off(v) for v in data["trade_off_results"]],
    )


async def checkpoint_synthesis(state: SynthesisState, memory_service=None):
    """Persists ``SynthesisState`` through the EXISTING Memory Platform —
    the same ``app.memory.checkpoint`` helper
    ``app.consulting.engine.checkpoint`` already uses, under
    ``MemoryType.CONSULTING`` (no new memory type)."""
    from app.memory.checkpoint import store_checkpoint

    engagement_id = state.engagement_state.engagement_id
    payload = serialize_synthesis_state(state)
    return await store_checkpoint(
        _checkpoint_key(engagement_id),
        payload,
        trace_id=state.engagement_state.trace_id,
        metadata={"engagement_id": engagement_id},
        memory_service=memory_service,
    )


async def resume_synthesis(engagement_id: str, memory_service=None) -> SynthesisState:
    from app.memory.checkpoint import load_checkpoint
    from app.synthesis.errors import SynthesisError as _SynthesisError

    value = await load_checkpoint(_checkpoint_key(engagement_id), memory_service)
    if value is None:
        raise _SynthesisError(
            f"no synthesis checkpoint found for engagement {engagement_id!r}"
        )
    return deserialize_synthesis_state(value)
