"""Platform lifecycle management (requirement 4).

Startup / health / ready / shutdown / restart, plus resource cleanup.

Honest scope note: none of the five layers hold a persistent external
connection that needs explicit closing — ``Provider.call()`` (ADR-012)
already creates its HTTP client per call; every W4/W5 adapter is either
stateless or holds only in-memory state. "Resource cleanup" here therefore
means what is REAL to clean up: the in-memory memory cache, and — for
in-flight work — the existing per-execution ``CancellationToken`` mechanism
each Runtime already has (W2/W3/W5); this module does not re-implement that,
it documents it as the correct tool for graceful cancellation and exposes
``shutdown()`` as the point a caller should have already cancelled outstanding
work before calling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.platform.bootstrap import Platform, bootstrap
from app.platform.config import PlatformConfig
from app.platform.health import ComponentState, PlatformHealthReport, aggregate_health


class LifecycleState(StrEnum):
    NOT_STARTED = "not_started"
    STARTING = "starting"
    READY = "ready"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    FAILED = "failed"


class PlatformLifecycle:
    """Owns ONE ``Platform`` instance's lifecycle. Not a singleton — a caller
    constructs one per platform instance it manages (consistent with
    ``bootstrap()``'s "no global mutable state")."""

    def __init__(self, platform: Platform) -> None:
        self.platform = platform
        self.state = LifecycleState.NOT_STARTED
        self._last_health: PlatformHealthReport | None = None

    async def start(self) -> LifecycleState:
        """Transition NOT_STARTED -> STARTING -> READY/DEGRADED/FAILED.
        ``bootstrap()`` already did the heavy construction; ``start()``'s job
        is the async warm-up health pass and the state transition."""
        self.state = LifecycleState.STARTING
        try:
            report = await aggregate_health(self.platform)
        except Exception:  # noqa: BLE001 — a health-check crash means FAILED, not a raised exception
            self.state = LifecycleState.FAILED
            return self.state
        self._last_health = report
        if report.overall_state is ComponentState.UNAVAILABLE:
            self.state = LifecycleState.FAILED
        elif report.degraded:
            self.state = LifecycleState.DEGRADED
        else:
            self.state = LifecycleState.READY
        return self.state

    async def health(self) -> PlatformHealthReport:
        self._last_health = await aggregate_health(self.platform)
        return self._last_health

    async def ready(self) -> bool:
        return self.state in (LifecycleState.READY, LifecycleState.DEGRADED)

    async def shutdown(self) -> None:
        """Graceful shutdown (requirement 4). Clears what is genuinely
        reclaimable (the memory cache); does not — cannot, honestly — force-
        cancel in-flight work it was never given a handle to. A caller
        managing in-flight executions should cancel their own
        ``CancellationToken``s (W2/W3/W5) before calling this."""
        self.state = LifecycleState.SHUTTING_DOWN
        self.platform.memory_service.cache.clear()
        self.state = LifecycleState.STOPPED

    async def restart(self, config: PlatformConfig | None = None) -> Platform:
        """Shutdown, then bootstrap a FRESH platform (requirement 4). Returns
        the new ``Platform`` — the caller must use the returned object; this
        method does not mutate ``self.platform`` in place (immutability)."""
        await self.shutdown()
        new_platform = bootstrap(config or self.platform.config)
        self.platform = new_platform
        self.state = LifecycleState.NOT_STARTED
        await self.start()
        return new_platform


@dataclass(frozen=True)
class LifecycleEvent:
    state: LifecycleState
    detail: str = ""


@dataclass
class LifecycleHistory:
    """Optional: a caller can record transitions for audit/debugging. Not
    auto-attached to ``PlatformLifecycle`` (keeps the core class simple);
    compose it explicitly if needed."""

    events: list[LifecycleEvent] = field(default_factory=list)

    def record(self, state: LifecycleState, detail: str = "") -> None:
        self.events.append(LifecycleEvent(state, detail))
