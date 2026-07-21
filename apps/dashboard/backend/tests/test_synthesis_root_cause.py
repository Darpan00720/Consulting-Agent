"""Tests for the root cause analysis engine — 4 methods, multiple root
causes supported throughout."""

from __future__ import annotations

import pytest

from app.synthesis.errors import SynthesisError
from app.synthesis.models import RootCauseMethod, RootCauseNode
from app.synthesis.root_cause import (
    build_root_cause_analysis,
    cause_mapping,
    fault_tree,
    fishbone,
    five_whys,
)


def test_five_whys_single_chain():
    rca = five_whys(
        "Churn increased", (("Churn increased", "Support slow", "Understaffed"),)
    )
    assert rca.method is RootCauseMethod.FIVE_WHYS
    assert len(rca.root_cause_ids) == 1
    root = next(n for n in rca.nodes if n.id in rca.root_cause_ids)
    assert root.statement == "Understaffed"


def test_five_whys_multiple_chains_multiple_root_causes():
    rca = five_whys(
        "Churn increased",
        (
            ("Churn increased", "Support slow", "Understaffed"),
            ("Churn increased", "Pricing uncompetitive"),
        ),
    )
    assert len(rca.root_cause_ids) == 2


def test_fishbone_produces_one_root_cause_per_leaf():
    rca = fishbone(
        "Late deliveries",
        {"people": ("understaffed",), "process": ("no forecasting", "manual routing")},
    )
    assert rca.method is RootCauseMethod.FISHBONE
    assert len(rca.root_cause_ids) == 3


def test_fault_tree_produces_basic_events_as_root_causes():
    rca = fault_tree(
        "Outage",
        "Service unavailable",
        {"Database failure": ("disk full", "replica lag")},
    )
    assert rca.method is RootCauseMethod.FAULT_TREE
    assert len(rca.root_cause_ids) == 2


def test_cause_mapping_finds_leaf_causes_as_root_causes():
    rca = cause_mapping(
        "Revenue decline",
        (
            ("Revenue decline", "Lower conversion"),
            ("Lower conversion", "Slow page load"),
        ),
    )
    assert rca.method is RootCauseMethod.CAUSE_MAPPING
    assert len(rca.root_cause_ids) == 1


def test_build_root_cause_analysis_rejects_duplicate_node_ids():
    nodes = (
        RootCauseNode(id="a", statement="x", parent_id=None),
        RootCauseNode(id="a", statement="y", parent_id=None),
    )
    with pytest.raises(SynthesisError):
        build_root_cause_analysis(RootCauseMethod.FIVE_WHYS, "problem", nodes, ("a",))


def test_build_root_cause_analysis_rejects_missing_parent():
    nodes = (RootCauseNode(id="a", statement="x", parent_id="ghost"),)
    with pytest.raises(SynthesisError):
        build_root_cause_analysis(RootCauseMethod.FIVE_WHYS, "problem", nodes, ("a",))


def test_build_root_cause_analysis_rejects_missing_root_cause_reference():
    nodes = (RootCauseNode(id="a", statement="x", parent_id=None),)
    with pytest.raises(SynthesisError):
        build_root_cause_analysis(
            RootCauseMethod.FIVE_WHYS, "problem", nodes, ("ghost",)
        )
