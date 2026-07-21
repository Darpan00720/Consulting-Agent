"""Tests for the core Knowledge Library data model."""

from __future__ import annotations

from app.knowledge.models import (
    CompanySize,
    FrameworkCategory,
    OutputSchema,
)


def test_framework_category_has_all_nine_sections():
    assert len(list(FrameworkCategory)) == 9


def test_company_size_has_four_tiers():
    assert len(list(CompanySize)) == 4


def test_output_schema_holds_field_names_not_values():
    schema = OutputSchema(fields=("valuation range", "confidence"))
    assert schema.fields == ("valuation range", "confidence")
