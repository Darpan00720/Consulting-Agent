"""Presentation model (requester's "Presentation Model" section) — all 9
named visual types, each built FROM real synthesis/knowledge objects.
"Visuals reference existing data only" is enforced by construction: every
builder takes real objects (or ids that must already exist in the caller's
state) and derives ``VisualSpec.data`` from their actual fields — none of
these functions accept free-text content to render.
"""

from __future__ import annotations

from app.deliverables.errors import MissingTraceabilityError
from app.deliverables.models import VisualSpec, VisualType, new_visual_id
from app.knowledge.models import FrameworkExecutionResult
from app.synthesis.models import (
    Finding,
    ImplementationTheme,
    Recommendation,
    RootCauseAnalysis,
    TradeOffResult,
)


def build_chart_from_business_impact(assessment) -> VisualSpec:
    data = {
        "dimensions": [e.dimension.value for e in assessment.estimates],
        "values": [e.estimated_value for e in assessment.estimates],
        "confidences": [e.confidence for e in assessment.estimates],
    }
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.CHART,
        title="Business Impact by Dimension",
        data_refs=(assessment.id,),
        data=data,
    )


def build_table_from_findings(findings: tuple[Finding, ...]) -> VisualSpec:
    rows = [
        (f.statement, f"{f.confidence:.2f}", str(len(f.supporting_evidence_ids)))
        for f in findings
    ]
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.TABLE,
        title="Key Findings",
        data_refs=tuple(f.id for f in findings),
        data={"columns": ("finding", "confidence", "evidence_count"), "rows": rows},
    )


def build_framework_visual(result: FrameworkExecutionResult) -> VisualSpec:
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.FRAMEWORK_VISUAL,
        title=f"{result.framework_id} — Analysis",
        data_refs=(result.id,),
        data={
            "framework_id": result.framework_id,
            "findings": list(result.findings),
            "calculations": dict(result.calculations),
            "confidence": result.confidence,
        },
    )


def build_roadmap(themes: tuple[ImplementationTheme, ...]) -> VisualSpec:
    phases = [
        {"name": t.name, "timeline": t.timeline, "workstreams": list(t.workstreams)}
        for t in themes
    ]
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.ROADMAP,
        title="Implementation Roadmap",
        data_refs=tuple(t.id for t in themes),
        data={"phases": phases},
    )


def build_matrix_from_trade_off(trade_off: TradeOffResult) -> VisualSpec:
    data = {
        "options": [o.name for o in trade_off.options],
        "dimensions": list(trade_off.dimension_weights.keys()),
        "scores": {
            o.id: {
                dim: o.dimension_scores.get(dim, 0.0)
                for dim in trade_off.dimension_weights
            }
            for o in trade_off.options
        },
        "ranked_option_ids": list(trade_off.ranked_option_ids),
    }
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.MATRIX,
        title="Options Trade-off Matrix",
        data_refs=tuple(o.id for o in trade_off.options),
        data=data,
    )


def build_timeline(themes: tuple[ImplementationTheme, ...]) -> VisualSpec:
    entries = [{"name": t.name, "timeline": t.timeline} for t in themes]
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.TIMELINE,
        title="Execution Timeline",
        data_refs=tuple(t.id for t in themes),
        data={"entries": entries},
    )


def build_decision_tree(rca: RootCauseAnalysis) -> VisualSpec:
    nodes = [
        {
            "id": n.id,
            "statement": n.statement,
            "parent_id": n.parent_id,
            "is_root_cause": n.id in rca.root_cause_ids,
        }
        for n in rca.nodes
    ]
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.DECISION_TREE,
        title=f"Root Cause Analysis — {rca.method.value}",
        data_refs=(rca.id,),
        data={"problem_statement": rca.problem_statement, "nodes": nodes},
    )


def build_risk_heatmap(
    recommendations: tuple[Recommendation, ...], risk_scores: dict
) -> VisualSpec:
    """``risk_scores`` maps recommendation id -> (likelihood, impact) —
    assigning a NUMERIC score to a risk is itself a judgment call (the same
    "generic math over caller-supplied judgment" split every scoring tool in
    this build already makes); every key MUST correspond to a recommendation
    actually passed in, so the heatmap can never reference a risk that isn't
    real."""
    known_ids = {r.id for r in recommendations}
    missing = set(risk_scores) - known_ids
    if missing:
        raise MissingTraceabilityError(
            f"risk_scores references recommendation ids not provided: {sorted(missing)}"
        )
    entries = [
        {
            "recommendation_id": r.id,
            "risk": r.risk,
            "likelihood": risk_scores.get(r.id, (0.0, 0.0))[0],
            "impact": risk_scores.get(r.id, (0.0, 0.0))[1],
        }
        for r in recommendations
        if r.id in risk_scores
    ]
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.RISK_HEATMAP,
        title="Risk Heatmap",
        data_refs=tuple(risk_scores.keys()),
        data={"entries": entries},
    )


def build_implementation_wave(themes: tuple[ImplementationTheme, ...]) -> VisualSpec:
    """Groups themes into waves by their existing ``timeline`` string —
    distinct timeline values become distinct waves, a real (not invented)
    grouping of the theme's own declared timing."""
    waves: dict[str, list[str]] = {}
    for t in themes:
        waves.setdefault(t.timeline or "unscheduled", []).append(t.name)
    return VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.IMPLEMENTATION_WAVE,
        title="Implementation Waves",
        data_refs=tuple(t.id for t in themes),
        data={"waves": waves},
    )
