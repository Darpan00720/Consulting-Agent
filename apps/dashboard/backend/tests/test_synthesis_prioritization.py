"""Tests for the prioritization engine — 6 named methods."""

from __future__ import annotations

from app.synthesis.models import PrioritizationInput
from app.synthesis.models import PrioritizationMethod as PM
from app.synthesis.prioritization import prioritize


def test_impact_vs_effort_ranks_higher_ratio_first():
    items = (
        PrioritizationInput(item_id="a", impact=8, effort=2),
        PrioritizationInput(item_id="b", impact=8, effort=8),
    )
    result = prioritize(PM.IMPACT_VS_EFFORT, items)
    assert result.scores[0].item_id == "a"
    assert result.scores[0].rank == 1


def test_ice_averages_the_three_scores():
    items = (PrioritizationInput(item_id="a", impact=9, confidence=6, ease=3),)
    result = prioritize(PM.ICE, items)
    assert abs(result.scores[0].score - 6.0) < 1e-9


def test_rice_formula():
    items = (
        PrioritizationInput(
            item_id="a", reach=1000, impact=2, confidence=0.8, effort=4
        ),
    )
    result = prioritize(PM.RICE, items)
    expected = (1000 * 2 * 0.8) / 4
    assert abs(result.scores[0].score - expected) < 1e-6


def test_weighted_scoring_uses_supplied_weights():
    items = (
        PrioritizationInput(item_id="a", impact=10, risk=0.0, weights={"impact": 1.0}),
    )
    result = prioritize(PM.WEIGHTED_SCORING, items)
    assert abs(result.scores[0].score - 10.0) < 1e-9


def test_strategic_alignment_scales_by_confidence():
    items = (
        PrioritizationInput(item_id="a", strategic_alignment=8, confidence=0.5),
        PrioritizationInput(item_id="b", strategic_alignment=8, confidence=1.0),
    )
    result = prioritize(PM.STRATEGIC_ALIGNMENT, items)
    b_score = next(s.score for s in result.scores if s.item_id == "b")
    a_score = next(s.score for s in result.scores if s.item_id == "a")
    assert b_score > a_score


def test_risk_adjusted_penalizes_high_risk():
    items = (
        PrioritizationInput(item_id="a", impact=8, effort=2, risk=0.0),
        PrioritizationInput(item_id="b", impact=8, effort=2, risk=0.8),
    )
    result = prioritize(PM.RISK_ADJUSTED, items)
    assert result.scores[0].item_id == "a"


def test_every_score_has_a_rank_and_explanation():
    items = (
        PrioritizationInput(item_id="a", impact=5, effort=1),
        PrioritizationInput(item_id="b", impact=3, effort=1),
    )
    result = prioritize(PM.IMPACT_VS_EFFORT, items)
    ranks = [s.rank for s in result.scores]
    assert ranks == [1, 2]
    assert all(s.explanation for s in result.scores)


def test_zero_effort_does_not_raise_division_error():
    items = (PrioritizationInput(item_id="a", impact=5, effort=0.0),)
    result = prioritize(PM.IMPACT_VS_EFFORT, items)
    assert result.scores[0].score > 0
