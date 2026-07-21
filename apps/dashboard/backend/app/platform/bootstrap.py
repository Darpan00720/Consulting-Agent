"""Platform Bootstrap (requirement 1) — the single initialization entry point.

``bootstrap()`` is the ONLY place all five layers are constructed and wired
together. It does not redesign any layer: every component is built via that
layer's OWN existing public factory —

    targets.default_registry()        (W1's Workflow Router target roster)
    builtin.default_agent_registry()  (W3's Agent Platform)
    AgentRuntime()                    (W3)
    memory_adapters.default_memory_registry()  (W4)
    MemoryService(registry)           (W4)
    tool_adapters.default_tool_registry()      (W5)
    ToolRuntime()                     (W5)
    providers.build_chain()           (ADR-012 Provider Router)

**Dependency injection (requirement 3):** each component is constructed
explicitly here and passed to whatever needs it — no service reaches for
another's process-global singleton (``app.agents.runtime.default_runtime()``,
``app.memory.service.default_service()``, ``app.tools.runtime.
default_runtime()``) internally. Those singletons still exist, UNCHANGED, as
each layer's own backward-compatible fallback for code that predates
``bootstrap()`` (e.g. ``app.agents.builtin``'s lazy internal calls) — this
phase adds a composition root, it does not remove the layers' existing
defaults, which would be redesigning them.

**No global mutable state (requirement 1):** ``bootstrap()`` returns a NEW
``Platform`` object every call. There is no module-level ``_platform``
singleton here — each of the five factories above is itself side-effect-free
construction (verified in W3/W4/W5: each builds fresh instances), so calling
``bootstrap()`` twice yields two fully independent platforms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.agents.builtin import default_agent_registry
from app.agents.registry import AgentRegistry
from app.agents.runtime import AgentRuntime
from app.memory.adapters import default_memory_registry
from app.memory.registry import MemoryRegistry
from app.memory.service import MemoryService
from app.pipeline import providers
from app.pipeline.providers import Provider
from app.platform.config import PlatformConfig
from app.platform.validation import ValidationReport, validate_platform
from app.tools.adapters import default_tool_registry
from app.tools.registry import ToolRegistry
from app.tools.runtime import ToolRuntime
from app.workflow import targets
from app.workflow.targets import Target


class PlatformBootstrapError(Exception):
    """Startup validation found blocking issues (requirement 8) — the
    platform is NOT returned; the caller sees exactly what failed."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        errors = "; ".join(f"[{i.component}] {i.message}" for i in report.errors)
        super().__init__(f"platform validation failed: {errors}")


@dataclass(frozen=True)
class Platform:
    """The fully composed platform. Immutable after ``bootstrap()`` returns —
    every field is either itself immutable (``PlatformConfig``,
    ``ValidationReport``) or a registry/runtime object whose own public
    surface is the only sanctioned way to interact with it (no field is ever
    reassigned post-construction)."""

    config: PlatformConfig
    workflow_registry: dict[str, Target]
    agent_registry: AgentRegistry
    agent_runtime: AgentRuntime
    memory_registry: MemoryRegistry
    memory_service: MemoryService
    tool_registry: ToolRegistry
    tool_runtime: ToolRuntime
    provider_chain: list[Provider]
    validation_report: ValidationReport
    started_at: float
    startup_duration_ms: float


def bootstrap(
    config: PlatformConfig | None = None,
    *,
    strict: bool = True,
) -> Platform:
    """Construct and wire every platform layer (requirement 1).

    Startup ordering (requirement 8's "startup sequence"): config is
    validated FIRST (nothing downstream is built on invalid config), then
    each layer's registry is constructed independently (none depends on
    another to construct — a real structural fact, not an assumption: each
    ``default_*_registry()``/``build_chain()`` factory takes no arguments from
    another layer), THEN the composed platform is cross-validated as a whole.

    ``strict=True`` (default) raises ``PlatformBootstrapError`` on any
    blocking (error-severity) validation issue — startup does not complete
    with a broken platform. ``strict=False`` returns the ``Platform`` anyway
    with the issues recorded in ``validation_report`` (useful for diagnostics
    tooling that wants to inspect a broken configuration rather than have it
    raise).
    """
    start = time.monotonic()
    cfg = config or PlatformConfig.from_env()

    # Startup ordering: each registry built independently, in a fixed order
    # for reproducibility (not because one depends on another's OUTPUT).
    workflow_registry = targets.default_registry()
    agent_registry = default_agent_registry()
    agent_runtime = AgentRuntime()

    memory_registry = default_memory_registry()
    memory_service = MemoryService(memory_registry)

    tool_registry = default_tool_registry()
    tool_runtime = ToolRuntime()

    provider_chain = providers.build_chain()

    report = validate_platform(
        config=cfg,
        workflow_registry=workflow_registry,
        agent_registry=agent_registry,
        memory_registry=memory_registry,
        tool_registry=tool_registry,
        provider_chain=provider_chain,
    )
    if strict and report.has_blocking_issues:
        raise PlatformBootstrapError(report)

    return Platform(
        config=cfg,
        workflow_registry=workflow_registry,
        agent_registry=agent_registry,
        agent_runtime=agent_runtime,
        memory_registry=memory_registry,
        memory_service=memory_service,
        tool_registry=tool_registry,
        tool_runtime=tool_runtime,
        provider_chain=provider_chain,
        validation_report=report,
        started_at=time.time(),
        startup_duration_ms=(time.monotonic() - start) * 1000,
    )
