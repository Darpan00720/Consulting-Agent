"""Tool Registry (requirement 2).

Registration, deregistration, lookup, discovery, capability search, health
lookup, and version lookup — the platform's tool catalog. Neither the
Dispatcher nor the Runtime ever hardcodes a tool instance; both resolve
through this registry, which is what keeps "add a tool" a pure data operation
(requirement 9: plugin-friendly, no switch/if-else, no Runtime/Dispatcher code
change). Structurally mirrors ``AgentRegistry`` (W3) — same ``(id, version)``
keying, same duplicate-detection discipline.
"""

from __future__ import annotations

import logging

from app.tools.errors import ConfigurationError
from app.tools.models import ToolHealthResult, ToolHealthState
from app.tools.tool import Tool

log = logging.getLogger(__name__)


class DuplicateToolError(ConfigurationError):
    """Registering the same ``(id, version)`` twice without ``replace=True``."""


class UnknownToolError(ConfigurationError):
    """Looked up / removed a tool id/version that was never registered."""


class ToolRegistry:
    """In-process tool catalog. Not a singleton by construction — tests build
    their own; ``adapters.default_tool_registry()`` provides the production
    instance seeded with the seven built-in adapters."""

    def __init__(self) -> None:
        self._by_id_version: dict[tuple[str, str], Tool] = {}
        self._latest: dict[str, str] = {}  # tool id -> latest registered version
        self._last_health: dict[tuple[str, str], ToolHealthResult] = {}

    # ---- registration -------------------------------------------------

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        key = (tool.id, tool.version)
        if key in self._by_id_version and not replace:
            raise DuplicateToolError(
                f"tool '{tool.id}' version '{tool.version}' already registered"
            )
        self._by_id_version[key] = tool
        self._latest[tool.id] = tool.version
        log.debug("tool-registry register id=%s version=%s", tool.id, tool.version)

    def deregister(self, tool_id: str, version: str | None = None) -> None:
        version = version or self._latest.get(tool_id)
        if version is None:
            return
        key = (tool_id, version)
        self._by_id_version.pop(key, None)
        self._last_health.pop(key, None)
        if self._latest.get(tool_id) == version:
            remaining = [v for (i, v) in self._by_id_version if i == tool_id]
            self._latest[tool_id] = sorted(remaining)[-1] if remaining else None
            if self._latest[tool_id] is None:
                self._latest.pop(tool_id, None)
        log.debug("tool-registry deregister id=%s version=%s", tool_id, version)

    # ---- lookup ---------------------------------------------------------

    def get(self, tool_id: str) -> Tool | None:
        """Latest registered version of ``tool_id``, or None."""
        version = self._latest.get(tool_id)
        if version is None:
            return None
        return self._by_id_version.get((tool_id, version))

    def get_version(self, tool_id: str, version: str) -> Tool | None:
        """Version lookup (requirement 2): a SPECIFIC version, not just latest."""
        return self._by_id_version.get((tool_id, version))

    def versions_of(self, tool_id: str) -> tuple[str, ...]:
        return tuple(sorted(v for (i, v) in self._by_id_version if i == tool_id))

    # ---- discovery / capability search ----------------------------------

    def discover(self) -> tuple[Tool, ...]:
        found = (self.get(tool_id) for tool_id in self._latest)
        return tuple(t for t in found if t is not None)

    def find_by_capability(self, capability: str) -> tuple[Tool, ...]:
        return tuple(t for t in self.discover() if capability in t.capabilities)

    # ---- health (requirement 2) -------------------------------------------

    async def health(self, tool_id: str) -> ToolHealthResult:
        tool = self.get(tool_id)
        if tool is None:
            return ToolHealthResult(ToolHealthState.UNKNOWN, detail="not registered")
        try:
            result = await tool.health()
        except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE, not a crash
            result = ToolHealthResult(
                ToolHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
            )
        self._last_health[(tool_id, tool.version)] = result
        return result

    def last_health(
        self, tool_id: str, version: str | None = None
    ) -> ToolHealthResult | None:
        version = version or self._latest.get(tool_id)
        if version is None:
            return None
        return self._last_health.get((tool_id, version))
