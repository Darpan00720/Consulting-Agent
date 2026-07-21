"""Tests for the core consulting data model (taxonomy, stage order, id gen)."""

from __future__ import annotations

from app.consulting.models import (
    CATEGORY_FAMILY,
    STAGE_ORDER,
    ConsultingStage,
    EngagementCategory,
    EngagementFamily,
    new_assumption_id,
    new_evidence_id,
    new_hypothesis_id,
)


def test_at_least_28_engagement_categories_across_7_families():
    assert len(list(EngagementCategory)) >= 28
    families = {CATEGORY_FAMILY[c] for c in EngagementCategory}
    assert families == set(EngagementFamily)


def test_every_category_maps_to_exactly_one_family():
    for category in EngagementCategory:
        assert category in CATEGORY_FAMILY


def test_stage_order_has_all_ten_stages_exactly_once():
    assert len(STAGE_ORDER) == 10
    assert set(STAGE_ORDER) == set(ConsultingStage)
    assert len(set(STAGE_ORDER)) == len(STAGE_ORDER)


def test_stage_order_starts_with_problem_definition_ends_with_executive_deliverable():
    assert STAGE_ORDER[0] is ConsultingStage.PROBLEM_DEFINITION
    assert STAGE_ORDER[-1] is ConsultingStage.EXECUTIVE_DELIVERABLE


def test_id_generators_produce_unique_ids():
    ids = {new_hypothesis_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(i.startswith("hyp-") for i in ids)


def test_evidence_and_assumption_id_prefixes():
    assert new_evidence_id().startswith("ev-")
    assert new_assumption_id().startswith("asm-")
