"""Tests for ``OrganizationRegistry`` — registration, versioning, search
axes, reporting-chain walk."""

from __future__ import annotations

import dataclasses

import pytest

from app.consulting.models import EngagementCategory as EC
from app.organization.errors import DuplicateRoleError, UnknownRoleError
from app.organization.models import DecisionType, Practice
from app.organization.registry import (
    OrganizationRegistry,
    default_organization_registry,
)


def test_default_registry_registers_all_25():
    r = default_organization_registry()
    assert len(r.list()) == 25


def test_duplicate_registration_raises():
    r = default_organization_registry()
    with pytest.raises(DuplicateRoleError):
        r.register(r.get("partner"))


def test_unknown_role_raises():
    r = default_organization_registry()
    with pytest.raises(UnknownRoleError):
        r.get("does_not_exist")


def test_versioning_get_without_version_returns_latest():
    r = OrganizationRegistry()
    base = default_organization_registry().get("partner")
    v1 = dataclasses.replace(base, version="1.0.0")
    v2 = dataclasses.replace(base, version="1.1.0")
    r.register(v1)
    r.register(v2)
    assert r.get("partner").version == "1.1.0"
    assert r.get("partner", "1.0.0").version == "1.0.0"


def test_find_by_practice():
    r = default_organization_registry()
    found = r.find_by_practice(Practice.FINANCE)
    assert {x.id for x in found} == {"financial_analyst"}


def test_find_by_capability():
    r = default_organization_registry()
    found = r.find_by_capability("financial modeling")
    assert any(x.id == "financial_analyst" for x in found)


def test_find_by_engagement():
    r = default_organization_registry()
    found = r.find_by_engagement(EC.MARKET_ENTRY)
    ids = {x.id for x in found}
    assert "financial_analyst" in ids
    assert "strategy_consultant" in ids


def test_find_by_decision_authority():
    r = default_organization_registry()
    found = r.find_by_decision_authority(DecisionType.APPROVE_EXECUTIVE_SUMMARIES)
    assert {x.id for x in found} == {"managing_partner"}


def test_reporting_chain_walks_all_the_way_to_the_top():
    r = default_organization_registry()
    chain = r.reporting_chain("data_analyst")
    assert chain[0].id == "data_analyst"
    assert chain[-1].id == "managing_partner"
    assert chain[-1].reporting_line is None


def test_reporting_chain_of_the_top_role_is_just_itself():
    r = default_organization_registry()
    chain = r.reporting_chain("managing_partner")
    assert [x.id for x in chain] == ["managing_partner"]
