"""Tests for platform lifecycle management (ADR-013 W6, requirement 4/6/13).

Startup, health aggregation, ready, shutdown, restart, resource cleanup, and
degraded mode.
"""

from __future__ import annotations

import asyncio

from app.platform.bootstrap import bootstrap
from app.platform.health import ComponentState
from app.platform.lifecycle import LifecycleState, PlatformLifecycle


def _run(coro):
    return asyncio.run(coro)


def _lifecycle() -> PlatformLifecycle:
    return PlatformLifecycle(bootstrap(strict=False))


# ---- Startup ----------------------------------------------------------------


def test_starts_not_started():
    lc = _lifecycle()
    assert lc.state is LifecycleState.NOT_STARTED


def test_start_transitions_to_ready_or_degraded():
    lc = _lifecycle()
    state = _run(lc.start())
    assert state in (LifecycleState.READY, LifecycleState.DEGRADED)


def test_start_in_dev_env_without_provider_keys_is_degraded():
    """No LLM provider configured (typical dev env) -> DEGRADED, not FAILED —
    the platform can still classify/route/store/tool-execute."""
    lc = _lifecycle()
    state = _run(lc.start())
    assert state is LifecycleState.DEGRADED  # provider_router unavailable


# ---- Health aggregation / degraded mode (requirement 6) --------------------


def test_health_report_covers_every_layer():
    lc = _lifecycle()
    report = _run(lc.health())
    names = {c.component for c in report.components}
    assert names == {
        "workflow_router",
        "dispatcher",
        "agent_runtime",
        "agents",
        "memory_platform",
        "tool_platform",
        "provider_router",
        "configuration",
    }


def test_degraded_overall_when_one_optional_layer_is_down():
    lc = _lifecycle()
    report = _run(lc.health())
    provider_health = report.component("provider_router")
    assert provider_health.state is ComponentState.UNAVAILABLE
    # core layers (router/dispatcher/runtime/agents/memory/tools) still healthy
    assert report.component("workflow_router").state is ComponentState.HEALTHY
    assert report.component("agents").state is ComponentState.HEALTHY
    assert report.overall_state is ComponentState.DEGRADED
    assert report.degraded is True


def test_healthy_when_all_components_healthy():
    from app.platform.health import ComponentHealth, PlatformHealthReport, _aggregate

    components = tuple(
        ComponentHealth(f"c{i}", ComponentState.HEALTHY) for i in range(3)
    )
    overall = _aggregate([c.state for c in components])
    report = PlatformHealthReport(
        components, overall, degraded=(overall is ComponentState.DEGRADED)
    )
    assert report.overall_state is ComponentState.HEALTHY
    assert report.degraded is False


def test_unavailable_when_all_components_down():
    from app.platform.health import _aggregate

    states = [ComponentState.UNAVAILABLE, ComponentState.UNAVAILABLE]
    assert _aggregate(states) is ComponentState.UNAVAILABLE


def test_component_lookup_by_name():
    lc = _lifecycle()
    report = _run(lc.health())
    assert report.component("memory_platform") is not None
    assert report.component("ghost-component") is None


# ---- Ready ------------------------------------------------------------------


def test_ready_true_when_degraded_or_ready():
    lc = _lifecycle()
    _run(lc.start())
    assert _run(lc.ready()) is True


def test_ready_false_before_start():
    lc = _lifecycle()
    assert _run(lc.ready()) is False


# ---- Shutdown / resource cleanup (requirement 4) ---------------------------


def test_shutdown_transitions_to_stopped():
    lc = _lifecycle()
    _run(lc.start())
    _run(lc.shutdown())
    assert lc.state is LifecycleState.STOPPED


def test_shutdown_clears_the_memory_cache():
    from app.memory.models import MemoryRecord, MemoryType

    lc = _lifecycle()
    _run(lc.start())
    _run(
        lc.platform.memory_service.store(
            MemoryRecord(
                key="lifecycle::test", value="x", memory_type=MemoryType.EXECUTION
            ),
            trace_id="t",
        )
    )
    _run(
        lc.platform.memory_service.retrieve(
            "lifecycle::test", MemoryType.EXECUTION, trace_id="t"
        )
    )
    assert lc.platform.memory_service.cache.stats().size > 0
    _run(lc.shutdown())
    assert lc.platform.memory_service.cache.stats().size == 0


def test_shutdown_is_idempotent_safe_to_call_twice():
    lc = _lifecycle()
    _run(lc.start())
    _run(lc.shutdown())
    _run(lc.shutdown())  # must not raise
    assert lc.state is LifecycleState.STOPPED


# ---- Restart ------------------------------------------------------------------


def test_restart_produces_a_fresh_platform():
    lc = _lifecycle()
    _run(lc.start())
    original = lc.platform
    new_platform = _run(lc.restart())
    assert new_platform is not original
    assert lc.platform is new_platform
    assert lc.state in (LifecycleState.READY, LifecycleState.DEGRADED)


def test_restart_preserves_config_by_default():
    lc = _lifecycle()
    original_config = lc.platform.config
    _run(lc.start())
    new_platform = _run(lc.restart())
    assert new_platform.config == original_config
