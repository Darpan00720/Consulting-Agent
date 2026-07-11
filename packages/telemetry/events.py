"""Canonical telemetry event schema (v1.0 Observability layer).

This is the **operational** observability layer. It is distinct from — and does
not duplicate — the ADR-002 *domain* event log in :mod:`state.events` (which
records what happened to the engagement). Telemetry records *how the machinery
performed*: agent spans, durations, tokens, retries, and validation outcomes.
The two correlate by ``engagement_id``.

One canonical event type (:class:`TelemetryEvent`) carries every field the
observability spec requires; the ``status`` field expresses the agent lifecycle
(started → finished / failed / retried / reworked). Events serialize to JSON
Lines and render to an OpenTelemetry-compatible span shape via ``to_otlp``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from state.identifiers import new_event_id

TELEMETRY_SCHEMA_VERSION = 1


class Phase(StrEnum):
    """Engagement phase a telemetry event belongs to.

    Mirrors the lifecycle vocabulary but is owned by observability (decoupled
    from the frozen ``state.enums.LifecycleStatus``), plus operational phases the
    lifecycle does not name (validation gate, report render).
    """

    INTAKE = "intake"
    CLASSIFY = "classify"
    GAP_ANALYSIS = "gap_analysis"
    PLANNING = "planning"
    FRAMING = "framing"
    ISSUE_TREE = "issue_tree"
    KNOWLEDGE = "knowledge"
    ANALYSIS = "analysis"
    EVIDENCE_VALIDATION = "evidence_validation"
    REVIEW = "review"
    CHALLENGE = "challenge"
    VALIDATION_GATE = "validation_gate"
    REPORTING = "reporting"
    KNOWLEDGE_WRITEBACK = "knowledge_writeback"
    ORCHESTRATION = "orchestration"


class EventStatus(StrEnum):
    """Lifecycle status of the instrumented unit of work."""

    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    RETRIED = "retried"
    REWORKED = "reworked"
    SKIPPED = "skipped"


class ValidationStatus(StrEnum):
    """Outcome of a governance/validation check, when applicable."""

    PASSED = "passed"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"


class TelemetryEvent(BaseModel):
    """One structured observability event. Immutable once created.

    ``duration_ms`` is set on terminal statuses (finished/failed); ``confidence``,
    ``frameworks_used``, and ``tokens`` are populated when the emitting unit
    reports them (e.g. an analyst's telemetry footer). ``metadata`` is a bounded,
    non-sensitive key-value bag (see :mod:`telemetry.recorder` redaction).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # identity / correlation
    event_id: str = Field(default_factory=lambda: str(new_event_id()))
    schema_version: int = TELEMETRY_SCHEMA_VERSION
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    engagement_id: str
    agent_name: str
    phase: Phase

    # lifecycle
    status: EventStatus
    duration_ms: float | None = None
    retry_count: int = 0

    # quality / cost signals (optional — present when reported)
    confidence: float | None = None
    frameworks_used: tuple[str, ...] = ()
    tokens: int | None = None
    validation_status: ValidationStatus | None = None

    # free-form (bounded, non-sensitive)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_otlp(self) -> dict[str, Any]:
        """Render as an OpenTelemetry-compatible span dict (no OTel dep required).

        Maps ``engagement_id`` → trace id, ``event_id`` → span id, and the
        remaining fields → span attributes, so a future OTLP exporter can forward
        events without touching call sites.
        """
        start_ns = int(self.timestamp.timestamp() * 1_000_000_000)
        end_ns = start_ns + int((self.duration_ms or 0.0) * 1_000_000)
        attributes: dict[str, Any] = {
            "stratagent.phase": self.phase.value,
            "stratagent.status": self.status.value,
            "stratagent.retry_count": self.retry_count,
        }
        if self.confidence is not None:
            attributes["stratagent.confidence"] = self.confidence
        if self.frameworks_used:
            attributes["stratagent.frameworks_used"] = list(self.frameworks_used)
        if self.tokens is not None:
            attributes["stratagent.tokens"] = self.tokens
        if self.validation_status is not None:
            attributes["stratagent.validation_status"] = self.validation_status.value
        attributes.update({f"stratagent.meta.{k}": v for k, v in self.metadata.items()})
        otel_status = "ERROR" if self.status is EventStatus.FAILED else "OK"
        return {
            "name": f"{self.agent_name}:{self.phase.value}",
            "trace_id": self.engagement_id,
            "span_id": self.event_id,
            "start_time_unix_nano": start_ns,
            "end_time_unix_nano": end_ns,
            "attributes": attributes,
            "status": {"code": otel_status},
        }
