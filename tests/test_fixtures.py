"""Validate that the sample fixtures behave as expected against the models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from state.models import EngagementState

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_valid_fixture_validates() -> None:
    data = json.loads((_FIXTURES / "valid_engagement.json").read_text(encoding="utf-8"))
    state = EngagementState.model_validate(data)
    assert state.metadata.engagement_id == "eng_demo"


def test_invalid_fixture_is_rejected() -> None:
    data = json.loads(
        (_FIXTURES / "invalid_engagement.json").read_text(encoding="utf-8")
    )
    with pytest.raises(ValidationError):
        EngagementState.model_validate(data)
