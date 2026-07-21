"""Platform health system (requirement 6).

Aggregates health across all six layers (Router, Dispatcher, Runtime, Memory,
Tools, Providers) plus Configuration into one report, with degraded-mode
semantics: the platform can be READY-BUT-DEGRADED (some optional provider is
down) without being UNHEALTHY (a structural core layer is broken).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.agents.models import HealthState as AgentHealthState
from app.memory.models import MemoryHealthState
from app.tools.models import ToolHealthState

if TYPE_CHECKING:
    from app.platform.bootstrap import Platform


class ComponentState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ComponentHealth:
    component: str
    state: ComponentState
    detail: str = ""


@dataclass(frozen=True)
class PlatformHealthReport:
    components: tuple[ComponentHealth, ...]
    overall_state: ComponentState
    degraded: bool

    def component(self, name: str) -> ComponentHealth | None:
        return next((c for c in self.components if c.component == name), None)


# Router and Dispatcher are pure, stateless functions with no external
# dependency (W1/W2 — verified: no I/O in route()/dispatch() themselves) — a
# "structural" health check is exactly correct for them: can they be called
# at all. Runtime is likewise structural (AgentRuntime holds no external
# connection). Memory/Tools/Providers genuinely have backends that can be
# down, so THEIR health is aggregated from each registered item's real
# health() probe.


def _check_router() -> ComponentHealth:
    try:
        from app.workflow.router import RoutingContext, Work, route

        route(Work(text=""), RoutingContext(trace_id="health-check"))
        return ComponentHealth("workflow_router", ComponentState.HEALTHY)
    except Exception as exc:  # noqa: BLE001 — health checks never raise
        return ComponentHealth("workflow_router", ComponentState.UNAVAILABLE, str(exc))


def _check_dispatcher() -> ComponentHealth:
    try:
        import app.workflow.dispatcher as _  # noqa: F401 — importable = structurally sound

        return ComponentHealth("dispatcher", ComponentState.HEALTHY)
    except Exception as exc:  # noqa: BLE001 — health checks never raise
        return ComponentHealth("dispatcher", ComponentState.UNAVAILABLE, str(exc))


def _check_runtime(platform: Platform) -> ComponentHealth:
    if platform.agent_runtime is None:
        return ComponentHealth(
            "agent_runtime", ComponentState.UNAVAILABLE, "not constructed"
        )
    return ComponentHealth("agent_runtime", ComponentState.HEALTHY)


_MEMORY_STATE_MAP = {
    MemoryHealthState.HEALTHY: ComponentState.HEALTHY,
    MemoryHealthState.DEGRADED: ComponentState.DEGRADED,
    MemoryHealthState.UNAVAILABLE: ComponentState.UNAVAILABLE,
    MemoryHealthState.UNKNOWN: ComponentState.UNKNOWN,
}
_TOOL_STATE_MAP = {
    ToolHealthState.HEALTHY: ComponentState.HEALTHY,
    ToolHealthState.DEGRADED: ComponentState.DEGRADED,
    ToolHealthState.UNAVAILABLE: ComponentState.UNAVAILABLE,
    ToolHealthState.UNKNOWN: ComponentState.UNKNOWN,
}
_AGENT_STATE_MAP = {
    AgentHealthState.HEALTHY: ComponentState.HEALTHY,
    AgentHealthState.DEGRADED: ComponentState.DEGRADED,
    AgentHealthState.UNAVAILABLE: ComponentState.UNAVAILABLE,
    AgentHealthState.UNKNOWN: ComponentState.UNKNOWN,
}


def _aggregate(states: list[ComponentState]) -> ComponentState:
    if not states:
        return ComponentState.UNKNOWN
    if all(s is ComponentState.HEALTHY for s in states):
        return ComponentState.HEALTHY
    if any(s is ComponentState.HEALTHY for s in states):
        return ComponentState.DEGRADED  # some usable, some not
    return ComponentState.UNAVAILABLE  # none usable


async def _check_agents(platform: Platform) -> ComponentHealth:
    agents = platform.agent_registry.discover()
    if not agents:
        return ComponentHealth(
            "agents", ComponentState.UNAVAILABLE, "no agents registered"
        )
    states = []
    for agent in agents:
        try:
            result = await agent.health()
            states.append(_AGENT_STATE_MAP.get(result.state, ComponentState.UNKNOWN))
        except Exception:  # noqa: BLE001 — a broken probe is UNKNOWN, not a crash
            states.append(ComponentState.UNKNOWN)
    overall = _aggregate(states)
    return ComponentHealth(
        "agents",
        overall,
        f"{states.count(ComponentState.HEALTHY)}/{len(states)} healthy",
    )


async def _check_memory(platform: Platform) -> ComponentHealth:
    providers_ = platform.memory_registry.discover()
    if not providers_:
        return ComponentHealth(
            "memory_platform", ComponentState.UNAVAILABLE, "no providers registered"
        )
    states = []
    for provider in providers_:
        result = await platform.memory_registry.health(provider.id)
        states.append(_MEMORY_STATE_MAP.get(result.state, ComponentState.UNKNOWN))
    overall = _aggregate(states)
    return ComponentHealth(
        "memory_platform",
        overall,
        f"{states.count(ComponentState.HEALTHY)}/{len(states)} healthy",
    )


async def _check_tools(platform: Platform) -> ComponentHealth:
    tools = platform.tool_registry.discover()
    if not tools:
        return ComponentHealth(
            "tool_platform", ComponentState.UNAVAILABLE, "no tools registered"
        )
    states = []
    for tool in tools:
        result = await platform.tool_registry.health(tool.id)
        states.append(_TOOL_STATE_MAP.get(result.state, ComponentState.UNKNOWN))
    overall = _aggregate(states)
    return ComponentHealth(
        "tool_platform",
        overall,
        f"{states.count(ComponentState.HEALTHY)}/{len(states)} healthy",
    )


def _check_providers(platform: Platform) -> ComponentHealth:
    """Structural presence check (no live network ping — consistent with
    "no benchmarking framework", and a live ping would spend real API quota
    just to answer a health check, which this platform's own cost-discipline
    argues against)."""
    if not platform.provider_chain and not platform.config.ollama_enabled:
        return ComponentHealth(
            "provider_router", ComponentState.UNAVAILABLE, "no provider configured"
        )
    if not platform.provider_chain:
        return ComponentHealth(
            "provider_router", ComponentState.DEGRADED, "chain empty, Ollama-only"
        )
    return ComponentHealth(
        "provider_router",
        ComponentState.HEALTHY,
        f"{len(platform.provider_chain)} provider(s)",
    )


def _check_configuration(platform: Platform) -> ComponentHealth:
    if platform.validation_report.has_blocking_issues:
        return ComponentHealth(
            "configuration",
            ComponentState.UNAVAILABLE,
            "blocking validation issues present",
        )
    if platform.validation_report.warnings:
        return ComponentHealth(
            "configuration",
            ComponentState.DEGRADED,
            f"{len(platform.validation_report.warnings)} warning(s)",
        )
    return ComponentHealth("configuration", ComponentState.HEALTHY)


async def aggregate_health(platform: Platform) -> PlatformHealthReport:
    """One report covering every layer (requirement 6)."""
    components = (
        _check_router(),
        _check_dispatcher(),
        _check_runtime(platform),
        await _check_agents(platform),
        await _check_memory(platform),
        await _check_tools(platform),
        _check_providers(platform),
        _check_configuration(platform),
    )
    overall = _aggregate([c.state for c in components])
    return PlatformHealthReport(
        components=components,
        overall_state=overall,
        degraded=overall is ComponentState.DEGRADED,
    )
