"""Section generation (requester's "Design Principles": "deliverables never
perform consulting reasoning; every section should reference supporting
recommendations"). Every builder below assembles content EXCLUSIVELY from
real ``app.synthesis`` objects and refuses (``MissingTraceabilityError``) to
produce a section with no traced ids — the same hard invariant
``app.synthesis.tracking`` already enforces one layer down, applied here to
presentation.
"""

from __future__ import annotations

from app.deliverables.errors import MissingTraceabilityError
from app.deliverables.models import GeneratedSection
from app.deliverables.narrative_engine import build_narrative_structure
from app.synthesis.state import SynthesisState


def _require(content: tuple, traced_ids: tuple, section_id: str) -> None:
    if not content or not traced_ids:
        raise MissingTraceabilityError(
            f"section {section_id!r} would have no supported content — "
            "refusing to generate it"
        )


def _build_cover(state: SynthesisState, **_ctx) -> GeneratedSection:
    content = (f"Engagement category: {state.engagement_state.category.value}",)
    return GeneratedSection(
        section_id="cover",
        title="Cover",
        content=content,
        traced_ids=(state.engagement_state.engagement_id,),
    )


def _build_executive_summary(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = list(state.recommendations.values())
    content = tuple(r.statement for r in recs)
    traced = tuple(r.id for r in recs)
    _require(content, traced, "executive_summary")
    return GeneratedSection(
        section_id="executive_summary",
        title="Executive Summary",
        content=content,
        traced_ids=traced,
    )


def _build_scr(
    state: SynthesisState, *, narrative_id: str | None = None, **_ctx
) -> GeneratedSection:
    if narrative_id is None:
        raise MissingTraceabilityError(
            "situation_complication_resolution requires a narrative_id"
        )
    structure = build_narrative_structure(state, narrative_id)
    content = (structure.situation, structure.complication, structure.resolution)
    traced = (structure.source_narrative_id, *structure.source_recommendation_ids)
    return GeneratedSection(
        section_id="situation_complication_resolution",
        title="Situation, Complication, and Resolution",
        content=content,
        traced_ids=traced,
    )


def _build_key_findings(state: SynthesisState, **_ctx) -> GeneratedSection:
    findings = list(state.findings.values())
    content = tuple(f.statement for f in findings)
    traced = tuple(f.id for f in findings)
    _require(content, traced, "key_findings")
    return GeneratedSection(
        section_id="key_findings",
        title="Key Findings",
        content=content,
        traced_ids=traced,
    )


def _build_core_insights(state: SynthesisState, **_ctx) -> GeneratedSection:
    insights = list(state.insights.values())
    content = tuple(i.theme for i in insights)
    traced = tuple(i.id for i in insights)
    _require(content, traced, "core_insights")
    return GeneratedSection(
        section_id="core_insights",
        title="Core Insights",
        content=content,
        traced_ids=traced,
    )


def _build_recommendations(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = list(state.recommendations.values())
    content = tuple(r.statement for r in recs)
    traced = tuple(r.id for r in recs)
    _require(content, traced, "recommendations")
    return GeneratedSection(
        section_id="recommendations",
        title="Recommendations",
        content=content,
        traced_ids=traced,
    )


def _build_business_case(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = list(state.recommendations.values())
    content = tuple(
        f"{r.statement} — cost: {r.cost or 'n/a'}; benefits: "
        f"{', '.join(r.expected_benefits) or 'n/a'}"
        for r in recs
    )
    traced = tuple(r.id for r in recs)
    _require(content, traced, "business_case")
    return GeneratedSection(
        section_id="business_case",
        title="Business Case",
        content=content,
        traced_ids=traced,
    )


def _build_trade_off_analysis(
    state: SynthesisState, *, trade_off_result=None, **_ctx
) -> GeneratedSection:
    if trade_off_result is None:
        raise MissingTraceabilityError("trade_off_analysis requires a trade_off_result")
    content = trade_off_result.reasoning
    traced = tuple(o.id for o in trade_off_result.options)
    _require(content, traced, "trade_off_analysis")
    return GeneratedSection(
        section_id="trade_off_analysis",
        title="Trade-off Analysis",
        content=content,
        traced_ids=traced,
    )


def _build_risk_assessment(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = [r for r in state.recommendations.values() if r.risk]
    content = tuple(r.risk for r in recs)
    traced = tuple(r.id for r in recs)
    _require(content, traced, "risk_assessment")
    return GeneratedSection(
        section_id="risk_assessment",
        title="Risk Assessment",
        content=content,
        traced_ids=traced,
    )


def _build_implementation_roadmap(state: SynthesisState, **_ctx) -> GeneratedSection:
    themes = list(state.implementation_themes.values())
    content = tuple(t.description for t in themes)
    traced = tuple(t.id for t in themes)
    _require(content, traced, "implementation_roadmap")
    return GeneratedSection(
        section_id="implementation_roadmap",
        title="Implementation Roadmap",
        content=content,
        traced_ids=traced,
    )


def _build_kpis_and_outcomes(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = [r for r in state.recommendations.values() if r.kpis]
    content = tuple(kpi for r in recs for kpi in r.kpis)
    traced = tuple(r.id for r in recs)
    _require(content, traced, "kpis_and_outcomes")
    return GeneratedSection(
        section_id="kpis_and_outcomes",
        title="KPIs and Expected Outcomes",
        content=content,
        traced_ids=traced,
    )


def _build_governance_and_approvals(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = list(state.recommendations.values())
    content = tuple(f"{r.statement}: {r.approval_status.value}" for r in recs)
    traced = tuple(r.id for r in recs)
    _require(content, traced, "governance_and_approvals")
    return GeneratedSection(
        section_id="governance_and_approvals",
        title="Governance and Approvals",
        content=content,
        traced_ids=traced,
    )


def _build_appendix_evidence(state: SynthesisState, **_ctx) -> GeneratedSection:
    evidence = list(state.engagement_state.evidence.values())
    content = tuple(f"{e.source}: {e.content}" for e in evidence)
    traced = tuple(e.id for e in evidence)
    _require(content, traced, "appendix_evidence")
    return GeneratedSection(
        section_id="appendix_evidence",
        title="Appendix: Supporting Evidence",
        content=content,
        traced_ids=traced,
    )


def _build_lessons_learned(state: SynthesisState, **_ctx) -> GeneratedSection:
    recs = list(state.recommendations.values())
    content = tuple(r.business_rationale for r in recs)
    traced = tuple(r.id for r in recs)
    _require(content, traced, "lessons_learned")
    return GeneratedSection(
        section_id="lessons_learned",
        title="Lessons Learned",
        content=content,
        traced_ids=traced,
    )


_BUILDERS = {
    "cover": _build_cover,
    "executive_summary": _build_executive_summary,
    "situation_complication_resolution": _build_scr,
    "key_findings": _build_key_findings,
    "core_insights": _build_core_insights,
    "recommendations": _build_recommendations,
    "business_case": _build_business_case,
    "trade_off_analysis": _build_trade_off_analysis,
    "risk_assessment": _build_risk_assessment,
    "implementation_roadmap": _build_implementation_roadmap,
    "kpis_and_outcomes": _build_kpis_and_outcomes,
    "governance_and_approvals": _build_governance_and_approvals,
    "appendix_evidence": _build_appendix_evidence,
    "lessons_learned": _build_lessons_learned,
}


def build_section(
    section_id: str, state: SynthesisState, **context
) -> GeneratedSection:
    from app.deliverables.errors import UnknownSectionError

    if section_id not in _BUILDERS:
        raise UnknownSectionError(f"no section builder for {section_id!r}")
    return _BUILDERS[section_id](state, **context)
