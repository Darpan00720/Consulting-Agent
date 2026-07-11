"""Per-engagement telemetry facade (v1.0 Observability — integration).

A thin, ergonomic wrapper the live orchestrator and the ``record_telemetry``
CLI both use so every engagement produces one complete trace. Binds a single
``engagement_id`` to a :class:`Recorder`, and keeps an in-memory mirror so
``analytics()`` works regardless of the durable sink.

This adds no new telemetry concepts — it only removes the per-call boilerplate
of passing ``engagement_id`` and building a sink. Nothing here changes agent or
consulting behaviour.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from telemetry.analytics import EngagementAnalytics, engagement_analytics
from telemetry.events import (
    EventStatus,
    Phase,
    TelemetryEvent,
    ValidationStatus,
)
from telemetry.recorder import Recorder, SpanHandle
from telemetry.sink import JSONLSink, MemorySink, MultiSink, Sink


class EngagementTracer:
    """Records one engagement's telemetry to a durable sink + in-memory mirror."""

    def __init__(
        self,
        engagement_id: str,
        *,
        sink: Sink | None = None,
        root: Path | str = Path("telemetry"),
        sample_rate: float = 1.0,
    ) -> None:
        self._eid = engagement_id
        self._mirror = MemorySink()
        durable: Sink = sink if sink is not None else JSONLSink(root)
        self._recorder = Recorder(
            MultiSink([durable, self._mirror]), sample_rate=sample_rate
        )

    @property
    def engagement_id(self) -> str:
        return self._eid

    @property
    def recorder(self) -> Recorder:
        return self._recorder

    # -- agent spans ---------------------------------------------------------

    @contextmanager
    def agent(self, agent_name: str, phase: Phase) -> Iterator[SpanHandle]:
        """Time one agent dispatch; emits STARTED then FINISHED/FAILED."""
        with self._recorder.span(
            engagement_id=self._eid, agent_name=agent_name, phase=phase
        ) as handle:
            yield handle

    def record(
        self,
        *,
        agent_name: str,
        phase: Phase,
        status: EventStatus,
        duration_ms: float | None = None,
        confidence: float | None = None,
        frameworks_used: Sequence[str] = (),
        tokens: int | None = None,
        retry_count: int = 0,
        validation_status: ValidationStatus | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TelemetryEvent | None:
        """Emit a single event for this engagement (one-shot, no timing)."""
        return self._recorder.emit(
            engagement_id=self._eid,
            agent_name=agent_name,
            phase=phase,
            status=status,
            duration_ms=duration_ms,
            confidence=confidence,
            frameworks_used=frameworks_used,
            tokens=tokens,
            retry_count=retry_count,
            validation_status=validation_status,
            metadata=metadata,
        )

    def rework(
        self,
        *,
        agent_name: str,
        phase: Phase,
        retry_count: int = 1,
        metadata: Mapping[str, Any] | None = None,
    ) -> TelemetryEvent | None:
        """Mark an agent's output as sent back for rework (governance loop)."""
        return self.record(
            agent_name=agent_name,
            phase=phase,
            status=EventStatus.REWORKED,
            retry_count=retry_count,
            metadata=metadata,
        )

    def phase_marker(
        self,
        *,
        phase: Phase,
        status: EventStatus = EventStatus.FINISHED,
        metadata: Mapping[str, Any] | None = None,
    ) -> TelemetryEvent | None:
        """Emit an orchestration-level phase transition marker."""
        return self.record(
            agent_name="orchestrator",
            phase=phase,
            status=status,
            metadata=metadata,
        )

    # -- read-back -----------------------------------------------------------

    def events(self) -> tuple[TelemetryEvent, ...]:
        """All events recorded via this tracer (in emission order)."""
        return self._mirror.events

    def analytics(self) -> EngagementAnalytics:
        """Compute this engagement's analytics from the in-memory mirror."""
        return engagement_analytics(self._mirror.events)

    def close(self) -> None:
        self._recorder.sink.close()
