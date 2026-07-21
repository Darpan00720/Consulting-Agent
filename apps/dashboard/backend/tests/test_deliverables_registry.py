"""Tests for ``DeliverableRegistry``."""

from __future__ import annotations

import dataclasses

import pytest

from app.consulting.models import EngagementCategory as EC
from app.deliverables.errors import (
    DuplicateDeliverableTypeError,
    UnknownDeliverableTypeError,
)
from app.deliverables.models import Audience
from app.deliverables.registry import DeliverableRegistry, default_deliverable_registry


def test_default_registry_registers_all_20():
    r = default_deliverable_registry()
    assert len(r.list()) == 20


def test_duplicate_registration_raises():
    r = default_deliverable_registry()
    with pytest.raises(DuplicateDeliverableTypeError):
        r.register(r.get("executive_summary"))


def test_unknown_deliverable_raises():
    r = default_deliverable_registry()
    with pytest.raises(UnknownDeliverableTypeError):
        r.get("does_not_exist")


def test_versioning_get_without_version_returns_latest():
    r = DeliverableRegistry()
    base = default_deliverable_registry().get("business_case")
    v1 = dataclasses.replace(base, version="1.0.0")
    v2 = dataclasses.replace(base, version="1.1.0")
    r.register(v1)
    r.register(v2)
    assert r.get("business_case").version == "1.1.0"
    assert r.get("business_case", "1.0.0").version == "1.0.0"


def test_find_by_audience():
    r = default_deliverable_registry()
    found = r.find_by_audience(Audience.CFO)
    ids = {d.id for d in found}
    assert "business_case" in ids
    assert "investment_committee_memo" in ids


def test_find_by_engagement():
    r = default_deliverable_registry()
    found = r.find_by_engagement(EC.MARKET_ENTRY)
    assert any(d.id == "market_entry_report" for d in found)


def test_find_by_tag():
    r = default_deliverable_registry()
    found = r.find_by_tag("board")
    assert any(d.id == "board_presentation" for d in found)
