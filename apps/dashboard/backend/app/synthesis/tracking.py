"""Synthesis-chain mutators — the ONLY sanctioned way to add a Finding /
Insight / Opportunity / Recommendation / ImplementationTheme to a
``SynthesisState``. Every function enforces the mandatory downward
traceability the requester's "Design Principles" section states as an
absolute: "every recommendation must originate from findings; every finding
must originate from evidence... no recommendation may bypass this chain."

Deliberate exception to "never raise" (documented, not accidental) — the
same one ``app.consulting.tracking`` already carved out for evidence-linkage:
a synthesis node built without a real reference to the layer beneath it is a
domain-invariant violation, not an expected outcome, so construction refuses
rather than silently producing an untraceable node a caller could ignore.
"""

from __future__ import annotations

from app.consulting.models import ConsultingStage
from app.synthesis.errors import (
    MissingTraceabilityError,
    UnknownEvidenceError,
    UnknownFindingError,
    UnknownInsightError,
    UnknownOpportunityError,
    UnknownRecommendationError,
)
from app.synthesis.models import (
    ApprovalStatus,
    Finding,
    FindingStatus,
    ImplementationTheme,
    Insight,
    Opportunity,
    Recommendation,
    TimeHorizon,
    new_finding_id,
    new_implementation_theme_id,
    new_insight_id,
    new_opportunity_id,
    new_recommendation_id,
)
from app.synthesis.state import SynthesisState


def create_finding(
    state: SynthesisState,
    statement: str,
    supporting_evidence_ids: tuple[str, ...],
    confidence: float,
    business_impact: str,
    *,
    affected_stakeholders: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
    related_frameworks: tuple[str, ...] = (),
    related_workflow_stages: tuple[ConsultingStage, ...] = (),
    owner: str = "",
    status: FindingStatus = FindingStatus.DRAFT,
) -> Finding:
    if not supporting_evidence_ids:
        raise MissingTraceabilityError("a finding must cite at least one evidence id")
    missing = set(supporting_evidence_ids) - set(state.engagement_state.evidence.keys())
    if missing:
        raise UnknownEvidenceError(
            f"evidence ids not found in this engagement: {sorted(missing)}"
        )
    finding = Finding(
        id=new_finding_id(),
        statement=statement,
        supporting_evidence_ids=supporting_evidence_ids,
        confidence=confidence,
        business_impact=business_impact,
        affected_stakeholders=affected_stakeholders,
        assumptions=assumptions,
        limitations=limitations,
        related_frameworks=related_frameworks,
        related_workflow_stages=related_workflow_stages,
        owner=owner,
        status=status,
    )
    state.findings[finding.id] = finding
    return finding


def create_insight(
    state: SynthesisState,
    theme: str,
    supporting_finding_ids: tuple[str, ...],
    *,
    drivers: tuple[str, ...] = (),
    root_causes: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    strategic_implications: tuple[str, ...] = (),
    confidence: float = 0.5,
    alternative_interpretations: tuple[str, ...] = (),
    contradictory_evidence_ids: tuple[str, ...] = (),
) -> Insight:
    if not supporting_finding_ids:
        raise MissingTraceabilityError("an insight must cite at least one finding id")
    missing_findings = set(supporting_finding_ids) - set(state.findings.keys())
    if missing_findings:
        raise UnknownFindingError(f"finding ids not found: {sorted(missing_findings)}")
    missing_deps = set(dependencies) - set(state.insights.keys())
    if missing_deps:
        raise UnknownInsightError(
            f"dependency insight ids not found: {sorted(missing_deps)}"
        )
    missing_evidence = set(contradictory_evidence_ids) - set(
        state.engagement_state.evidence.keys()
    )
    if missing_evidence:
        raise UnknownEvidenceError(
            f"evidence ids not found: {sorted(missing_evidence)}"
        )
    insight = Insight(
        id=new_insight_id(),
        theme=theme,
        supporting_finding_ids=supporting_finding_ids,
        drivers=drivers,
        root_causes=root_causes,
        dependencies=dependencies,
        strategic_implications=strategic_implications,
        confidence=confidence,
        alternative_interpretations=alternative_interpretations,
        contradictory_evidence_ids=contradictory_evidence_ids,
    )
    state.insights[insight.id] = insight
    return insight


def create_opportunity(
    state: SynthesisState,
    description: str,
    supporting_insight_ids: tuple[str, ...],
    expected_value: str,
    strategic_importance: str,
    complexity: str,
    investment: str,
    risk: str,
    *,
    dependencies: tuple[str, ...] = (),
    priority: int = 0,
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM_TERM,
    confidence: float = 0.5,
    expected_value_score: float = 0.5,
    complexity_score: float = 0.5,
    investment_score: float = 0.5,
    risk_score: float = 0.5,
) -> Opportunity:
    if not supporting_insight_ids:
        raise MissingTraceabilityError(
            "an opportunity must cite at least one insight id"
        )
    missing_insights = set(supporting_insight_ids) - set(state.insights.keys())
    if missing_insights:
        raise UnknownInsightError(f"insight ids not found: {sorted(missing_insights)}")
    missing_deps = set(dependencies) - set(state.opportunities.keys())
    if missing_deps:
        raise UnknownOpportunityError(
            f"dependency opportunity ids not found: {sorted(missing_deps)}"
        )
    opportunity = Opportunity(
        id=new_opportunity_id(),
        description=description,
        supporting_insight_ids=supporting_insight_ids,
        expected_value=expected_value,
        strategic_importance=strategic_importance,
        complexity=complexity,
        investment=investment,
        risk=risk,
        dependencies=dependencies,
        priority=priority,
        time_horizon=time_horizon,
        confidence=confidence,
        expected_value_score=expected_value_score,
        complexity_score=complexity_score,
        investment_score=investment_score,
        risk_score=risk_score,
    )
    state.opportunities[opportunity.id] = opportunity
    return opportunity


def create_recommendation(
    state: SynthesisState,
    statement: str,
    business_rationale: str,
    supporting_finding_ids: tuple[str, ...],
    supporting_evidence_ids: tuple[str, ...],
    *,
    supporting_opportunity_ids: tuple[str, ...] = (),
    supporting_insight_ids: tuple[str, ...] = (),
    expected_benefits: tuple[str, ...] = (),
    cost: str = "",
    risk: str = "",
    trade_offs: tuple[str, ...] = (),
    implementation_complexity: str = "",
    kpis: tuple[str, ...] = (),
    confidence: float = 0.5,
    owner: str = "",
    approval_status: ApprovalStatus = ApprovalStatus.PENDING,
    contradicts: tuple[str, ...] = (),
) -> Recommendation:
    """ "Every recommendation must originate from findings" +
    "every finding must originate from evidence" — both halves of the chain
    are checked here directly (not just transitively via the findings
    already being evidence-linked), so a recommendation can never cite a
    finding without ALSO citing at least one evidence id of its own."""
    if not supporting_finding_ids:
        raise MissingTraceabilityError(
            "a recommendation must cite at least one finding id"
        )
    if not supporting_evidence_ids:
        raise MissingTraceabilityError(
            "a recommendation must cite at least one evidence id"
        )
    missing_findings = set(supporting_finding_ids) - set(state.findings.keys())
    if missing_findings:
        raise UnknownFindingError(f"finding ids not found: {sorted(missing_findings)}")
    missing_evidence = set(supporting_evidence_ids) - set(
        state.engagement_state.evidence.keys()
    )
    if missing_evidence:
        raise UnknownEvidenceError(
            f"evidence ids not found: {sorted(missing_evidence)}"
        )
    missing_opportunities = set(supporting_opportunity_ids) - set(
        state.opportunities.keys()
    )
    if missing_opportunities:
        raise UnknownOpportunityError(
            f"opportunity ids not found: {sorted(missing_opportunities)}"
        )
    missing_insights = set(supporting_insight_ids) - set(state.insights.keys())
    if missing_insights:
        raise UnknownInsightError(f"insight ids not found: {sorted(missing_insights)}")

    recommendation = Recommendation(
        id=new_recommendation_id(),
        statement=statement,
        business_rationale=business_rationale,
        supporting_opportunity_ids=supporting_opportunity_ids,
        supporting_insight_ids=supporting_insight_ids,
        supporting_finding_ids=supporting_finding_ids,
        supporting_evidence_ids=supporting_evidence_ids,
        expected_benefits=expected_benefits,
        cost=cost,
        risk=risk,
        trade_offs=trade_offs,
        implementation_complexity=implementation_complexity,
        kpis=kpis,
        confidence=confidence,
        owner=owner,
        approval_status=approval_status,
        contradicts=contradicts,
    )
    state.recommendations[recommendation.id] = recommendation
    return recommendation


def create_implementation_theme(
    state: SynthesisState,
    name: str,
    description: str,
    supporting_recommendation_ids: tuple[str, ...],
    *,
    workstreams: tuple[str, ...] = (),
    timeline: str = "",
    owner: str = "",
) -> ImplementationTheme:
    if not supporting_recommendation_ids:
        raise MissingTraceabilityError(
            "an implementation theme must cite at least one recommendation id"
        )
    missing = set(supporting_recommendation_ids) - set(state.recommendations.keys())
    if missing:
        raise UnknownRecommendationError(
            f"recommendation ids not found: {sorted(missing)}"
        )
    theme = ImplementationTheme(
        id=new_implementation_theme_id(),
        name=name,
        description=description,
        supporting_recommendation_ids=supporting_recommendation_ids,
        workstreams=workstreams,
        timeline=timeline,
        owner=owner,
    )
    state.implementation_themes[theme.id] = theme
    return theme
