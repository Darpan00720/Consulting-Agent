"""Work allocation engine (requester's "Work Allocation" section).

Deterministic, rule-based scoring — the same no-LLM, auditable design choice
``app.knowledge.selection`` and ``app.workflow.router.classify`` already
made in this codebase. Every assignment carries an explicit ``reasoning``
tuple.
"""

from __future__ import annotations

from app.consulting.models import ConsultingStage
from app.organization.models import (
    AllocationContext,
    AllocationResult,
    Practice,
    RoleAssignment,
)
from app.organization.registry import OrganizationRegistry

_FRAMEWORK_MATCH_WEIGHT = 3.0
_CAPABILITY_MATCH_WEIGHT = 2.0
_PRACTICE_RELEVANCE_WEIGHT = 2.0

# Which practices are typically load-bearing at each lifecycle stage — a
# staffing heuristic, not a hard requirement (a role can still be assigned
# with zero practice-relevance score if its frameworks/capabilities match).
_STAGE_PRACTICE_RELEVANCE: dict[ConsultingStage, tuple[Practice, ...]] = {
    ConsultingStage.PROBLEM_DEFINITION: (Practice.STRATEGY,),
    ConsultingStage.HYPOTHESIS_DEVELOPMENT: (
        Practice.STRATEGY,
        Practice.MARKET_RESEARCH,
    ),
    ConsultingStage.ISSUE_TREE_CONSTRUCTION: (Practice.STRATEGY,),
    ConsultingStage.ANALYSIS_PLANNING: (Practice.STRATEGY, Practice.DATA_ANALYTICS),
    ConsultingStage.EVIDENCE_COLLECTION: (
        Practice.MARKET_RESEARCH,
        Practice.KNOWLEDGE_MANAGEMENT,
    ),
    ConsultingStage.ANALYSIS_EXECUTION: (
        Practice.FINANCE,
        Practice.OPERATIONS,
        Practice.DIGITAL_AI,
        Practice.DATA_ANALYTICS,
        Practice.RISK,
    ),
    ConsultingStage.SYNTHESIS: (Practice.STRATEGY,),
    ConsultingStage.RECOMMENDATIONS: (Practice.STRATEGY,),
    ConsultingStage.IMPLEMENTATION_ROADMAP: (Practice.IMPLEMENTATION,),
    ConsultingStage.EXECUTIVE_DELIVERABLE: (Practice.QUALITY_EDITORIAL,),
}

# Team leads are always included — every engagement needs a single
# accountable delivery lead, independent of framework/stage scoring.
_ALWAYS_INCLUDE = ("engagement_manager", "project_leader")


def _loose_match(needle: str, haystacks: tuple[str, ...]) -> bool:
    n = needle.lower()
    return any(n in h.lower() or h.lower() in n for h in haystacks)


def _score_role(role, context: AllocationContext) -> tuple[float, tuple[str, ...]]:
    score = 0.0
    reasoning: list[str] = []

    framework_overlap = set(role.supported_frameworks) & set(
        context.frameworks_selected
    )
    if framework_overlap:
        score += _FRAMEWORK_MATCH_WEIGHT * len(framework_overlap)
        reasoning.append(
            f"supports selected framework(s): {', '.join(sorted(framework_overlap))}"
        )

    capability_hits = [
        req
        for req in context.required_expertise
        if _loose_match(req, role.required_capabilities)
    ]
    if capability_hits:
        score += _CAPABILITY_MATCH_WEIGHT * len(capability_hits)
        reasoning.append(f"required expertise match: {', '.join(capability_hits)}")

    relevant_practices = _STAGE_PRACTICE_RELEVANCE.get(context.workflow_stage, ())
    if role.practice in relevant_practices:
        score += _PRACTICE_RELEVANCE_WEIGHT
        reasoning.append(
            f"practice '{role.practice.value}' relevant to stage "
            f"'{context.workflow_stage.value}'"
        )

    return score, tuple(reasoning)


def allocate_team(
    context: AllocationContext, registry: OrganizationRegistry, *, limit: int = 6
) -> AllocationResult:
    """Score every role compatible with ``context.engagement_type``, always
    include the delivery leads, and return the top ``limit`` specialists with
    a normalized work distribution."""
    candidates = registry.find_by_engagement(context.engagement_type)
    scored = [(role, *_score_role(role, context)) for role in candidates]
    scored.sort(key=lambda triple: triple[1], reverse=True)

    leads = [
        (role, 0.0, ("always assigned as delivery lead",))
        for role in candidates
        if role.id in _ALWAYS_INCLUDE
    ]
    lead_ids = {role.id for role, _s, _r in leads}
    specialists = [t for t in scored if t[0].id not in lead_ids][:limit]

    team = leads + specialists
    total_score = sum(max(s, 0.1) for _r, s, _reason in team) or 1.0
    assignments = tuple(
        RoleAssignment(
            role_id=role.id,
            reasoning=reasoning,
            workload_share=max(score, 0.1) / total_score,
        )
        for role, score, reasoning in team
    )
    confidence = context.confidence if candidates else 0.0
    return AllocationResult(recommended_team=assignments, confidence=confidence)
