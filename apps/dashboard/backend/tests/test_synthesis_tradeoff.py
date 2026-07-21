"""Tests for the trade-off analysis engine."""

from __future__ import annotations

from app.synthesis.models import TradeOffOption
from app.synthesis.tradeoff import compare_options


def test_ranks_options_by_weighted_score():
    options = (
        TradeOffOption(
            id="a", name="Option A", dimension_scores={"financial": 9, "risk": 2}
        ),
        TradeOffOption(
            id="b", name="Option B", dimension_scores={"financial": 3, "risk": 8}
        ),
    )
    result = compare_options(options, dimension_weights={"financial": 0.7, "risk": 0.3})
    assert result.ranked_option_ids[0] == "a"
    assert result.scores["a"] > result.scores["b"]


def test_unweighted_dimensions_share_remaining_weight_equally():
    options = (
        TradeOffOption(
            id="a",
            name="A",
            dimension_scores=dict.fromkeys(
                (
                    "financial",
                    "operational",
                    "customer",
                    "technology",
                    "risk",
                    "implementation",
                    "organizational",
                    "strategic_alignment",
                ),
                5.0,
            ),
        ),
    )
    result = compare_options(options)
    # all 8 dimensions unweighted -> each gets 1/8
    assert all(abs(w - 1 / 8) < 1e-9 for w in result.dimension_weights.values())


def test_reasoning_is_provided_per_ranked_option():
    options = (
        TradeOffOption(id="a", name="Option A", dimension_scores={"financial": 9}),
        TradeOffOption(id="b", name="Option B", dimension_scores={"financial": 4}),
    )
    result = compare_options(options)
    assert len(result.reasoning) == 2
    assert result.reasoning[0].startswith("#1")


def test_three_option_comparison_ranks_all_three():
    options = (
        TradeOffOption(id="a", name="A", dimension_scores={"financial": 5}),
        TradeOffOption(id="b", name="B", dimension_scores={"financial": 9}),
        TradeOffOption(id="c", name="C", dimension_scores={"financial": 1}),
    )
    result = compare_options(options, dimension_weights={"financial": 1.0})
    assert result.ranked_option_ids == ("b", "a", "c")
