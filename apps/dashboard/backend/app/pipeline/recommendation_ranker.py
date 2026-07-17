"""Recommendation Ranker (ADR-010 Phase 3).

The LLM proposes each :class:`~app.pipeline.consulting_schema.StrategicOption`
and scores it, per criterion, in [0, 1] — a judgment call, unavoidable (is
this option's execution risk "low"? that's an assessment, not arithmetic).
What this module does is the part that IS arithmetic: combining those
declared scores into ONE final ranking via an explicit, documented formula.

The final ``rank`` is NEVER the LLM's own claimed ordering — the same
discipline P1 applies to a derived ledger value (an LLM's stated number is
discarded; only the computed one is trusted). If an LLM asserts "Option B is
our top recommendation," this module either confirms that computationally or
contradicts it — and the computed ranking wins, exactly as a re-evaluated
formula wins over an LLM's stated value in the Quant Gate.
"""

from __future__ import annotations

from app.pipeline.consulting_schema import CRITERIA, Recommendation, StrategicOption

# One weight per CRITERIA entry (ADR-010 §6b), summing to 1.0. A documented
# default — not yet tuned against real engagements (see ADR-010 known
# limitations), but explicit and inspectable rather than implicit.
DEFAULT_WEIGHTS: dict[str, float] = {
    "strategic_value": 0.20,
    "business_impact": 0.20,
    "low_execution_risk": 0.15,
    "confidence": 0.15,
    "evidence_quality": 0.10,
    "low_complexity": 0.10,
    "low_dependency_burden": 0.05,
    "fast_time_to_value": 0.05,
}
assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9
assert set(DEFAULT_WEIGHTS) == set(CRITERIA)

# Below this composite score, an option is REJECTED rather than merely ranked
# last — the spec's "reject weak recommendations", not just deprioritize them.
DEFAULT_REJECTION_FLOOR = 0.35


def composite_score(
    option: StrategicOption, weights: dict[str, float] = DEFAULT_WEIGHTS
) -> float:
    """The one documented formula every option's final score comes from —
    schema validation (``StrategicOption.__post_init__``) already guarantees
    every criterion is present and in [0, 1], so this is a pure weighted sum,
    no defensive branching needed."""
    total: float = sum(weights[c] * option.scores[c] for c in CRITERIA)
    return total


def rank(
    options: list[StrategicOption],
    *,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    rejection_floor: float = DEFAULT_REJECTION_FLOOR,
) -> list[Recommendation]:
    """Rank every option by :func:`composite_score`. Options at/above the
    rejection floor are ranked 1..N by descending score; options below it are
    marked ``rejected`` with the composite score in the reason, and are NOT
    assigned a competitive rank (rank 0 — "did not qualify", not "came last")."""
    scored = [(composite_score(o, weights), o) for o in options]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    recommendations: list[Recommendation] = []
    next_rank = 1
    for score, option in scored:
        if score < rejection_floor:
            recommendations.append(
                Recommendation(
                    option_id=option.option_id,
                    rank=0,
                    composite_score=score,
                    status="rejected",
                    rejection_reason=(
                        f"composite score {score:.3f} is below the rejection "
                        f"floor {rejection_floor:.3f}."
                    ),
                )
            )
            continue
        recommendations.append(
            Recommendation(
                option_id=option.option_id,
                rank=next_rank,
                composite_score=score,
                status="recommended",
            )
        )
        next_rank += 1
    return recommendations
