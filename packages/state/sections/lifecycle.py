"""Lifecycle-audit section models (ADR-002 §2 Lifecycle Status).

These record *how* an engagement progressed — phase transitions, quality-gate
outcomes, and outstanding requirements (execution blockers or missing information).
They are populated by projection (M1.5) from lifecycle/governance/HITL events.
"""

from __future__ import annotations

from datetime import datetime

from common.models import DomainObject
from common.values import Reference
from state.enums import LifecycleStatus
from state.sections.enums import GateResult, PendingKind


class PhaseRecord(DomainObject):
    """A phase entered (and optionally exited) during the engagement (ADR-002 §2)."""

    phase: LifecycleStatus
    entered_at: datetime | None = None
    exited_at: datetime | None = None
    result: str | None = None


class QualityGate(DomainObject):
    """A quality-gate outcome — Reviewer/Challenger (ADR-002 §2)."""

    gate: str
    result: GateResult
    by: str | None = None
    ts: datetime | None = None


class PendingRequirement(DomainObject):
    """An outstanding requirement: an execution blocker or missing information.

    Broadens the ADR-002 §2 ``blocked_on`` marker to represent both categories.
    """

    kind: PendingKind = PendingKind.OTHER
    description: str
    ref: Reference | None = None
