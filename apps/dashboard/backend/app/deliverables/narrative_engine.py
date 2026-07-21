"""Narrative presentation engine (requester's "Narrative Engine" section):
Situation-Complication-Resolution plus business impact/implementation/
expected outcomes/risks/dependencies — assembled ENTIRELY from a real
``app.synthesis.StrategicNarrative`` and the recommendations/findings/
themes it references. No prose is invented: every field below is either a
direct copy of real synthesized text or a join of real statements from
objects the narrative already cites.
"""

from __future__ import annotations

from app.deliverables.errors import MissingTraceabilityError
from app.deliverables.models import NarrativeStructure
from app.synthesis.state import SynthesisState


def build_narrative_structure(
    state: SynthesisState, narrative_id: str
) -> NarrativeStructure:
    if narrative_id not in state.narratives:
        raise MissingTraceabilityError(
            f"no strategic narrative {narrative_id!r} in synthesis state"
        )
    narrative = state.narratives[narrative_id]

    findings = [
        state.findings[fid]
        for fid in narrative.key_finding_ids
        if fid in state.findings
    ]
    recommendations = [
        state.recommendations[rid]
        for rid in narrative.recommendation_ids
        if rid in state.recommendations
    ]
    themes = [
        state.implementation_themes[tid]
        for tid in narrative.implementation_theme_ids
        if tid in state.implementation_themes
    ]

    if not recommendations:
        raise MissingTraceabilityError(
            f"narrative {narrative_id!r} references no recommendations "
            "currently in state"
        )

    complication = (
        "; ".join(f.statement for f in findings) or narrative.current_situation
    )
    resolution = "; ".join(r.statement for r in recommendations)
    business_impact = tuple(b for r in recommendations for b in r.expected_benefits)
    implementation = tuple(t.description for t in themes)
    dependencies = tuple(w for t in themes for w in t.workstreams)
    risks = tuple(narrative.risks) + tuple(r.risk for r in recommendations if r.risk)

    return NarrativeStructure(
        situation=narrative.current_situation,
        complication=complication,
        resolution=resolution,
        business_impact=business_impact,
        implementation=implementation,
        expected_outcomes=narrative.expected_outcomes,
        risks=risks,
        dependencies=dependencies,
        source_narrative_id=narrative.id,
        source_recommendation_ids=tuple(r.id for r in recommendations),
    )
