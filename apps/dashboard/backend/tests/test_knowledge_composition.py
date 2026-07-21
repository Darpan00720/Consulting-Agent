"""Tests for the framework composition validator, including the requester's
own Market Entry worked example."""

from __future__ import annotations

from app.consulting.models import EngagementCategory as EC
from app.knowledge.composition import validate_composition
from app.knowledge.registry import default_framework_registry


def test_market_entry_worked_example_composes_cleanly():
    """PESTLE -> Five Forces -> TAM/SAM/SOM -> SWOT -> Financial Model
    (dcf) -> Risk Matrix — the requester's exact named chain."""
    r = default_framework_registry()
    chain = ("pestle", "five_forces", "tam_sam_som", "swot", "dcf", "risk_matrix")
    plan = validate_composition(chain, r, engagement=EC.MARKET_ENTRY)
    assert plan.valid
    assert plan.execution_order == chain


def test_unknown_framework_id_is_invalid():
    r = default_framework_registry()
    plan = validate_composition(("five_forces", "ghost_framework"), r)
    assert not plan.valid
    assert any("ghost_framework" in i.framework_id for i in plan.issues)


def test_incompatible_engagement_is_invalid():
    r = default_framework_registry()
    # dcf supports MARKET_ENTRY (it's part of the requester's own worked
    # example chain) but not CHANGE_MANAGEMENT — a genuine mismatch.
    plan = validate_composition(("dcf",), r, engagement=EC.CHANGE_MANAGEMENT)
    assert not plan.valid
    assert any("does not support engagement" in i.reason for i in plan.issues)


def test_out_of_order_dependency_is_corrected_and_advisory_only():
    r = default_framework_registry()
    plan = validate_composition(("swot", "five_forces", "pestle"), r)
    assert plan.valid  # correctable, so still usable
    assert plan.execution_order.index("five_forces") < plan.execution_order.index(
        "swot"
    )
    assert plan.execution_order.index("pestle") < plan.execution_order.index("swot")
    assert any("appears AFTER it" in i.reason for i in plan.issues)


def test_circular_dependency_is_invalid():
    import dataclasses

    from app.knowledge.registry import FrameworkRegistry

    r = FrameworkRegistry()
    base = default_framework_registry().get("five_forces")
    a = dataclasses.replace(base, id="cyc_a", dependencies=("cyc_b",))
    b = dataclasses.replace(base, id="cyc_b", dependencies=("cyc_a",))
    r.register(a)
    r.register(b)
    plan = validate_composition(("cyc_a", "cyc_b"), r)
    assert not plan.valid


def test_implicit_dependency_pulled_in_is_advisory():
    r = default_framework_registry()
    # "swot" alone requires five_forces + pestle as dependencies but they
    # aren't in the requested list -> pulled in implicitly, still valid.
    plan = validate_composition(("swot",), r)
    assert plan.valid
    assert "five_forces" in plan.execution_order
    assert "pestle" in plan.execution_order
    assert any("pulled in implicitly" in i.reason for i in plan.issues)
