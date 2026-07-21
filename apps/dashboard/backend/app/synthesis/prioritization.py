"""Prioritization engine (requester's "Prioritization" section): real,
deterministic scoring formulas for Impact vs Effort, ICE, RICE, Weighted
Scoring, Strategic Alignment, and Risk-adjusted priority.

The FORMULAS are genuine, reusable code (the same "generic math over
caller-supplied judgment ratings" already established for
``app.synthesis.tradeoff`` and, one layer down, ``app.knowledge``'s
Sensitivity Analysis/DCF framework entries) — what's caller-supplied is the
underlying 0-10 (or 0-1) judgment scores (impact, effort, confidence, ...),
never the arithmetic itself.
"""

from __future__ import annotations

from app.synthesis.models import (
    PrioritizationInput,
    PrioritizationMethod,
    PrioritizationResult,
    PrioritizationScore,
)

_EPSILON = 0.01


def _impact_vs_effort(item: PrioritizationInput) -> tuple[float, str]:
    score = item.impact / max(item.effort, _EPSILON)
    return score, f"impact {item.impact:.1f} / effort {item.effort:.1f} = {score:.2f}"


def _ice(item: PrioritizationInput) -> tuple[float, str]:
    score = (item.impact + item.confidence + item.ease) / 3
    return (
        score,
        f"(impact {item.impact:.1f} + confidence {item.confidence:.1f} + "
        f"ease {item.ease:.1f}) / 3 = {score:.2f}",
    )


def _rice(item: PrioritizationInput) -> tuple[float, str]:
    score = (item.reach * item.impact * item.confidence) / max(item.effort, _EPSILON)
    return score, (
        f"(reach {item.reach:.1f} x impact {item.impact:.1f} x confidence "
        f"{item.confidence:.1f}) / effort {item.effort:.1f} = {score:.2f}"
    )


def _weighted_scoring(item: PrioritizationInput) -> tuple[float, str]:
    fields = {
        "impact": item.impact,
        "effort": item.effort,
        "confidence": item.confidence,
        "reach": item.reach,
        "ease": item.ease,
        "strategic_alignment": item.strategic_alignment,
        "risk": item.risk,
    }
    score = sum(item.weights.get(name, 0.0) * value for name, value in fields.items())
    used = ", ".join(
        f"{name}*{w:.2f}" for name, w in item.weights.items() if name in fields
    )
    return score, f"weighted sum ({used}) = {score:.2f}"


def _strategic_alignment(item: PrioritizationInput) -> tuple[float, str]:
    confidence_factor = item.confidence if item.confidence > 0 else 1.0
    score = item.strategic_alignment * confidence_factor
    return (
        score,
        f"strategic_alignment {item.strategic_alignment:.1f} x confidence "
        f"factor {confidence_factor:.1f} = {score:.2f}",
    )


def _risk_adjusted(item: PrioritizationInput) -> tuple[float, str]:
    base = item.impact / max(item.effort, _EPSILON)
    score = base * (1 - item.risk)
    return (
        score,
        f"(impact/effort {base:.2f}) x (1 - risk {item.risk:.1f}) = {score:.2f}",
    )


_SCORERS = {
    PrioritizationMethod.IMPACT_VS_EFFORT: _impact_vs_effort,
    PrioritizationMethod.ICE: _ice,
    PrioritizationMethod.RICE: _rice,
    PrioritizationMethod.WEIGHTED_SCORING: _weighted_scoring,
    PrioritizationMethod.STRATEGIC_ALIGNMENT: _strategic_alignment,
    PrioritizationMethod.RISK_ADJUSTED: _risk_adjusted,
}


def prioritize(
    method: PrioritizationMethod, items: tuple[PrioritizationInput, ...]
) -> PrioritizationResult:
    scorer = _SCORERS[method]
    raw = [(item.item_id, *scorer(item)) for item in items]
    raw.sort(key=lambda triple: triple[1], reverse=True)
    scores = tuple(
        PrioritizationScore(
            item_id=item_id,
            method=method,
            score=score,
            rank=i + 1,
            explanation=explanation,
        )
        for i, (item_id, score, explanation) in enumerate(raw)
    )
    return PrioritizationResult(method=method, scores=scores)
