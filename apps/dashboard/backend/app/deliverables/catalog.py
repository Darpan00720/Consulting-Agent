"""The deliverable catalog — all 20 named deliverable types the requester
listed, each composed from the shared 14-section library (``sections.py``)
rather than hand-written per type. All-keyword ``_Spec`` construction,
deliberately — the same lesson ``app.knowledge.catalog``'s positional-
argument bug taught this codebase, applied from the start here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.consulting.models import EngagementCategory as EC
from app.deliverables.models import Audience as AU
from app.deliverables.models import DeliverableDefinition
from app.deliverables.models import DeliverableType as DT
from app.organization.models import DecisionType as DEC

_ALL_ENGAGEMENTS = tuple(EC)


@dataclass(frozen=True)
class _Spec:
    key: DT
    name: str
    purpose: str
    audience: tuple[AU, ...]
    template: str
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = ("recommendation",)
    supported_engagement_types: tuple[EC, ...] = _ALL_ENGAGEMENTS
    supported_industries: tuple[str, ...] = ("all",)
    required_approvals: tuple[DEC, ...] = ()
    quality_checklist: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


def _build(spec: _Spec) -> DeliverableDefinition:
    return DeliverableDefinition(
        id=spec.key.value,
        name=spec.name,
        purpose=spec.purpose,
        audience=spec.audience,
        template=spec.template,
        required_sections=spec.required_sections,
        optional_sections=spec.optional_sections,
        required_artifacts=spec.required_artifacts,
        supported_engagement_types=spec.supported_engagement_types,
        supported_industries=spec.supported_industries,
        required_approvals=spec.required_approvals,
        quality_checklist=spec.quality_checklist,
        tags=spec.tags,
    )


_SPECS: tuple[_Spec, ...] = (
    _Spec(
        key=DT.EXECUTIVE_SUMMARY,
        name="Executive Summary",
        purpose="One-page statement of the recommendation and its business case.",
        audience=(AU.CEO, AU.BOARD),
        template="one_pager",
        required_sections=("executive_summary", "key_findings", "recommendations"),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "finding"),
        quality_checklist=("fits one page", "headline recommendation is unambiguous"),
        tags=("summary",),
    ),
    _Spec(
        key=DT.BOARD_PRESENTATION,
        name="Board Presentation",
        purpose="Full board-level deck presenting the recommendation for approval.",
        audience=(AU.BOARD, AU.CEO),
        template="slide_deck",
        required_sections=(
            "cover",
            "executive_summary",
            "situation_complication_resolution",
            "recommendations",
            "business_case",
            "risk_assessment",
        ),
        optional_sections=("implementation_roadmap",),
        required_artifacts=(
            "recommendation",
            "narrative",
            "business_impact_assessment",
        ),
        required_approvals=(DEC.APPROVE_RECOMMENDATIONS,),
        quality_checklist=("board-ready formatting", "risks explicitly addressed"),
        tags=("board", "governance"),
    ),
    _Spec(
        key=DT.STRATEGY_MEMORANDUM,
        name="Strategy Memorandum",
        purpose="Written memo framing the strategic situation and recommendation.",
        audience=(AU.CEO, AU.BUSINESS_UNIT_LEADER),
        template="memo",
        required_sections=(
            "executive_summary",
            "situation_complication_resolution",
            "key_findings",
            "core_insights",
            "recommendations",
        ),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "insight", "finding"),
        tags=("memo", "strategy"),
    ),
    _Spec(
        key=DT.BUSINESS_CASE,
        name="Business Case",
        purpose="Quantified cost/benefit case supporting the recommendation.",
        audience=(AU.CFO, AU.CEO),
        template="report",
        required_sections=(
            "executive_summary",
            "business_case",
            "trade_off_analysis",
            "risk_assessment",
            "kpis_and_outcomes",
        ),
        optional_sections=("implementation_roadmap",),
        required_artifacts=("recommendation", "business_impact_assessment"),
        supported_engagement_types=(EC.BUSINESS_CASE, EC.INVESTMENT_EVALUATION),
        required_approvals=(DEC.APPROVE_RECOMMENDATIONS,),
        quality_checklist=("every cost/benefit figure has a confidence value",),
        tags=("finance",),
    ),
    _Spec(
        key=DT.MARKET_ENTRY_REPORT,
        name="Market Entry Report",
        purpose="Full market entry assessment and recommendation.",
        audience=(AU.CEO, AU.BOARD),
        template="report",
        required_sections=(
            "executive_summary",
            "situation_complication_resolution",
            "key_findings",
            "business_case",
            "risk_assessment",
            "recommendations",
        ),
        optional_sections=("implementation_roadmap",),
        required_artifacts=("recommendation", "finding", "business_impact_assessment"),
        supported_engagement_types=(EC.MARKET_ENTRY,),
        tags=("market_entry",),
    ),
    _Spec(
        key=DT.TRANSFORMATION_ROADMAP,
        name="Transformation Roadmap",
        purpose="Phased plan for executing an approved transformation.",
        audience=(AU.COO, AU.PROGRAM_SPONSOR, AU.CHRO),
        template="roadmap",
        required_sections=(
            "executive_summary",
            "implementation_roadmap",
            "kpis_and_outcomes",
            "governance_and_approvals",
        ),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "implementation_theme"),
        supported_engagement_types=(
            EC.DIGITAL_TRANSFORMATION,
            EC.OPERATIONAL_EXCELLENCE,
            EC.CHANGE_MANAGEMENT,
        ),
        tags=("roadmap", "implementation"),
    ),
    _Spec(
        key=DT.DIGITAL_TRANSFORMATION_STRATEGY,
        name="Digital Transformation Strategy",
        purpose="Digital capability strategy and roadmap.",
        audience=(AU.CTO, AU.CEO),
        template="report",
        required_sections=(
            "executive_summary",
            "situation_complication_resolution",
            "recommendations",
            "implementation_roadmap",
        ),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "implementation_theme"),
        supported_engagement_types=(
            EC.DIGITAL_TRANSFORMATION,
            EC.TECHNOLOGY_MODERNIZATION,
        ),
        tags=("digital",),
    ),
    _Spec(
        key=DT.AI_STRATEGY_REPORT,
        name="AI Strategy Report",
        purpose="AI adoption strategy and prioritized use cases.",
        audience=(AU.CTO, AU.CEO),
        template="report",
        required_sections=(
            "executive_summary",
            "key_findings",
            "recommendations",
            "implementation_roadmap",
        ),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "finding"),
        supported_engagement_types=(EC.AI_TRANSFORMATION, EC.AUTOMATION_STRATEGY),
        tags=("ai",),
    ),
    _Spec(
        key=DT.OPERATIONAL_EXCELLENCE_REPORT,
        name="Operational Excellence Report",
        purpose="Operational diagnostic and improvement recommendations.",
        audience=(AU.COO,),
        template="report",
        required_sections=(
            "executive_summary",
            "key_findings",
            "business_case",
            "implementation_roadmap",
        ),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "finding", "business_impact_assessment"),
        supported_engagement_types=(
            EC.OPERATIONAL_EXCELLENCE,
            EC.COST_REDUCTION,
            EC.PROCESS_OPTIMIZATION,
        ),
        tags=("operations",),
    ),
    _Spec(
        key=DT.DUE_DILIGENCE_REPORT,
        name="Due Diligence Report",
        purpose="Commercial due diligence findings and risk assessment.",
        audience=(AU.CFO, AU.BOARD),
        template="report",
        required_sections=(
            "executive_summary",
            "key_findings",
            "risk_assessment",
            "business_case",
        ),
        optional_sections=("appendix_evidence",),
        required_artifacts=("finding", "evidence"),
        supported_engagement_types=(EC.DUE_DILIGENCE,),
        required_approvals=(DEC.APPROVE_FINDINGS,),
        tags=("due_diligence",),
    ),
    _Spec(
        key=DT.IMPLEMENTATION_ROADMAP,
        name="Implementation Roadmap",
        purpose="Standalone phased execution plan for approved recommendations.",
        audience=(AU.PROGRAM_SPONSOR, AU.COO),
        template="roadmap",
        required_sections=(
            "implementation_roadmap",
            "kpis_and_outcomes",
            "governance_and_approvals",
        ),
        optional_sections=("risk_assessment",),
        required_artifacts=("recommendation", "implementation_theme"),
        tags=("roadmap",),
    ),
    _Spec(
        key=DT.PMO_STATUS_REPORT,
        name="PMO Status Report",
        purpose="Periodic program execution status update.",
        audience=(AU.PROGRAM_SPONSOR,),
        template="status_report",
        required_sections=("implementation_roadmap", "kpis_and_outcomes"),
        optional_sections=("risk_assessment", "lessons_learned"),
        required_artifacts=("implementation_theme",),
        tags=("pmo", "status"),
    ),
    _Spec(
        key=DT.RISK_ASSESSMENT_REPORT,
        name="Risk Assessment Report",
        purpose="Structured risk register and mitigation plan.",
        audience=(AU.BOARD, AU.CFO, AU.COO),
        template="report",
        required_sections=("risk_assessment", "key_findings"),
        optional_sections=("recommendations",),
        required_artifacts=("recommendation", "finding"),
        supported_engagement_types=(EC.RISK_ASSESSMENT, EC.BUSINESS_CONTINUITY),
        tags=("risk",),
    ),
    _Spec(
        key=DT.EXECUTIVE_BRIEFING,
        name="Executive Briefing",
        purpose="Short-form briefing for a time-constrained executive audience.",
        audience=(AU.CEO, AU.BOARD),
        template="briefing",
        required_sections=("executive_summary", "key_findings", "recommendations"),
        required_artifacts=("recommendation", "finding"),
        quality_checklist=("readable in under 5 minutes",),
        tags=("briefing", "short_form"),
    ),
    _Spec(
        key=DT.STEERING_COMMITTEE_DECK,
        name="Steering Committee Deck",
        purpose="Recurring steering committee update deck.",
        audience=(AU.PROGRAM_SPONSOR, AU.BUSINESS_UNIT_LEADER),
        template="slide_deck",
        required_sections=(
            "cover",
            "executive_summary",
            "implementation_roadmap",
            "risk_assessment",
            "kpis_and_outcomes",
        ),
        required_artifacts=("recommendation", "implementation_theme"),
        tags=("steering_committee",),
    ),
    _Spec(
        key=DT.WORKSHOP_PACK,
        name="Workshop Pack",
        purpose="Working materials for a client workshop session.",
        audience=(AU.BUSINESS_UNIT_LEADER,),
        template="workshop",
        required_sections=(
            "situation_complication_resolution",
            "key_findings",
            "core_insights",
        ),
        optional_sections=("recommendations",),
        required_artifacts=("finding", "insight"),
        tags=("workshop", "interactive"),
    ),
    _Spec(
        key=DT.CLIENT_PROPOSAL,
        name="Client Proposal",
        purpose="Proposal framing the engagement's recommended approach.",
        audience=(AU.CEO, AU.BOARD),
        template="proposal",
        required_sections=(
            "cover",
            "executive_summary",
            "situation_complication_resolution",
            "recommendations",
            "business_case",
        ),
        optional_sections=("implementation_roadmap",),
        required_artifacts=("recommendation", "narrative"),
        tags=("proposal",),
    ),
    _Spec(
        key=DT.INVESTMENT_COMMITTEE_MEMO,
        name="Investment Committee Memo",
        purpose="Formal investment committee decision memo.",
        audience=(AU.CFO, AU.BOARD),
        template="memo",
        required_sections=(
            "executive_summary",
            "business_case",
            "trade_off_analysis",
            "risk_assessment",
        ),
        required_artifacts=(
            "recommendation",
            "business_impact_assessment",
            "trade_off_result",
        ),
        supported_engagement_types=(EC.INVESTMENT_EVALUATION, EC.BUSINESS_CASE),
        required_approvals=(
            DEC.APPROVE_RECOMMENDATIONS,
            DEC.APPROVE_IMPLEMENTATION_PLANS,
        ),
        tags=("investment", "governance"),
    ),
    _Spec(
        key=DT.POST_ENGAGEMENT_REPORT,
        name="Post-Engagement Report",
        purpose="Closing report summarizing the engagement's outcomes.",
        audience=(AU.CEO, AU.PROGRAM_SPONSOR),
        template="report",
        required_sections=(
            "executive_summary",
            "key_findings",
            "recommendations",
            "kpis_and_outcomes",
            "lessons_learned",
        ),
        required_artifacts=("recommendation", "finding"),
        tags=("closeout",),
    ),
    _Spec(
        key=DT.LESSONS_LEARNED,
        name="Lessons Learned",
        purpose="Standalone retrospective on what worked and what to change.",
        audience=(AU.PROGRAM_SPONSOR, AU.BUSINESS_UNIT_LEADER),
        template="retrospective",
        required_sections=("lessons_learned", "key_findings"),
        required_artifacts=("finding",),
        tags=("retrospective",),
    ),
)


def all_deliverable_definitions() -> tuple[DeliverableDefinition, ...]:
    return tuple(_build(spec) for spec in _SPECS)
