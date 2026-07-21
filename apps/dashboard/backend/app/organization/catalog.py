"""The role catalog — all 25 named roles the requester listed.

**All-keyword construction, deliberately** — ``app.knowledge.catalog``'s
positional ``_Spec`` calls hid a field-order bug across dozens of entries
until an explicit type audit caught it (see that module's history). With
only 25 roles and 20 fields each, every ``_Spec(...)`` call below uses
keyword arguments exclusively, so a field can never silently land in the
wrong slot — the lesson applied, not just noted.

**Data-driven, not hand-written classes** — the same mechanism
``app.consulting.workflow.standard_workflow`` and ``app.knowledge.catalog``
established: a role is a ``_Spec`` fed through ``_build()``; role #26 is one
more entry, never a new class.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.consulting.models import ArtifactType as AT
from app.consulting.models import EngagementCategory as EC
from app.organization.models import (
    DecisionType as DT,
)
from app.organization.models import (
    ExperienceLevel as EL,
)
from app.organization.models import (
    Practice as PR,
)
from app.organization.models import (
    ReviewStage as RS,
)
from app.organization.models import (
    RoleDefinition,
)

# Decision authority escalates by seniority — junior roles own low-stakes,
# reversible decisions (hypotheses/assumptions); findings need manager
# sign-off; recommendations/implementation plans need partner sign-off;
# executive summaries are the Managing Partner's call. Mechanically derived
# from experience level so the escalation CHAIN (governance.py) is coherent
# by construction, not by 25 independently-guessed lists.
_DECISION_AUTHORITY_BY_LEVEL: dict[EL, tuple[DT, ...]] = {
    EL.ANALYST: (DT.APPROVE_HYPOTHESES, DT.APPROVE_ASSUMPTIONS),
    EL.SPECIALIST: (DT.APPROVE_HYPOTHESES, DT.APPROVE_ASSUMPTIONS),
    EL.CONSULTANT: (DT.APPROVE_HYPOTHESES, DT.APPROVE_ASSUMPTIONS),
    EL.SENIOR_CONSULTANT: (
        DT.APPROVE_HYPOTHESES,
        DT.APPROVE_ASSUMPTIONS,
        DT.APPROVE_FINDINGS,
    ),
    EL.MANAGER: (DT.APPROVE_FINDINGS,),
    EL.PRINCIPAL: (DT.APPROVE_FINDINGS, DT.APPROVE_RECOMMENDATIONS),
    EL.PARTNER: (DT.APPROVE_RECOMMENDATIONS, DT.APPROVE_IMPLEMENTATION_PLANS),
    EL.MANAGING_PARTNER: (
        DT.APPROVE_EXECUTIVE_SUMMARIES,
        DT.APPROVE_RECOMMENDATIONS,
        DT.APPROVE_IMPLEMENTATION_PLANS,
    ),
}

_REVIEW_AUTHORITY_BY_LEVEL: dict[EL, tuple[RS, ...]] = {
    EL.ANALYST: (RS.PEER,),
    EL.SPECIALIST: (RS.PEER,),
    EL.CONSULTANT: (RS.PEER,),
    EL.SENIOR_CONSULTANT: (RS.PEER, RS.MANAGER),
    EL.MANAGER: (RS.PEER, RS.MANAGER),
    EL.PRINCIPAL: (RS.MANAGER, RS.PARTNER),
    EL.PARTNER: (RS.PARTNER,),
    EL.MANAGING_PARTNER: (RS.PARTNER, RS.EXECUTIVE),
}


@dataclass(frozen=True)
class _Spec:
    key: str
    name: str
    description: str
    practice: PR
    experience_level: EL
    primary_responsibilities: tuple[str, ...]
    secondary_responsibilities: tuple[str, ...] = ()
    approval_authority: tuple[AT, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    supported_engagement_types: tuple[EC, ...] = ()
    supported_frameworks: tuple[str, ...] = ()
    quality_checklist: tuple[str, ...] = ()
    handoff_criteria: tuple[str, ...] = ()
    escalation_rules: tuple[str, ...] = ()
    deliverables_owned: tuple[AT, ...] = ()
    inputs_required: tuple[str, ...] = ()
    outputs_produced: tuple[str, ...] = ()
    kpis: tuple[str, ...] = ()
    reporting_line: str | None = None
    decision_authority_override: tuple[DT, ...] | None = None
    review_authority_override: tuple[RS, ...] | None = None


def _build(spec: _Spec) -> RoleDefinition:
    decision_authority = (
        spec.decision_authority_override
        if spec.decision_authority_override is not None
        else _DECISION_AUTHORITY_BY_LEVEL[spec.experience_level]
    )
    review_authority = (
        spec.review_authority_override
        if spec.review_authority_override is not None
        else _REVIEW_AUTHORITY_BY_LEVEL[spec.experience_level]
    )
    return RoleDefinition(
        id=spec.key,
        name=spec.name,
        description=spec.description,
        practice=spec.practice,
        experience_level=spec.experience_level,
        primary_responsibilities=spec.primary_responsibilities,
        secondary_responsibilities=spec.secondary_responsibilities,
        decision_authority=decision_authority,
        approval_authority=spec.approval_authority,
        required_capabilities=spec.required_capabilities,
        supported_engagement_types=spec.supported_engagement_types,
        supported_frameworks=spec.supported_frameworks,
        quality_checklist=spec.quality_checklist,
        handoff_criteria=spec.handoff_criteria,
        escalation_rules=spec.escalation_rules,
        deliverables_owned=spec.deliverables_owned,
        inputs_required=spec.inputs_required,
        outputs_produced=spec.outputs_produced,
        kpis=spec.kpis,
        review_authority=review_authority,
        reporting_line=spec.reporting_line,
    )


_SPECS: tuple[_Spec, ...] = (
    _Spec(
        key="managing_partner",
        name="Managing Partner",
        description="Ultimate firm leadership; final accountability "
        "for engagement quality and client relationship.",
        practice=PR.STRATEGY,
        experience_level=EL.MANAGING_PARTNER,
        primary_responsibilities=(
            "Own the client relationship at the executive level",
            "Approve executive summaries before client delivery",
        ),
        secondary_responsibilities=("Firm-wide quality standards",),
        approval_authority=(AT.EXECUTIVE_SUMMARY,),
        required_capabilities=("executive communication", "client management"),
        supported_engagement_types=tuple(EC),
        quality_checklist=(
            "strategic coherence with firm standards",
            "client relationship risk assessed",
        ),
        handoff_criteria=("Partner has signed off on recommendations",),
        escalation_rules=("Terminal escalation point — no further escalation exists",),
        deliverables_owned=(AT.EXECUTIVE_SUMMARY,),
        inputs_required=("partner-approved recommendation matrix",),
        outputs_produced=("client-ready executive summary",),
        kpis=("client satisfaction", "engagement profitability", "firm reputation"),
        reporting_line=None,
    ),
    _Spec(
        key="partner",
        name="Partner",
        description="Owns engagement economics and the final recommendation; "
        "the primary client-facing decision-maker.",
        practice=PR.STRATEGY,
        experience_level=EL.PARTNER,
        primary_responsibilities=(
            "Approve the recommendation matrix and implementation roadmap",
            "Own overall engagement quality",
        ),
        secondary_responsibilities=("Business development for the account",),
        approval_authority=(AT.RECOMMENDATION_MATRIX, AT.IMPLEMENTATION_ROADMAP),
        required_capabilities=("strategic judgment", "client relationship management"),
        supported_engagement_types=tuple(EC),
        quality_checklist=(
            "strategic coherence",
            "business impact quantified",
            "client value clear",
        ),
        handoff_criteria=("Principal has validated findings",),
        escalation_rules=(
            "Escalate to Managing Partner for executive summary sign-off",
        ),
        deliverables_owned=(AT.RECOMMENDATION_MATRIX,),
        inputs_required=("validated findings report",),
        outputs_produced=("recommendation matrix", "implementation roadmap"),
        kpis=("engagement margin", "recommendation adoption rate"),
        reporting_line="managing_partner",
    ),
    _Spec(
        key="principal",
        name="Principal",
        description="Owns analytical rigor across the engagement; "
        "validates findings before they reach the Partner.",
        practice=PR.STRATEGY,
        experience_level=EL.PRINCIPAL,
        primary_responsibilities=(
            "Validate the findings report for evidentiary rigor",
            "Own the assumption register",
        ),
        secondary_responsibilities=("Mentor Engagement Managers and Project Leaders",),
        approval_authority=(AT.FINDINGS_REPORT, AT.ASSUMPTION_REGISTER),
        required_capabilities=("analytical rigor", "cross-workstream synthesis"),
        supported_engagement_types=tuple(EC),
        quality_checklist=(
            "evidence traceable",
            "assumptions documented and reasonable",
        ),
        handoff_criteria=("Engagement Manager has consolidated workstream findings",),
        escalation_rules=("Escalate to Partner when findings imply a strategy pivot",),
        deliverables_owned=(AT.ASSUMPTION_REGISTER, AT.FINDINGS_REPORT),
        inputs_required=("workstream findings from all analysts",),
        outputs_produced=("validated findings report",),
        kpis=("finding accuracy", "rework rate"),
        reporting_line="partner",
    ),
    _Spec(
        key="engagement_manager",
        name="Engagement Manager",
        description="Owns day-to-day engagement delivery, "
        "scope, and stakeholder coordination.",
        practice=PR.STRATEGY,
        experience_level=EL.MANAGER,
        primary_responsibilities=(
            "Define the problem statement and project charter",
            "Coordinate workstreams and manage scope",
        ),
        secondary_responsibilities=("Client-facing status reporting",),
        approval_authority=(AT.PROBLEM_STATEMENT,),
        required_capabilities=("project management", "stakeholder management"),
        supported_engagement_types=tuple(EC),
        quality_checklist=("scope clearly defined", "stakeholders identified"),
        handoff_criteria=("Client has confirmed engagement scope",),
        escalation_rules=("Escalate scope changes exceeding budget to Principal",),
        deliverables_owned=(AT.PROBLEM_STATEMENT, AT.PROJECT_CHARTER),
        inputs_required=("client brief",),
        outputs_produced=("problem statement", "project charter"),
        kpis=("on-time delivery", "scope stability"),
        reporting_line="principal",
    ),
    _Spec(
        key="project_leader",
        name="Project Leader",
        description="Owns the issue tree, analysis plan, "
        "and daily workstream execution.",
        practice=PR.STRATEGY,
        experience_level=EL.MANAGER,
        primary_responsibilities=(
            "Build the issue tree and analysis plan",
            "Direct day-to-day consultant/analyst work",
        ),
        secondary_responsibilities=(
            "Quality-check workstream outputs before Principal review",
        ),
        approval_authority=(AT.ISSUE_TREE, AT.ANALYSIS_PLAN),
        required_capabilities=("issue structuring", "team leadership"),
        supported_engagement_types=tuple(EC),
        quality_checklist=(
            "issue tree is MECE",
            "analysis plan covers all required evidence",
        ),
        handoff_criteria=("Engagement Manager has confirmed scope",),
        escalation_rules=("Escalate resourcing conflicts to Engagement Manager",),
        deliverables_owned=(AT.ISSUE_TREE, AT.ANALYSIS_PLAN),
        inputs_required=("problem statement",),
        outputs_produced=("issue tree", "analysis plan"),
        kpis=("issue tree MECE compliance", "workstream velocity"),
        reporting_line="engagement_manager",
    ),
    _Spec(
        key="strategy_consultant",
        name="Strategy Consultant",
        description="Develops and tests strategic hypotheses "
        "using core strategy frameworks.",
        practice=PR.STRATEGY,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=(
            "Develop and document hypotheses",
            "Apply strategy frameworks to test them",
        ),
        secondary_responsibilities=("Support Project Leader in issue-tree refinement",),
        required_capabilities=("hypothesis-driven analysis", "framework application"),
        supported_engagement_types=(
            EC.CORPORATE_STRATEGY,
            EC.BUSINESS_STRATEGY,
            EC.GROWTH_STRATEGY,
            EC.MARKET_ENTRY,
            EC.PORTFOLIO_STRATEGY,
        ),
        supported_frameworks=("five_forces", "swot", "pestle", "ansoff_matrix", "vrio"),
        quality_checklist=("hypotheses falsifiable", "rationale documented"),
        handoff_criteria=("Hypothesis has at least one linked piece of evidence",),
        escalation_rules=("Escalate framework disagreements to Project Leader",),
        deliverables_owned=(AT.HYPOTHESIS_LOG,),
        inputs_required=("issue tree",),
        outputs_produced=("hypothesis log", "framework analyses"),
        kpis=("hypothesis confirmation rate",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="industry_specialist",
        name="Industry Specialist",
        description="Provides deep sector expertise and "
        "context for industry-specific engagements.",
        practice=PR.MARKET_RESEARCH,
        experience_level=EL.SPECIALIST,
        primary_responsibilities=(
            "Provide industry context and benchmarks",
            "Own the interview guide for expert/customer interviews",
        ),
        secondary_responsibilities=(
            "Validate market analyst findings against sector norms",
        ),
        approval_authority=(AT.INTERVIEW_GUIDE,),
        required_capabilities=("sector expertise", "expert network"),
        supported_engagement_types=(
            EC.MARKET_ENTRY,
            EC.DUE_DILIGENCE,
            EC.GROWTH_STRATEGY,
        ),
        supported_frameworks=("pestle", "market_attractiveness"),
        quality_checklist=("industry context accurate and current",),
        handoff_criteria=("Interview guide reviewed by Project Leader",),
        escalation_rules=("Escalate conflicting sector data to Principal",),
        deliverables_owned=(AT.INTERVIEW_GUIDE,),
        inputs_required=("analysis plan",),
        outputs_produced=("industry context brief", "interview guide"),
        kpis=("interview completion rate",),
        reporting_line="engagement_manager",
    ),
    _Spec(
        key="financial_analyst",
        name="Financial Analyst",
        description="Builds and verifies quantitative financial "
        "analyses supporting the business case.",
        practice=PR.FINANCE,
        experience_level=EL.ANALYST,
        primary_responsibilities=(
            "Build financial models (DCF, NPV, unit economics)",
            "Verify calculations and run sensitivity analysis",
        ),
        secondary_responsibilities=(
            "Support Business Analyst with data reconciliation",
        ),
        required_capabilities=("financial modeling", "quantitative analysis"),
        supported_engagement_types=(
            EC.INVESTMENT_EVALUATION,
            EC.BUSINESS_CASE,
            EC.DUE_DILIGENCE,
            EC.FINANCIAL_PERFORMANCE,
            EC.MARKET_ENTRY,
        ),
        supported_frameworks=(
            "dcf",
            "npv",
            "irr",
            "payback_period",
            "sensitivity_analysis",
            "unit_economics",
            "breakeven_analysis",
        ),
        quality_checklist=(
            "calculations verified",
            "assumptions documented",
            "sensitivity completed",
        ),
        handoff_criteria=("Model has been independently recalculated once",),
        escalation_rules=("Escalate assumption disputes to Principal",),
        outputs_produced=("financial model", "sensitivity analysis"),
        kpis=("calculation error rate",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="operations_consultant",
        name="Operations Consultant",
        description="Diagnoses and redesigns operational "
        "processes for efficiency and cost.",
        practice=PR.OPERATIONS,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=(
            "Map and diagnose operational processes",
            "Apply lean/six-sigma frameworks to identify waste",
        ),
        required_capabilities=("process analysis", "operational benchmarking"),
        supported_engagement_types=(
            EC.COST_REDUCTION,
            EC.OPERATIONAL_EXCELLENCE,
            EC.PROCESS_OPTIMIZATION,
            EC.SUPPLY_CHAIN,
        ),
        supported_frameworks=(
            "lean",
            "six_sigma",
            "value_stream_mapping",
            "process_mapping",
            "bottleneck_analysis",
        ),
        quality_checklist=("process map validated with process owners",),
        handoff_criteria=("Process map reviewed by a peer",),
        escalation_rules=(
            "Escalate cross-functional process conflicts to Project Leader",
        ),
        outputs_produced=("process maps", "waste/bottleneck analysis"),
        kpis=("cost savings identified",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="digital_transformation_consultant",
        name="Digital Transformation Consultant",
        description="Assesses and designs digital capability "
        "and transformation roadmaps.",
        practice=PR.DIGITAL_AI,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=(
            "Assess digital maturity",
            "Design digital transformation roadmap options",
        ),
        required_capabilities=("digital strategy", "change management"),
        supported_engagement_types=(
            EC.DIGITAL_TRANSFORMATION,
            EC.TECHNOLOGY_MODERNIZATION,
        ),
        supported_frameworks=(
            "digital_maturity",
            "platform_strategy",
            "technology_landscape",
        ),
        quality_checklist=("maturity assessment evidence-backed",),
        handoff_criteria=("Maturity assessment reviewed by Technology Architect",),
        escalation_rules=(
            "Escalate architecture feasibility questions to Technology Architect",
        ),
        outputs_produced=("digital maturity assessment",),
        kpis=("roadmap adoption",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="ai_strategy_consultant",
        name="AI Strategy Consultant",
        description="Assesses AI readiness and designs AI adoption strategy.",
        practice=PR.DIGITAL_AI,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=(
            "Assess AI/data readiness",
            "Prioritize AI use cases by feasibility and impact",
        ),
        required_capabilities=("AI strategy", "use-case prioritization"),
        supported_engagement_types=(EC.AI_TRANSFORMATION, EC.AUTOMATION_STRATEGY),
        supported_frameworks=("ai_readiness", "automation_assessment", "data_strategy"),
        quality_checklist=("use cases ranked with explicit criteria",),
        handoff_criteria=("Readiness assessment reviewed by Technology Architect",),
        escalation_rules=("Escalate data governance gaps to Principal",),
        outputs_produced=("AI readiness assessment", "use-case priority list"),
        kpis=("use-case pipeline value",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="technology_architect",
        name="Technology Architect",
        description="Evaluates technical architecture "
        "feasibility for digital/AI recommendations.",
        practice=PR.DIGITAL_AI,
        experience_level=EL.SPECIALIST,
        primary_responsibilities=(
            "Assess architecture and technology capability",
            "Validate technical feasibility of proposed roadmaps",
        ),
        required_capabilities=("enterprise architecture", "technology evaluation"),
        supported_engagement_types=(
            EC.TECHNOLOGY_MODERNIZATION,
            EC.DIGITAL_TRANSFORMATION,
        ),
        supported_frameworks=(
            "architecture_assessment",
            "cloud_readiness",
            "technology_capability_assessment",
        ),
        quality_checklist=("feasibility assessment covers integration risk",),
        handoff_criteria=(
            "Architecture assessment reviewed by Digital Transformation Consultant",
        ),
        escalation_rules=("Escalate unresolvable feasibility risk to Principal",),
        outputs_produced=("architecture feasibility assessment",),
        kpis=("feasibility assessment accuracy",),
        reporting_line="digital_transformation_consultant",
    ),
    _Spec(
        key="market_research_analyst",
        name="Market Research Analyst",
        description="Executes market sizing and demand research.",
        practice=PR.MARKET_RESEARCH,
        experience_level=EL.ANALYST,
        primary_responsibilities=(
            "Size markets (TAM/SAM/SOM)",
            "Conduct demand research",
        ),
        required_capabilities=("market sizing", "secondary research"),
        supported_engagement_types=(
            EC.MARKET_ENTRY,
            EC.GROWTH_STRATEGY,
            EC.BUSINESS_CASE,
        ),
        supported_frameworks=(
            "tam_sam_som",
            "demand_forecasting",
            "customer_segmentation",
        ),
        quality_checklist=("sizing methodology documented", "sources cited"),
        handoff_criteria=("Sizing reviewed by Industry Specialist",),
        escalation_rules=("Escalate data quality concerns to Industry Specialist",),
        outputs_produced=("market sizing analysis",),
        kpis=("research turnaround time",),
        reporting_line="industry_specialist",
    ),
    _Spec(
        key="competitive_intelligence_analyst",
        name="Competitive Intelligence Analyst",
        description="Tracks and analyzes competitor positioning and strategy.",
        practice=PR.MARKET_RESEARCH,
        experience_level=EL.ANALYST,
        primary_responsibilities=("Profile competitors", "Track competitive moves"),
        required_capabilities=("competitive analysis", "secondary research"),
        supported_engagement_types=(
            EC.BUSINESS_STRATEGY,
            EC.MARKET_ENTRY,
            EC.PRICING_STRATEGY,
        ),
        supported_frameworks=("competitive_positioning", "five_forces"),
        quality_checklist=("competitor data current within 6 months",),
        handoff_criteria=("Competitor profile reviewed by Industry Specialist",),
        escalation_rules=(
            "Escalate ambiguous competitive signals to Industry Specialist",
        ),
        outputs_produced=("competitor profiles", "positioning map"),
        kpis=("profile freshness",),
        reporting_line="industry_specialist",
    ),
    _Spec(
        key="customer_insights_analyst",
        name="Customer Insights Analyst",
        description="Runs customer research to surface needs, "
        "pain points, and journey friction.",
        practice=PR.MARKET_RESEARCH,
        experience_level=EL.ANALYST,
        primary_responsibilities=(
            "Conduct customer research",
            "Map the customer journey",
        ),
        required_capabilities=("qualitative research", "journey mapping"),
        supported_engagement_types=(
            EC.GO_TO_MARKET,
            EC.PRODUCT_STRATEGY,
            EC.GROWTH_STRATEGY,
        ),
        supported_frameworks=(
            "customer_journey",
            "jobs_to_be_done",
            "customer_segmentation",
        ),
        quality_checklist=("findings triangulated across multiple customers",),
        handoff_criteria=("Journey map reviewed by Industry Specialist",),
        escalation_rules=(
            "Escalate conflicting customer signals to Industry Specialist",
        ),
        outputs_produced=("customer journey map", "needs analysis"),
        kpis=("interview sample size",),
        reporting_line="industry_specialist",
    ),
    _Spec(
        key="risk_consultant",
        name="Risk Consultant",
        description="Owns the risk register and mitigation "
        "planning across the engagement.",
        practice=PR.RISK,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=(
            "Build and maintain the risk register",
            "Plan mitigations",
        ),
        approval_authority=(AT.RISK_REGISTER,),
        required_capabilities=("risk assessment", "scenario planning"),
        supported_engagement_types=(
            EC.RISK_ASSESSMENT,
            EC.BUSINESS_CONTINUITY,
            EC.DUE_DILIGENCE,
        ),
        supported_frameworks=(
            "risk_matrix",
            "failure_mode_analysis",
            "scenario_planning",
            "mitigation_planning",
        ),
        quality_checklist=("every high-severity risk has a named mitigation owner",),
        handoff_criteria=("Risk register reviewed by Project Leader",),
        escalation_rules=("Escalate unmitigated critical risks to Partner",),
        deliverables_owned=(AT.RISK_REGISTER,),
        inputs_required=("findings report",),
        outputs_produced=("risk register", "mitigation plan"),
        kpis=("critical risks with mitigation coverage",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="implementation_consultant",
        name="Implementation Consultant",
        description="Owns the implementation roadmap and "
        "feasibility of proposed initiatives.",
        practice=PR.IMPLEMENTATION,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=(
            "Build the implementation roadmap",
            "Assess execution feasibility of recommendations",
        ),
        approval_authority=(AT.IMPLEMENTATION_ROADMAP,),
        required_capabilities=("program planning", "change readiness assessment"),
        supported_engagement_types=(EC.CHANGE_MANAGEMENT, EC.OPERATIONAL_EXCELLENCE),
        supported_frameworks=("value_stream_mapping",),
        quality_checklist=("every phase has an owner and a KPI",),
        handoff_criteria=("Roadmap reviewed by PMO Consultant",),
        escalation_rules=("Escalate resourcing gaps to Partner",),
        deliverables_owned=(AT.IMPLEMENTATION_ROADMAP,),
        inputs_required=("recommendation matrix",),
        outputs_produced=("implementation roadmap",),
        kpis=("roadmap milestone hit rate",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="pmo_consultant",
        name="PMO Consultant",
        description="Tracks program execution health and "
        "governance cadence post-recommendation.",
        practice=PR.IMPLEMENTATION,
        experience_level=EL.CONSULTANT,
        primary_responsibilities=("Track milestone status", "Run governance cadence"),
        required_capabilities=("program governance", "status tracking"),
        supported_engagement_types=(EC.CHANGE_MANAGEMENT,),
        quality_checklist=("status reporting is current within the reporting cycle",),
        handoff_criteria=("Status report reviewed by Engagement Manager",),
        escalation_rules=("Escalate missed milestones to Engagement Manager",),
        outputs_produced=("status reports", "governance cadence"),
        kpis=("on-time milestone rate",),
        reporting_line="engagement_manager",
    ),
    _Spec(
        key="knowledge_manager",
        name="Knowledge Manager",
        description="Owns knowledge-vault curation and "
        "cross-engagement institutional memory.",
        practice=PR.KNOWLEDGE_MANAGEMENT,
        experience_level=EL.MANAGER,
        primary_responsibilities=(
            "Curate durable insights back into the knowledge vault",
            "Ensure frameworks stay current and well-documented",
        ),
        required_capabilities=("knowledge curation", "framework governance"),
        supported_engagement_types=tuple(EC),
        quality_checklist=("curated notes are evidence-pinned",),
        handoff_criteria=("Engagement closed out with a knowledge write-back",),
        escalation_rules=("Escalate framework quality disputes to Partner",),
        outputs_produced=("curated knowledge notes",),
        kpis=("knowledge reuse rate",),
        reporting_line="partner",
    ),
    _Spec(
        key="research_librarian",
        name="Research Librarian",
        description="Owns the research summary and source curation for the engagement.",
        practice=PR.KNOWLEDGE_MANAGEMENT,
        experience_level=EL.SPECIALIST,
        primary_responsibilities=("Curate and validate external research sources",),
        approval_authority=(AT.RESEARCH_SUMMARY,),
        required_capabilities=("research curation", "source validation"),
        supported_engagement_types=tuple(EC),
        quality_checklist=("every source has a traceable citation",),
        handoff_criteria=("Research summary reviewed by Knowledge Manager",),
        escalation_rules=("Escalate source-credibility concerns to Knowledge Manager",),
        deliverables_owned=(AT.RESEARCH_SUMMARY,),
        outputs_produced=("research summary",),
        kpis=("source citation completeness",),
        reporting_line="knowledge_manager",
    ),
    _Spec(
        key="qa_reviewer",
        name="QA Reviewer",
        description="Runs structured quality review across logic, "
        "evidence, and calculations before partner review.",
        practice=PR.QUALITY_EDITORIAL,
        experience_level=EL.MANAGER,
        primary_responsibilities=(
            "Review findings and recommendations for logic and evidence quality",
            "Verify calculations independently",
        ),
        approval_authority=(AT.FINDINGS_REPORT,),
        required_capabilities=("quality assurance", "attention to detail"),
        supported_engagement_types=tuple(EC),
        quality_checklist=(
            "logic internally consistent",
            "evidence traceable",
            "calculations re-verified",
        ),
        handoff_criteria=("Artifact submitted with all supporting evidence attached",),
        escalation_rules=("Escalate unresolved quality gaps to Partner",),
        outputs_produced=("QA review findings",),
        kpis=("defect escape rate",),
        reporting_line="partner",
    ),
    _Spec(
        key="executive_editor",
        name="Executive Editor",
        description="Owns narrative clarity and executive-readiness "
        "of client-facing deliverables.",
        practice=PR.QUALITY_EDITORIAL,
        experience_level=EL.SENIOR_CONSULTANT,
        primary_responsibilities=(
            "Edit deliverables for executive clarity",
            "Ensure narrative consistency across sections",
        ),
        required_capabilities=("executive writing", "narrative structuring"),
        supported_engagement_types=tuple(EC),
        quality_checklist=(
            "executive clarity",
            "concise messaging",
            "narrative consistency",
        ),
        handoff_criteria=("Draft reviewed by QA Reviewer for content accuracy first",),
        escalation_rules=(
            "Escalate unresolved narrative/content conflicts to Partner",
        ),
        inputs_required=("QA-reviewed recommendation matrix",),
        outputs_produced=("client-ready narrative draft",),
        kpis=("client readability feedback",),
        reporting_line="qa_reviewer",
    ),
    _Spec(
        key="presentation_specialist",
        name="Presentation Specialist",
        description="Owns visual design and slide "
        "craftsmanship of client deliverables.",
        practice=PR.QUALITY_EDITORIAL,
        experience_level=EL.SPECIALIST,
        primary_responsibilities=(
            "Design and format client-facing presentation materials",
        ),
        required_capabilities=("visual design", "data visualization"),
        supported_engagement_types=tuple(EC),
        quality_checklist=("visual consistency with firm brand standards",),
        handoff_criteria=("Content finalized by Executive Editor before formatting",),
        escalation_rules=(
            "Escalate content changes needed mid-formatting to Executive Editor",
        ),
        outputs_produced=("client presentation deck",),
        kpis=("formatting turnaround time",),
        reporting_line="executive_editor",
    ),
    _Spec(
        key="data_analyst",
        name="Data Analyst",
        description="Prepares, cleans, and analyzes structured "
        "data supporting engagement analyses.",
        practice=PR.DATA_ANALYTICS,
        experience_level=EL.ANALYST,
        primary_responsibilities=(
            "Clean and structure engagement data",
            "Run quantitative analyses",
        ),
        required_capabilities=("data analysis", "data engineering basics"),
        supported_engagement_types=(
            EC.FINANCIAL_PERFORMANCE,
            EC.GROWTH_STRATEGY,
            EC.OPERATIONAL_EXCELLENCE,
        ),
        supported_frameworks=(
            "cost_structure_analysis",
            "profitability_analysis",
            "growth_diagnostic",
        ),
        quality_checklist=("data lineage documented", "outliers investigated"),
        handoff_criteria=("Data validated against a second source where possible",),
        escalation_rules=(
            "Escalate data quality issues to Financial Analyst or Project Leader",
        ),
        outputs_produced=("cleaned datasets", "quantitative analyses"),
        kpis=("data quality issues found post-handoff",),
        reporting_line="project_leader",
    ),
    _Spec(
        key="business_analyst",
        name="Business Analyst",
        description="Bridges business requirements and "
        "analytical execution across workstreams.",
        practice=PR.DATA_ANALYTICS,
        experience_level=EL.ANALYST,
        primary_responsibilities=(
            "Translate business questions into analysis requirements",
        ),
        required_capabilities=(
            "requirements analysis",
            "cross-functional communication",
        ),
        supported_engagement_types=tuple(EC),
        quality_checklist=("requirements traced back to the issue tree",),
        handoff_criteria=("Requirements confirmed with Project Leader",),
        escalation_rules=("Escalate ambiguous requirements to Project Leader",),
        outputs_produced=("analysis requirements", "workstream documentation"),
        kpis=("requirements rework rate",),
        reporting_line="project_leader",
    ),
)


def all_role_definitions() -> tuple[RoleDefinition, ...]:
    return tuple(_build(spec) for spec in _SPECS)
