"""Tests for the core Deliverables Engine data model."""

from __future__ import annotations

from app.deliverables.models import Audience, DeliverableType, ExportFormat, VisualType


def test_deliverable_type_has_all_20_named_types():
    assert len(list(DeliverableType)) == 20


def test_audience_has_all_8_named_audiences():
    assert len(list(Audience)) == 8


def test_export_format_has_all_6_named_formats():
    assert len(list(ExportFormat)) == 6


def test_visual_type_has_all_9_named_types():
    assert len(list(VisualType)) == 9
