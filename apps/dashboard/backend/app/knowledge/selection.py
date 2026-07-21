"""Framework selection engine (requester's "Framework Selection" section).

Deterministic, rule-based scoring — no LLM, the same design choice
``app.workflow.router.classify`` and ``app.tools.permissions.PermissionPolicy``
already made in this codebase, for the same reason: auditability. Every
recommendation carries an explicit ``reasoning`` tuple explaining WHY it
scored the way it did — never a black-box rank.
"""

from __future__ import annotations

from app.knowledge.models import (
    FrameworkDefinition,
    FrameworkRecommendation,
    SelectionContext,
    SelectionResult,
)
from app.knowledge.registry import FrameworkRegistry

_ENGAGEMENT_MATCH_WEIGHT = 3.0
_INDUSTRY_MATCH_WEIGHT = 2.0
_COMPANY_SIZE_MATCH_WEIGHT = 2.0
_KEYWORD_MATCH_WEIGHT = 1.0
_DATA_READINESS_WEIGHT = 2.0
_EVIDENCE_READINESS_WEIGHT = 2.0


def _loose_match(needle: str, haystacks: tuple[str, ...]) -> bool:
    """Case-insensitive, direction-agnostic substring match — deterministic
    and simple by design; this is a READINESS signal for selection, not a
    validation gate (``quality.py`` owns the strict version)."""
    n = needle.lower()
    return any(n in h.lower() or h.lower() in n for h in haystacks)


def _readiness(
    required: tuple[str, ...], available: tuple[str, ...]
) -> tuple[int, int]:
    if not required:
        return 0, 0
    matched = sum(1 for r in required if _loose_match(r, available))
    return matched, len(required)


def _keyword_hits(
    business_problem: str, framework: FrameworkDefinition
) -> tuple[str, ...]:
    if not business_problem:
        return ()
    text = business_problem.lower()
    hits = []
    for tag in framework.tags:
        if tag.lower() in text:
            hits.append(tag)
    for word in framework.name.lower().split():
        if len(word) > 4 and word in text and word not in hits:
            hits.append(word)
    return tuple(hits)


def _score_framework(
    framework: FrameworkDefinition, context: SelectionContext
) -> tuple[float, float, tuple[str, ...]]:
    """Returns (score, confidence, reasoning)."""
    score = 0.0
    reasoning: list[str] = []

    score += _ENGAGEMENT_MATCH_WEIGHT
    reasoning.append(f"supports engagement type '{context.engagement_type.value}'")

    industry_match = (
        "all" in framework.supported_industries
        or context.industry in framework.supported_industries
    )
    if industry_match:
        score += _INDUSTRY_MATCH_WEIGHT
        reasoning.append(
            "industry-agnostic"
            if "all" in framework.supported_industries
            else f"industry '{context.industry}' explicitly supported"
        )

    if context.company_size in framework.supported_company_sizes:
        score += _COMPANY_SIZE_MATCH_WEIGHT
        reasoning.append(f"fits company size '{context.company_size.value}'")

    keyword_hits = _keyword_hits(context.business_problem, framework)
    if keyword_hits:
        score += _KEYWORD_MATCH_WEIGHT * len(keyword_hits)
        reasoning.append(f"problem statement matches: {', '.join(keyword_hits)}")

    data_matched, data_total = _readiness(
        framework.required_inputs, context.available_data
    )
    if data_total:
        data_ratio = data_matched / data_total
        score += _DATA_READINESS_WEIGHT * data_ratio
        reasoning.append(f"required inputs available: {data_matched}/{data_total}")
    else:
        data_ratio = 1.0

    evidence_matched, evidence_total = _readiness(
        framework.required_evidence, context.available_evidence
    )
    if evidence_total:
        evidence_ratio = evidence_matched / evidence_total
        score += _EVIDENCE_READINESS_WEIGHT * evidence_ratio
        reasoning.append(
            f"required evidence available: {evidence_matched}/{evidence_total}"
        )
    else:
        evidence_ratio = 1.0

    confidence = min(
        1.0, max(0.0, (data_ratio + evidence_ratio) / 2 * context.confidence + 0.0)
    )
    # Floor confidence at the context's own stated confidence when readiness
    # is perfect, so a caller expressing high confidence isn't silently
    # diluted by a framework with no required inputs/evidence at all.
    if data_total == 0 and evidence_total == 0:
        confidence = context.confidence

    return score, confidence, tuple(reasoning)


def select_frameworks(
    context: SelectionContext,
    registry: FrameworkRegistry,
    *,
    limit: int = 5,
    alternatives_limit: int = 3,
) -> SelectionResult:
    """Score every framework compatible with ``context.engagement_type``,
    rank deterministically, and return the top ``limit`` as recommendations
    plus the next ``alternatives_limit`` as alternatives."""
    candidates = registry.find_by_engagement(context.engagement_type)
    scored = sorted(
        ((_score_framework(f, context), f) for f in candidates),
        key=lambda pair: pair[0][0],
        reverse=True,
    )

    recommended: list[FrameworkRecommendation] = []
    alternatives: list[FrameworkRecommendation] = []
    for i, ((_score, confidence, reasoning), framework) in enumerate(scored):
        rec = FrameworkRecommendation(
            framework_id=framework.id,
            priority=i + 1,
            reasoning=reasoning,
            confidence=confidence,
        )
        if i < limit:
            recommended.append(rec)
        elif i < limit + alternatives_limit:
            alternatives.append(rec)
        else:
            break

    return SelectionResult(
        recommended=tuple(recommended), alternatives=tuple(alternatives)
    )
