"""Foundational Engagement State models (ADR-002).

M0 builds only the minimal slice needed to establish the Pydantic -> JSON-Schema
pipeline and exercise the quality gate: Engagement Metadata (§1) and the root
state shell carrying Lifecycle Status (§2). M1 extends ``EngagementState`` with the
remaining ADR-002 sections, the event model, projection, and invariants.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from core.base import StratAgentModel
from state.enums import LifecycleStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EngagementMetadata(StratAgentModel):
    """ADR-002 §1 — Engagement Metadata."""

    engagement_id: str
    tenant_id: str
    slug: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    created_by: Literal["human", "system"] = "human"
    state_version: int = 0
    schema_version: int = 1


class EngagementState(StratAgentModel):
    """Root Engagement State (M0 foundational slice).

    Extended in M1 with the remaining ADR-002 sections (problem definition,
    ledgers, analysis sections, gates, recommendation, audit trail, ...).
    """

    metadata: EngagementMetadata
    status: LifecycleStatus = LifecycleStatus.INTAKE
