"""Telemetry sinks — pluggable event destinations (v1.0 Observability).

A :class:`Sink` is where emitted events go. Ships three concrete sinks —
append-only JSON Lines (default, matches the repo's file-based persistence
ethos), in-memory (tests / in-process analytics), and null (disabled) — plus a
fan-out. A future OTLP/HTTP exporter implements the same Protocol and drops in
behind the recorder without changing call sites (events already render via
``TelemetryEvent.to_otlp``).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from telemetry.events import TelemetryEvent


@runtime_checkable
class Sink(Protocol):
    """A destination for telemetry events."""

    def emit(self, event: TelemetryEvent) -> None:
        """Record one event. Must not raise for a single bad event (isolate)."""
        ...

    def close(self) -> None:
        """Flush/release resources. Idempotent."""
        ...


class NullSink:
    """Discards everything. Used when telemetry is disabled or a sample is dropped."""

    def emit(self, event: TelemetryEvent) -> None:
        return None

    def close(self) -> None:
        return None


class MemorySink:
    """Keeps events in memory. For tests and in-process analytics."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def close(self) -> None:
        return None

    @property
    def events(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)


class JSONLSink:
    """Append-only JSON Lines sink, one file per engagement.

    Writes ``<root>/<engagement_id>.jsonl``; each line is one event. Append-only
    (never rewrites history), mirroring the persistence layer's event-log ethos.
    The filename uses only ``engagement_id`` — no user-supplied text — so no
    sensitive data lands in a path.
    """

    def __init__(self, root: Path | str = Path("telemetry")) -> None:
        self._root = Path(root)

    def _path(self, engagement_id: str) -> Path:
        # engagement_id is a system id; guard against path escapes defensively.
        safe = engagement_id.replace("/", "_").replace("..", "_")
        return self._root / f"{safe}.jsonl"

    def emit(self, event: TelemetryEvent) -> None:
        path = self._path(event.engagement_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")

    def close(self) -> None:
        return None

    def read(self, engagement_id: str) -> list[TelemetryEvent]:
        """Load all events for one engagement (analytics convenience)."""
        path = self._path(engagement_id)
        if not path.is_file():
            return []
        out: list[TelemetryEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(TelemetryEvent.model_validate_json(line))
        return out

    def read_all(self) -> Iterator[TelemetryEvent]:
        """Iterate events across all engagements under the root (chronological
        within each file)."""
        if not self._root.is_dir():
            return
        for path in sorted(self._root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    yield TelemetryEvent.model_validate_json(line)


class MultiSink:
    """Fan-out to several sinks; one sink failing never blocks the others."""

    def __init__(self, sinks: Iterable[Sink]) -> None:
        self._sinks = tuple(sinks)

    def emit(self, event: TelemetryEvent) -> None:
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception:  # noqa: BLE001 — a sink failure must not break others
                continue

    def close(self) -> None:
        for sink in self._sinks:
            try:
                sink.close()
            except Exception:  # noqa: BLE001
                continue
