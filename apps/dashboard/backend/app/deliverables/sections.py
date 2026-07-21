"""The shared section library (requester's "Section Model" section) — 14
reusable ``SectionDefinition``s, composed differently by each of the 20
deliverable types in ``catalog.py``. The same "small library of building
blocks, composed by reference" mechanism ``app.consulting.workflow.
standard_workflow`` and ``app.knowledge.catalog`` already established —
deliverable #21 composing a new combination of these needs zero new section
code.

``default_order``/``depends_on`` are the requester's "ordering rules" — a
real, checkable dependency graph (validated the same way
``app.knowledge.registry.resolve_dependency_order`` already validates
framework dependencies).
"""

from __future__ import annotations

from app.deliverables.models import SectionDefinition

_SECTIONS: tuple[SectionDefinition, ...] = (
    SectionDefinition(
        id="cover",
        title="Cover",
        purpose="Identify the engagement, client, and deliverable at a glance.",
        required_inputs=("engagement_category",),
        supported_content=("text",),
        traceability_references=(),
        quality_requirements=("engagement identified",),
        default_order=0,
    ),
    SectionDefinition(
        id="executive_summary",
        title="Executive Summary",
        purpose="State the recommendation and its business case in one page.",
        required_inputs=("recommendations", "narrative"),
        supported_content=("text", "bullets"),
        traceability_references=("recommendation", "narrative"),
        quality_requirements=("headline recommendation stated", "confidence stated"),
        default_order=1,
    ),
    SectionDefinition(
        id="situation_complication_resolution",
        title="Situation, Complication, and Resolution",
        purpose="Frame the business context using the classic consulting "
        "narrative arc.",
        required_inputs=("narrative",),
        supported_content=("text",),
        traceability_references=("narrative", "finding"),
        quality_requirements=(
            "situation stated",
            "complication stated",
            "resolution stated",
        ),
        default_order=2,
        depends_on=("cover",),
    ),
    SectionDefinition(
        id="key_findings",
        title="Key Findings",
        purpose="Present the evidence-backed findings underlying the recommendation.",
        required_inputs=("findings",),
        supported_content=("bullets", "table"),
        traceability_references=("finding", "evidence"),
        quality_requirements=("every finding cites evidence",),
        default_order=3,
    ),
    SectionDefinition(
        id="core_insights",
        title="Core Insights",
        purpose="Synthesize findings into the themes driving the recommendation.",
        required_inputs=("insights",),
        supported_content=("text", "bullets"),
        traceability_references=("insight", "finding"),
        quality_requirements=("every insight cites findings",),
        default_order=4,
        depends_on=("key_findings",),
    ),
    SectionDefinition(
        id="recommendations",
        title="Recommendations",
        purpose="State the approved recommendation(s) and their rationale.",
        required_inputs=("recommendations",),
        supported_content=("text", "bullets", "table"),
        traceability_references=("recommendation", "insight", "finding", "evidence"),
        quality_requirements=("every recommendation is approved", "rationale stated"),
        default_order=5,
        depends_on=("core_insights",),
    ),
    SectionDefinition(
        id="business_case",
        title="Business Case",
        purpose="Quantify cost, benefit, and expected business impact.",
        required_inputs=("recommendations", "business_impact"),
        supported_content=("text", "table", "chart"),
        traceability_references=("recommendation",),
        quality_requirements=("cost stated", "benefit stated", "confidence stated"),
        default_order=6,
        depends_on=("recommendations",),
    ),
    SectionDefinition(
        id="trade_off_analysis",
        title="Trade-off Analysis",
        purpose="Compare the options considered and explain why this one was chosen.",
        required_inputs=("trade_off_result",),
        supported_content=("table", "matrix"),
        traceability_references=("recommendation",),
        quality_requirements=("ranking explained",),
        default_order=7,
        depends_on=("recommendations",),
    ),
    SectionDefinition(
        id="risk_assessment",
        title="Risk Assessment",
        purpose="Name the risks associated with the recommendation and "
        "their mitigations.",
        required_inputs=("recommendations",),
        supported_content=("table", "chart"),
        traceability_references=("recommendation",),
        quality_requirements=("every material risk has a mitigation",),
        default_order=8,
        depends_on=("recommendations",),
    ),
    SectionDefinition(
        id="implementation_roadmap",
        title="Implementation Roadmap",
        purpose="Lay out the phased plan to execute the recommendation.",
        required_inputs=("implementation_themes",),
        supported_content=("text", "chart", "table"),
        traceability_references=("implementation_theme", "recommendation"),
        quality_requirements=("every phase has an owner and timeline",),
        default_order=9,
        depends_on=("recommendations",),
    ),
    SectionDefinition(
        id="kpis_and_outcomes",
        title="KPIs and Expected Outcomes",
        purpose="State how success will be measured.",
        required_inputs=("recommendations",),
        supported_content=("table", "bullets"),
        traceability_references=("recommendation",),
        quality_requirements=("every kpi is measurable",),
        default_order=10,
        depends_on=("implementation_roadmap",),
    ),
    SectionDefinition(
        id="governance_and_approvals",
        title="Governance and Approvals",
        purpose="Record who owns and has approved this deliverable's recommendations.",
        required_inputs=("recommendations",),
        supported_content=("table",),
        traceability_references=("recommendation",),
        quality_requirements=("approval status stated for every recommendation",),
        default_order=11,
        depends_on=("recommendations",),
    ),
    SectionDefinition(
        id="appendix_evidence",
        title="Appendix: Supporting Evidence",
        purpose="Provide the full evidentiary backing for findings and "
        "recommendations.",
        required_inputs=("evidence",),
        supported_content=("table",),
        traceability_references=("evidence", "finding"),
        quality_requirements=("every evidence item is cited by at least one finding",),
        default_order=12,
    ),
    SectionDefinition(
        id="lessons_learned",
        title="Lessons Learned",
        purpose="Capture what worked, what didn't, and what to change next time.",
        required_inputs=("recommendations",),
        supported_content=("bullets",),
        traceability_references=("recommendation",),
        quality_requirements=("at least one lesson stated",),
        default_order=13,
    ),
)

_BY_ID = {s.id: s for s in _SECTIONS}


def all_section_definitions() -> tuple[SectionDefinition, ...]:
    return _SECTIONS


def get_section_definition(section_id: str) -> SectionDefinition:
    from app.deliverables.errors import UnknownSectionError

    if section_id not in _BY_ID:
        raise UnknownSectionError(f"no section definition {section_id!r}")
    return _BY_ID[section_id]


def resolve_order(section_ids: tuple[str, ...]) -> tuple[str, ...]:
    """A real, checkable ordering: sorted by ``default_order``, with a
    dependency-completeness check (a section's ``depends_on`` should already
    be satisfied by an earlier position once sorted by ``default_order`` —
    the shared library is hand-curated so this always holds; this function
    still verifies it rather than assuming it)."""
    from app.deliverables.errors import DeliverableError

    defs = [get_section_definition(sid) for sid in section_ids]
    ordered = tuple(s.id for s in sorted(defs, key=lambda s: s.default_order))
    position = {sid: i for i, sid in enumerate(ordered)}
    for sid in ordered:
        section = _BY_ID[sid]
        for dep in section.depends_on:
            if dep in position and position[dep] > position[sid]:
                raise DeliverableError(
                    f"section {sid!r} depends on {dep!r}, which is ordered after it"
                )
    return ordered
