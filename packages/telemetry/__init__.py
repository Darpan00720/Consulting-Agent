"""StratAgent Observability — telemetry layer (v1.0).

Operational observability that sits alongside (never duplicates) the ADR-002
domain event log. Emit :class:`TelemetryEvent`s through a :class:`Recorder` to a
pluggable :class:`Sink`; aggregate with the analytics functions. See
``docs/observability/`` for architecture, schema, dashboards, and integration.
"""

from __future__ import annotations

from telemetry.analytics import (
    ConfidenceSummary,
    EngagementAnalytics,
    QualityAnalytics,
    engagement_analytics,
    quality_analytics,
    summarize_confidence,
)
from telemetry.engagement import EngagementTracer
from telemetry.events import (
    TELEMETRY_SCHEMA_VERSION,
    EventStatus,
    Phase,
    TelemetryEvent,
    ValidationStatus,
)
from telemetry.recorder import Recorder, SpanHandle, default_redactor
from telemetry.sink import JSONLSink, MemorySink, MultiSink, NullSink, Sink

__all__ = [
    # schema
    "TelemetryEvent",
    "Phase",
    "EventStatus",
    "ValidationStatus",
    "TELEMETRY_SCHEMA_VERSION",
    # emission
    "Recorder",
    "SpanHandle",
    "EngagementTracer",
    "default_redactor",
    # sinks
    "Sink",
    "JSONLSink",
    "MemorySink",
    "NullSink",
    "MultiSink",
    # analytics
    "engagement_analytics",
    "quality_analytics",
    "summarize_confidence",
    "EngagementAnalytics",
    "QualityAnalytics",
    "ConfidenceSummary",
]
