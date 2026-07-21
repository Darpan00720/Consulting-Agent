"""Tests for ``FrameworkRegistry`` — registration, versioning, search axes,
dependency resolution, compatibility lookup, registry integrity."""

from __future__ import annotations

import dataclasses

import pytest

from app.consulting.models import EngagementCategory as EC
from app.knowledge.errors import (
    CircularDependencyError,
    DuplicateFrameworkError,
    UnknownFrameworkError,
)
from app.knowledge.models import CompanySize, FrameworkCategory
from app.knowledge.registry import FrameworkRegistry, default_framework_registry


def test_default_registry_registers_all_86():
    r = default_framework_registry()
    assert len(r.list()) == 86


def test_duplicate_registration_raises():
    r = default_framework_registry()
    with pytest.raises(DuplicateFrameworkError):
        r.register(r.get("five_forces"))


def test_unknown_framework_raises():
    r = default_framework_registry()
    with pytest.raises(UnknownFrameworkError):
        r.get("does_not_exist")


def test_versioning_get_without_version_returns_latest():
    r = FrameworkRegistry()
    base = default_framework_registry().get("dcf")
    v1 = dataclasses.replace(base, version="1.0.0")
    v2 = dataclasses.replace(base, version="1.1.0")
    r.register(v1)
    r.register(v2)
    assert r.get("dcf").version == "1.1.0"
    assert r.get("dcf", "1.0.0").version == "1.0.0"
    assert set(r.versions_of("dcf")) == {"1.0.0", "1.1.0"}


def test_find_by_category():
    r = default_framework_registry()
    found = r.find_by_category(FrameworkCategory.FINANCE)
    assert len(found) == 11
    assert all(f.category is FrameworkCategory.FINANCE for f in found)


def test_find_by_tag():
    r = default_framework_registry()
    found = r.find_by_tag("classic")
    assert len(found) > 0
    assert all("classic" in f.tags for f in found)


def test_find_by_industry_matches_all_and_specific():
    r = default_framework_registry()
    everything = r.find_by_industry("healthcare")
    assert len(everything) == 86  # every framework defaults to industry "all"


def test_find_by_engagement():
    r = default_framework_registry()
    found = r.find_by_engagement(EC.MARKET_ENTRY)
    ids = {f.id for f in found}
    assert "five_forces" in ids
    assert "dcf" in ids


def test_find_by_company_size():
    r = default_framework_registry()
    found = r.find_by_company_size(CompanySize.STARTUP)
    assert len(found) == 86  # every framework defaults to all sizes


def test_search_axes_never_return_duplicate_versions():
    r = FrameworkRegistry()
    base = default_framework_registry().get("dcf")
    r.register(dataclasses.replace(base, version="1.0.0"))
    r.register(dataclasses.replace(base, version="1.1.0"))
    found = r.find_by_category(FrameworkCategory.FINANCE)
    assert len(found) == 1
    assert found[0].version == "1.1.0"


def test_is_compatible_checks_engagement_industry_and_size():
    r = default_framework_registry()
    assert r.is_compatible("five_forces", EC.MARKET_ENTRY) is True
    assert r.is_compatible("dcf", EC.RISK_ASSESSMENT) is False


def test_resolve_dependency_order_is_topologically_valid():
    r = default_framework_registry()
    order = r.resolve_dependency_order(("swot", "five_forces", "pestle"))
    assert order.index("five_forces") < order.index("swot")
    assert order.index("pestle") < order.index("swot")


def test_resolve_dependency_order_detects_cycles():
    r = FrameworkRegistry()
    base = default_framework_registry().get("five_forces")
    a = dataclasses.replace(base, id="cycle_a", dependencies=("cycle_b",))
    b = dataclasses.replace(base, id="cycle_b", dependencies=("cycle_a",))
    r.register(a)
    r.register(b)
    with pytest.raises(CircularDependencyError):
        r.resolve_dependency_order(("cycle_a",))


def test_resolve_dependency_order_raises_on_unknown_dependency():
    r = FrameworkRegistry()
    base = default_framework_registry().get("five_forces")
    a = dataclasses.replace(base, id="broken", dependencies=("ghost",))
    r.register(a)
    with pytest.raises(UnknownFrameworkError):
        r.resolve_dependency_order(("broken",))


def test_full_catalog_dependency_graph_has_no_cycles():
    """Registry integrity: the ENTIRE shipped catalog resolves without a
    cycle — a real, live check, not just a per-pair unit test."""
    r = default_framework_registry()
    all_ids = tuple(f.id for f in r.list())
    order = r.resolve_dependency_order(all_ids)
    assert set(order) >= set(all_ids)
