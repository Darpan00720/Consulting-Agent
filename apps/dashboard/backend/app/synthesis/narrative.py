"""Strategic narrative builder (requester's "Strategic Narrative" section).

Assembles a ``StrategicNarrative`` that REFERENCES real findings/insights/
recommendations/themes already created in the ``SynthesisState`` — never
free-standing text. The genuinely judgment-driven sections (current
situation, strategic choices, expected outcomes, risks, executive summary)
are caller-supplied prose, the same "structure real content, never invent
it" boundary ``app.consulting.artifacts`` already drew for engagement
artifacts one layer down.
"""

from __future__ import annotations

from app.synthesis.errors import (
    UnknownFindingError,
    UnknownImplementationThemeError,
    UnknownInsightError,
    UnknownRecommendationError,
)
from app.synthesis.models import StrategicNarrative, new_narrative_id
from app.synthesis.state import SynthesisState


def build_strategic_narrative(
    state: SynthesisState,
    current_situation: str,
    strategic_choices: tuple[str, ...],
    expected_outcomes: tuple[str, ...],
    risks: tuple[str, ...],
    executive_summary: str,
    *,
    key_finding_ids: tuple[str, ...] | None = None,
    core_insight_ids: tuple[str, ...] | None = None,
    recommendation_ids: tuple[str, ...] | None = None,
    implementation_theme_ids: tuple[str, ...] | None = None,
) -> StrategicNarrative:
    """Any of the four id sets left as ``None`` defaults to EVERYTHING
    currently in the synthesis state at that layer — the narrative
    references the full chain by default, and a caller only needs to curate
    a subset when they deliberately want to narrow the story."""
    finding_ids = tuple(state.findings) if key_finding_ids is None else key_finding_ids
    insight_ids = (
        tuple(state.insights) if core_insight_ids is None else core_insight_ids
    )
    rec_ids = (
        tuple(state.recommendations)
        if recommendation_ids is None
        else recommendation_ids
    )
    theme_ids = (
        tuple(state.implementation_themes)
        if implementation_theme_ids is None
        else implementation_theme_ids
    )

    missing_findings = set(finding_ids) - set(state.findings.keys())
    if missing_findings:
        raise UnknownFindingError(f"finding ids not found: {sorted(missing_findings)}")
    missing_insights = set(insight_ids) - set(state.insights.keys())
    if missing_insights:
        raise UnknownInsightError(f"insight ids not found: {sorted(missing_insights)}")
    missing_recs = set(rec_ids) - set(state.recommendations.keys())
    if missing_recs:
        raise UnknownRecommendationError(
            f"recommendation ids not found: {sorted(missing_recs)}"
        )
    missing_themes = set(theme_ids) - set(state.implementation_themes.keys())
    if missing_themes:
        raise UnknownImplementationThemeError(
            f"implementation theme ids not found: {sorted(missing_themes)}"
        )

    narrative = StrategicNarrative(
        id=new_narrative_id(),
        current_situation=current_situation,
        key_finding_ids=finding_ids,
        core_insight_ids=insight_ids,
        strategic_choices=strategic_choices,
        recommendation_ids=rec_ids,
        implementation_theme_ids=theme_ids,
        expected_outcomes=expected_outcomes,
        risks=risks,
        executive_summary=executive_summary,
    )
    state.narratives[narrative.id] = narrative
    return narrative
