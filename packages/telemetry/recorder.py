"""Telemetry recorder — the emission API (v1.0 Observability).

The single entry point call sites use. Wraps a :class:`Sink` and adds:

* ``emit`` — construct + record one :class:`TelemetryEvent`;
* ``span`` — a context manager that times a unit of work and emits a
  ``STARTED`` event on entry and a ``FINISHED`` (or ``FAILED``) event on exit,
  with ``duration_ms`` measured by a monotonic clock;
* **sampling** — drop a fraction of spans (injectable sampler → testable);
* **redaction** — bound/scrub ``metadata`` so no free-form or oversized values
  are persisted (privacy).

Nothing here is wired into agents; the orchestrator and Python components call
it. See ``docs/observability/`` for the integration design.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from random import random
from time import perf_counter
from typing import Any

from telemetry.events import (
    EventStatus,
    Phase,
    TelemetryEvent,
    ValidationStatus,
)
from telemetry.sink import MemorySink, Sink

_MAX_STR = 256
_MAX_META_KEYS = 32


def default_redactor(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Bound metadata to non-sensitive, size-limited scalars/lists.

    Drops keys beginning with ``_`` (convention for raw/internal), truncates
    strings, caps the number of keys, and rejects nested mappings (which could
    smuggle unbounded/sensitive payloads).
    """
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if len(out) >= _MAX_META_KEYS:
            break
        if key.startswith("_"):
            continue
        if isinstance(value, str):
            out[key] = value[:_MAX_STR]
        elif isinstance(value, (int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, (list, tuple)):
            out[key] = [str(v)[:_MAX_STR] for v in list(value)[:20]]
        # nested dicts / other objects are dropped on purpose
    return out


@dataclass
class SpanHandle:
    """Mutable handle a ``span`` body uses to attach signals before finish."""

    confidence: float | None = None
    frameworks_used: tuple[str, ...] = ()
    tokens: int | None = None
    validation_status: ValidationStatus | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def set(
        self,
        *,
        confidence: float | None = None,
        frameworks_used: Sequence[str] | None = None,
        tokens: int | None = None,
        validation_status: ValidationStatus | None = None,
        retry_count: int | None = None,
        **metadata: Any,
    ) -> None:
        if confidence is not None:
            self.confidence = confidence
        if frameworks_used is not None:
            self.frameworks_used = tuple(frameworks_used)
        if tokens is not None:
            self.tokens = tokens
        if validation_status is not None:
            self.validation_status = validation_status
        if retry_count is not None:
            self.retry_count = retry_count
        self.metadata.update(metadata)


class Recorder:
    """Records telemetry to a sink, with sampling and redaction."""

    def __init__(
        self,
        sink: Sink | None = None,
        *,
        sample_rate: float = 1.0,
        sampler: Callable[[], float] = random,
        redactor: Callable[[Mapping[str, Any]], dict[str, Any]] = default_redactor,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("sample_rate must be in [0.0, 1.0]")
        self._sink: Sink = sink if sink is not None else MemorySink()
        self._sample_rate = sample_rate
        self._sampler = sampler
        self._redactor = redactor
        self._clock = clock

    @property
    def sink(self) -> Sink:
        return self._sink

    def _sampled_in(self) -> bool:
        if self._sample_rate >= 1.0:
            return True
        if self._sample_rate <= 0.0:
            return False
        return self._sampler() < self._sample_rate

    def emit(
        self,
        *,
        engagement_id: str,
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
        """Construct and record one event. Returns it, or ``None`` if sampled out."""
        if not self._sampled_in():
            return None
        event = TelemetryEvent(
            engagement_id=engagement_id,
            agent_name=agent_name,
            phase=phase,
            status=status,
            duration_ms=duration_ms,
            confidence=confidence,
            frameworks_used=tuple(frameworks_used),
            tokens=tokens,
            retry_count=retry_count,
            validation_status=validation_status,
            metadata=self._redactor(metadata or {}),
        )
        self._sink.emit(event)
        return event

    @contextmanager
    def span(
        self,
        *,
        engagement_id: str,
        agent_name: str,
        phase: Phase,
        emit_start: bool = True,
    ) -> Iterator[SpanHandle]:
        """Time a unit of work; emit STARTED on entry, FINISHED/FAILED on exit.

        The body may attach signals to the yielded :class:`SpanHandle`; they are
        included on the terminal event.
        """
        handle = SpanHandle()
        sampled = self._sampled_in()
        if sampled and emit_start:
            self._emit_raw(
                engagement_id, agent_name, phase, EventStatus.STARTED, handle, None
            )
        start = self._clock()
        status = EventStatus.FINISHED
        try:
            yield handle
        except Exception:
            status = EventStatus.FAILED
            raise
        finally:
            if sampled:
                duration_ms = (self._clock() - start) * 1000.0
                self._emit_raw(
                    engagement_id, agent_name, phase, status, handle, duration_ms
                )

    def _emit_raw(
        self,
        engagement_id: str,
        agent_name: str,
        phase: Phase,
        status: EventStatus,
        handle: SpanHandle,
        duration_ms: float | None,
    ) -> None:
        event = TelemetryEvent(
            engagement_id=engagement_id,
            agent_name=agent_name,
            phase=phase,
            status=status,
            duration_ms=duration_ms,
            confidence=handle.confidence,
            frameworks_used=handle.frameworks_used,
            tokens=handle.tokens,
            retry_count=handle.retry_count,
            validation_status=handle.validation_status,
            metadata=self._redactor(handle.metadata),
        )
        self._sink.emit(event)
