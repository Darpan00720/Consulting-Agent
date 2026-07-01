"""M0 Engagement State model tests: valid construction and rejection of bad input."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from state.enums import LifecycleStatus
from state.models import EngagementMetadata, EngagementState


def test_valid_state_constructs() -> None:
    state = EngagementState(
        metadata=EngagementMetadata(
            engagement_id="eng_1", tenant_id="t_1", slug="acme-margin"
        )
    )
    assert state.status is LifecycleStatus.INTAKE
    assert state.metadata.schema_version == 1
    assert state.metadata.state_version == 0


def test_extra_field_is_forbidden() -> None:
    with pytest.raises(ValidationError):
        EngagementMetadata.model_validate(
            {"engagement_id": "e", "tenant_id": "t", "slug": "s", "bogus": "nope"}
        )


def test_invalid_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EngagementState.model_validate(
            {
                "metadata": {"engagement_id": "e", "tenant_id": "t", "slug": "s"},
                "status": "not_a_phase",
            }
        )
