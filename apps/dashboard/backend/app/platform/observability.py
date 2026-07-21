"""Unified observability (requirement 5).

Every layer ALREADY logs one ``key=value ...`` line per operation, reusing
the SAME ``trace_id`` — proven end-to-end in W3/W4/W5:

    app.workflow.router:      "workflow-route trace_id=%s category=%s ..."
    app.workflow.dispatcher:  "dispatch trace_id=%s ... duration_ms=%.1f ..."
    app.agents.runtime:       "agent-execute trace_id=%s ... duration_ms=%.1f ..."
    app.memory.service:       "memory-op trace_id=%s ... duration_ms=%.1f ..."
    app.tools.runtime:        "tool-execute trace_id=%s ... duration_ms=%.1f ..."

Correlation therefore ALREADY EXISTS structurally — no layer's logging is
redesigned here. This module adds a ``logging.Handler`` (a standard, non-
invasive Python extension point) that ATTACHES to those five loggers from
the outside and buffers records per ``trace_id``, giving ``get_trace()``/
``latency_breakdown()`` without touching a single log call site.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

PLATFORM_LOGGERS: tuple[str, ...] = (
    "app.workflow.router",
    "app.workflow.dispatcher",
    "app.agents.runtime",
    "app.memory.service",
    "app.tools.runtime",
)

_FIELD_RE = re.compile(r"(\w+)=(\S+)")


def _parse_fields(message: str) -> dict[str, str]:
    """Parse the ``key=value key2=value2`` shape every platform logger already
    uses (by convention, established across W2-W5) — no per-layer parser."""
    return dict(_FIELD_RE.findall(message))


@dataclass(frozen=True)
class TraceEvent:
    layer: str  # the logger name, e.g. "app.agents.runtime"
    message: str
    duration_ms: float | None
    timestamp: float
    fields: dict[str, str]


class TraceCollector(logging.Handler):
    """Buffers log records by ``trace_id``, extracted from each record's own
    formatted message. A bounded ring of the most recent ``max_traces`` trace
    ids — never grows unbounded."""

    def __init__(self, max_traces: int = 500) -> None:
        super().__init__(level=logging.DEBUG)
        self._traces: dict[str, list[TraceEvent]] = {}
        self._order: list[str] = []
        self.max_traces = max_traces
        self._prior_levels: dict[str, int] = {}

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            fields = _parse_fields(message)
            trace_id = fields.get("trace_id")
            if not trace_id:
                return
            duration = None
            if "duration_ms" in fields:
                try:
                    duration = float(fields["duration_ms"])
                except ValueError:
                    duration = None
            event = TraceEvent(
                layer=record.name,
                message=message,
                duration_ms=duration,
                timestamp=record.created,
                fields=fields,
            )
            bucket = self._traces.setdefault(trace_id, [])
            bucket.append(event)
            if trace_id not in self._order:
                self._order.append(trace_id)
                if len(self._order) > self.max_traces:
                    oldest = self._order.pop(0)
                    self._traces.pop(oldest, None)
        except Exception:  # noqa: BLE001 — a logging handler must never raise
            self.handleError(record)

    def get_trace(self, trace_id: str) -> tuple[TraceEvent, ...]:
        """The ordered sequence of every layer's event for one trace_id —
        end-to-end tracing (requirement 5)."""
        return tuple(self._traces.get(trace_id, ()))

    def latency_breakdown(self, trace_id: str) -> dict[str, float]:
        """Per-layer duration for one trace — the "latency breakdown"
        requirement 5 asks for, derived from data every layer already emits."""
        return {
            e.layer: e.duration_ms
            for e in self.get_trace(trace_id)
            if e.duration_ms is not None
        }

    def layers_touched(self, trace_id: str) -> tuple[str, ...]:
        """Which layers this trace actually passed through — the concrete
        proof of end-to-end correlation (requirement 5's core ask)."""
        return tuple(dict.fromkeys(e.layer for e in self.get_trace(trace_id)))

    def clear(self) -> None:
        self._traces.clear()
        self._order.clear()


def attach_trace_collector(
    loggers: tuple[str, ...] = PLATFORM_LOGGERS, *, max_traces: int = 500
) -> TraceCollector:
    """Attach a fresh ``TraceCollector`` to every platform logger. Returns the
    collector so the caller can detach it later (``detach_trace_collector``)
    — never a hidden global.

    Also lowers each logger's OWN level to DEBUG for the duration. A
    ``logging.Handler``'s level only filters records the LOGGER already
    decided to emit — a logger left at its default WARNING level (the
    ``logging`` module's own default when nothing else configures it) drops
    every ``log.debug(...)`` call in ``app.workflow.router``/etc. before any
    handler — including this one — ever sees it. Each prior level is saved
    and restored by ``detach_trace_collector`` so attaching a collector
    doesn't permanently change the process's logging verbosity.
    """
    collector = TraceCollector(max_traces=max_traces)
    for name in loggers:
        logger = logging.getLogger(name)
        collector._prior_levels[name] = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(collector)
    return collector


def detach_trace_collector(
    collector: TraceCollector, loggers: tuple[str, ...] = PLATFORM_LOGGERS
) -> None:
    for name in loggers:
        logger = logging.getLogger(name)
        logger.removeHandler(collector)
        if name in collector._prior_levels:
            logger.setLevel(collector._prior_levels[name])
