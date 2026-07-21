"""Tests for the Tool Registry (ADR-013 W5, requirement 2).

Registration, duplicate detection, removal, lookup, discovery, capability
search, health, and version lookup.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.tools.models import ToolHealthResult, ToolHealthState, ToolMetadata, ToolType
from app.tools.registry import DuplicateToolError, ToolRegistry


@dataclass
class StubTool:
    id: str
    name: str = "Stub"
    version: str = "1.0.0"
    description: str = "test"
    caps: tuple = ("op1",)
    tool_type: ToolType = ToolType.CLI
    health_state: ToolHealthState = ToolHealthState.HEALTHY

    @property
    def capabilities(self):
        return self.caps

    @property
    def type(self):
        return self.tool_type

    async def execute(self, request):
        return None

    async def health(self) -> ToolHealthResult:
        return ToolHealthResult(self.health_state)

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="test",
            tool_type=self.tool_type,
            backing_system="stub",
        )


def _run(coro):
    return asyncio.run(coro)


# ---- Registration -----------------------------------------------------------


def test_register_and_get():
    reg = ToolRegistry()
    reg.register(StubTool(id="a"))
    assert reg.get("a").id == "a"


def test_duplicate_registration_raises():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", version="1.0.0"))
    try:
        reg.register(StubTool(id="a", version="1.0.0"))
        raise AssertionError("expected DuplicateToolError")
    except DuplicateToolError:
        pass


def test_duplicate_registration_allowed_with_replace():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", name="v1"))
    reg.register(StubTool(id="a", name="v2"), replace=True)
    assert reg.get("a").name == "v2"


def test_different_versions_are_not_duplicates():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", version="1.0.0"))
    reg.register(StubTool(id="a", version="2.0.0"))
    assert reg.versions_of("a") == ("1.0.0", "2.0.0")


# ---- Version lookup ---------------------------------------------------------


def test_get_returns_latest_version():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", version="1.0.0"))
    reg.register(StubTool(id="a", version="2.0.0"))
    assert reg.get("a").version == "2.0.0"


def test_get_version_returns_specific_version():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", version="1.0.0"))
    reg.register(StubTool(id="a", version="2.0.0"))
    assert reg.get_version("a", "1.0.0").version == "1.0.0"
    assert reg.get_version("a", "9.9.9") is None


def test_get_unknown_tool_returns_none():
    reg = ToolRegistry()
    assert reg.get("ghost") is None


# ---- Deregistration -----------------------------------------------------


def test_deregister_removes_tool():
    reg = ToolRegistry()
    reg.register(StubTool(id="a"))
    reg.deregister("a")
    assert reg.get("a") is None


def test_deregister_falls_back_to_next_highest_version():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", version="1.0.0"))
    reg.register(StubTool(id="a", version="2.0.0"))
    reg.deregister("a", version="2.0.0")
    assert reg.get("a").version == "1.0.0"


def test_deregister_unknown_tool_is_a_noop():
    reg = ToolRegistry()
    reg.deregister("ghost")  # must not raise


# ---- Discovery / capability search -----------------------------------------


def test_dynamic_discovery_lists_every_registered_tool():
    reg = ToolRegistry()
    reg.register(StubTool(id="a"))
    assert {t.id for t in reg.discover()} == {"a"}
    reg.register(StubTool(id="b"))
    assert {t.id for t in reg.discover()} == {"a", "b"}


def test_capability_search():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", caps=("scan_vault",)))
    reg.register(StubTool(id="b", caps=("query_graph",)))
    found = reg.find_by_capability("scan_vault")
    assert [t.id for t in found] == ["a"]


# ---- Health -------------------------------------------------------------


def test_health_query_through_registry():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", health_state=ToolHealthState.DEGRADED))
    result = _run(reg.health("a"))
    assert result.state is ToolHealthState.DEGRADED


def test_health_probe_exception_is_unavailable_not_a_crash():
    @dataclass
    class BrokenHealthTool(StubTool):
        async def health(self):
            raise RuntimeError("probe boom")

    reg = ToolRegistry()
    reg.register(BrokenHealthTool(id="broken"))
    result = _run(reg.health("broken"))  # must not raise
    assert result.state is ToolHealthState.UNAVAILABLE
    assert "probe boom" in result.detail


def test_health_of_unregistered_tool_is_unknown():
    reg = ToolRegistry()
    result = _run(reg.health("ghost"))
    assert result.state is ToolHealthState.UNKNOWN


def test_last_health_is_cached_after_query():
    reg = ToolRegistry()
    reg.register(StubTool(id="a", health_state=ToolHealthState.HEALTHY))
    assert reg.last_health("a") is None
    _run(reg.health("a"))
    assert reg.last_health("a").state is ToolHealthState.HEALTHY
