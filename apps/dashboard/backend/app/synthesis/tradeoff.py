"""Trade-off analysis engine (requester's "Trade-off Analysis" section):
structured comparison across the 8 named dimensions, weighted scoring,
ranking, and explicit reasoning per rank.

Deterministic weighted-sum scoring — the SCORES per option/dimension are
caller-supplied judgment (an analyst rates Option A's financial dimension a
7/10); this module only combines them consistently and explains the result,
the same "generic math over caller-supplied judgment" split
``app.knowledge.execution`` already established for framework execution.
"""

from __future__ import annotations

from app.synthesis.models import TRADE_OFF_DIMENSIONS, TradeOffOption, TradeOffResult


def compare_options(
    options: tuple[TradeOffOption, ...],
    *,
    dimension_weights: dict | None = None,
) -> TradeOffResult:
    """Every dimension not explicitly weighted gets an equal default share
    of the remaining weight, so a caller can weight only the dimensions that
    matter for this decision without having to enumerate all 8."""
    weights = dict(dimension_weights or {})
    unweighted = [d for d in TRADE_OFF_DIMENSIONS if d not in weights]
    remaining = max(0.0, 1.0 - sum(weights.values()))
    if unweighted:
        share = remaining / len(unweighted)
        for dim in unweighted:
            weights[dim] = share

    scores: dict[str, float] = {}
    for option in options:
        total = sum(
            weights.get(dim, 0.0) * option.dimension_scores.get(dim, 0.0)
            for dim in TRADE_OFF_DIMENSIONS
        )
        scores[option.id] = total

    ranked_ids = tuple(sorted(scores, key=lambda oid: scores[oid], reverse=True))

    reasoning: list[str] = []
    by_id = {o.id: o for o in options}
    for rank, option_id in enumerate(ranked_ids, start=1):
        option = by_id[option_id]
        top_dims = sorted(
            option.dimension_scores.items(), key=lambda kv: kv[1], reverse=True
        )[:2]
        top_desc = ", ".join(f"{d}={v:.1f}" for d, v in top_dims)
        reasoning.append(
            f"#{rank} {option.name} (score={scores[option_id]:.2f}) — "
            f"strongest on {top_desc}"
        )

    return TradeOffResult(
        options=options,
        dimension_weights=weights,
        scores=scores,
        ranked_option_ids=ranked_ids,
        reasoning=tuple(reasoning),
    )
