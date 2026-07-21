"""Tests for the core Organization Layer data model."""

from __future__ import annotations

from app.organization.models import (
    EXPERIENCE_RANK,
    DecisionType,
    ExperienceLevel,
    Practice,
    ReviewStage,
)


def test_practice_has_all_ten_areas():
    assert len(list(Practice)) == 10


def test_experience_level_has_eight_tiers():
    assert len(list(ExperienceLevel)) == 8


def test_experience_rank_covers_every_level_and_is_strictly_ordered():
    levels = list(ExperienceLevel)
    assert set(EXPERIENCE_RANK) == set(levels)
    ranks = [EXPERIENCE_RANK[lvl] for lvl in levels]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)


def test_decision_type_has_all_six_named_decisions():
    assert len(list(DecisionType)) == 6


def test_review_stage_has_all_four_stages():
    assert len(list(ReviewStage)) == 4
