"""Tests for platform bootstrap / DI / configuration validation (ADR-013 W6,
requirement 1/2/3/8/13).

Covers: bootstrap composition, dependency injection (fresh instances, no
shared singletons), configuration validation, missing providers/tools,
duplicate-registration propagation, and dependency-graph/startup-sequence
validation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.agents.registry import AgentRegistry
from app.memory.registry import MemoryRegistry
from app.platform.bootstrap import Platform, PlatformBootstrapError, bootstrap
from app.platform.config import PlatformConfig
from app.platform.validation import ValidationIssue, ValidationReport, validate_platform
from app.tools.registry import ToolRegistry
from app.workflow import targets

# ---- Bootstrap composition (requirement 1) ---------------------------------


def test_bootstrap_returns_a_platform_object():
    platform = bootstrap(strict=False)
    assert isinstance(platform, Platform)


def test_bootstrap_composes_all_five_layers():
    platform = bootstrap(strict=False)
    assert platform.workflow_registry  # W1
    assert platform.agent_registry.discover()  # W3
    assert platform.memory_registry.discover()  # W4
    assert platform.tool_registry.discover()  # W5
    # provider_chain (ADR-012) may legitimately be empty without API keys —
    # not asserted non-empty here, that's what validation warnings are for.


def test_bootstrap_records_startup_duration():
    platform = bootstrap(strict=False)
    assert platform.startup_duration_ms >= 0
    assert platform.started_at > 0


def test_bootstrap_is_the_only_place_all_layers_are_wired():
    """Structural proof: Platform holds a runtime/service/registry for every
    layer — nothing is left to be separately assembled by the caller."""
    platform = bootstrap(strict=False)
    for field_name in (
        "workflow_registry",
        "agent_registry",
        "agent_runtime",
        "memory_registry",
        "memory_service",
        "tool_registry",
        "tool_runtime",
        "provider_chain",
    ):
        assert hasattr(platform, field_name)


# ---- Dependency injection: no global mutable state (requirement 1/3) ------


def test_bootstrap_returns_independent_platforms_each_call():
    """No process-global Platform singleton — two calls give two fully
    independent object graphs."""
    p1 = bootstrap(strict=False)
    p2 = bootstrap(strict=False)
    assert p1 is not p2
    assert p1.agent_registry is not p2.agent_registry
    assert p1.memory_registry is not p2.memory_registry
    assert p1.tool_registry is not p2.tool_registry
    assert p1.agent_runtime is not p2.agent_runtime


def test_mutating_one_platforms_registry_does_not_affect_another():
    p1 = bootstrap(strict=False)
    p2 = bootstrap(strict=False)
    p1.memory_registry.remove("graphify")
    assert p1.memory_registry.get("graphify") is None
    assert p2.memory_registry.get("graphify") is not None  # untouched


def test_platform_is_immutable_dataclass():
    import dataclasses

    platform = bootstrap(strict=False)
    assert dataclasses.is_dataclass(platform)
    try:
        platform.started_at = 0.0  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_no_service_reaches_for_anothers_singleton_during_bootstrap():
    """Bootstrap constructs AgentRuntime()/ToolRuntime()/MemoryService(reg)
    directly — NOT via app.agents.runtime.default_runtime() etc. Proven by:
    resetting every layer's own singleton first, then confirming bootstrap()
    still succeeds and produces runtimes independent of those singletons."""
    from app.agents.runtime import reset_runtime as reset_agent_runtime
    from app.memory.service import reset_service
    from app.tools.runtime import reset_runtime as reset_tool_runtime

    reset_agent_runtime()
    reset_service()
    reset_tool_runtime()

    platform = bootstrap(strict=False)
    from app.agents.runtime import default_runtime as agent_default
    from app.memory.service import default_service
    from app.tools.runtime import default_runtime as tool_default

    assert platform.agent_runtime is not agent_default()
    assert platform.memory_service is not default_service()
    assert platform.tool_runtime is not tool_default()


# ---- Configuration (requirement 2) -----------------------------------------


def test_config_from_env_uses_defaults_when_env_empty():
    config = PlatformConfig.from_env(env={})
    assert config.environment == "development"
    assert config.memory_cache_ttl_s == 60.0
    assert config.local_shell_allowed_commands == ()


def test_config_from_env_reads_environment_variables():
    config = PlatformConfig.from_env(
        env={
            "STRATAGENT_ENV": "production",
            "STRATAGENT_MEMORY_CACHE_TTL_S": "120",
            "STRATAGENT_SHELL_ALLOWLIST": "echo,ls",
        }
    )
    assert config.environment == "production"
    assert config.memory_cache_ttl_s == 120.0
    assert config.local_shell_allowed_commands == ("echo", "ls")


def test_config_is_immutable():
    import dataclasses

    config = PlatformConfig.from_env(env={})
    try:
        config.environment = "production"  # type: ignore[misc]
        raise AssertionError("expected FrozenInstanceError")
    except dataclasses.FrozenInstanceError:
        pass


def test_config_overrides_take_precedence():
    config = PlatformConfig.from_env(env={}, overrides={"environment": "test"})
    assert config.environment == "test"


def test_feature_flag_lookup():
    config = replace(PlatformConfig.from_env(env={}), feature_flags={"x": True})
    assert config.feature_enabled("x") is True
    assert config.feature_enabled("y", default=False) is False


# ---- Missing providers / missing tools (requirement 8) ---------------------


def test_validation_flags_empty_memory_registry():
    report = validate_platform(
        config=PlatformConfig.from_env(env={}),
        workflow_registry=targets.default_registry(),
        agent_registry=_agent_registry_with_one(),
        memory_registry=MemoryRegistry(),  # empty — nothing registered
        tool_registry=_tool_registry_with_one(),
        provider_chain=[],
    )
    assert report.has_blocking_issues
    assert any(i.component == "memory_platform" for i in report.errors)


def test_validation_flags_empty_tool_registry():
    report = validate_platform(
        config=PlatformConfig.from_env(env={}),
        workflow_registry=targets.default_registry(),
        agent_registry=_agent_registry_with_one(),
        memory_registry=_memory_registry_with_default(),
        tool_registry=ToolRegistry(),  # empty
        provider_chain=[],
    )
    assert report.has_blocking_issues
    assert any(i.component == "tool_platform" for i in report.errors)


def test_validation_flags_missing_default_memory_provider():
    """A memory registry with entries but NO default provider is invalid —
    every unqualified memory call would silently fail to resolve."""
    reg = MemoryRegistry()

    # Directly poke internal state to simulate a registry with entries but a
    # cleared default (the public API always sets a default on first
    # register(), so this exercises the validator's own defensive check).
    reg.register(_StubMemoryProvider())
    reg._default = None  # noqa: SLF001 — deliberate, testing the validator's guard

    report = validate_platform(
        config=PlatformConfig.from_env(env={}),
        workflow_registry=targets.default_registry(),
        agent_registry=_agent_registry_with_one(),
        memory_registry=reg,
        tool_registry=_tool_registry_with_one(),
        provider_chain=[],
    )
    assert any(
        i.component == "memory_platform" and "default" in i.message
        for i in report.errors
    )


def test_bootstrap_raises_when_strict_and_validation_fails(monkeypatch):
    def _empty_memory_registry():
        return MemoryRegistry()

    monkeypatch.setattr(
        "app.platform.bootstrap.default_memory_registry", _empty_memory_registry
    )
    try:
        bootstrap(strict=True)
        raise AssertionError("expected PlatformBootstrapError")
    except PlatformBootstrapError as exc:
        assert exc.report.has_blocking_issues


def test_bootstrap_does_not_raise_when_not_strict(monkeypatch):
    def _empty_memory_registry():
        return MemoryRegistry()

    monkeypatch.setattr(
        "app.platform.bootstrap.default_memory_registry", _empty_memory_registry
    )
    platform = bootstrap(strict=False)  # must not raise
    assert platform.validation_report.has_blocking_issues


# ---- Duplicate registration propagation (requirement 8/13) ----------------


def test_duplicate_registration_is_still_rejected_through_bootstrap_registries():
    """Bootstrap uses the SAME registries as W3/W4/W5 — their duplicate-
    detection is untouched and still fires."""
    from app.agents.registry import DuplicateAgentError

    platform = bootstrap(strict=False)
    existing = platform.agent_registry.get("claude")
    try:
        platform.agent_registry.register(existing)
        raise AssertionError("expected DuplicateAgentError")
    except DuplicateAgentError:
        pass


# ---- Version compatibility (requirement 8) ---------------------------------


def test_version_compatibility_check_flags_future_requirement():
    from app.agents.models import AgentMetadata, HealthResult, HealthState
    from app.workflow.targets import WorkflowCategory

    @dataclass
    class _FutureAgent:
        id: str = "future"
        name: str = "Future"
        version: str = "1.0.0"
        description: str = "test"
        owner: str = "test"

        @property
        def capabilities(self):
            return ()

        @property
        def supported_workflows(self):
            return (WorkflowCategory.GENERAL_REASONING,)

        async def health(self) -> HealthResult:
            return HealthResult(HealthState.HEALTHY)

        def metadata(self) -> AgentMetadata:
            return AgentMetadata(
                version=self.version, author=self.owner, min_runtime_version="99.0.0"
            )

    reg = AgentRegistry()
    reg.register(_FutureAgent())
    report = validate_platform(
        config=PlatformConfig.from_env(env={}),
        workflow_registry=targets.default_registry(),
        agent_registry=reg,
        memory_registry=_memory_registry_with_default(),
        tool_registry=_tool_registry_with_one(),
        provider_chain=[],
    )
    assert any("requires runtime >=" in i.message for i in report.errors)


# ---- Validation report shape ------------------------------------------------


def test_validation_report_separates_errors_and_warnings():
    report = ValidationReport(
        issues=(
            ValidationIssue("error", "x", "bad"),
            ValidationIssue("warning", "y", "hmm"),
        )
    )
    assert len(report.errors) == 1
    assert len(report.warnings) == 1
    assert report.has_blocking_issues is True
    assert report.is_valid is False


def test_clean_validation_report_is_valid():
    report = ValidationReport(issues=())
    assert report.is_valid is True
    assert report.has_blocking_issues is False


# ---- Real bootstrap validates cleanly end-to-end ---------------------------


def test_real_bootstrap_has_no_blocking_issues():
    """The ACTUAL built-in registries (W3/W4/W5) must validate cleanly — only
    the 'no provider configured' warning is expected in a dev environment
    without API keys."""
    platform = bootstrap(strict=False)
    assert not platform.validation_report.has_blocking_issues


# ---- test fixtures ----------------------------------------------------------


def _agent_registry_with_one() -> AgentRegistry:
    from app.agents.builtin import claude_agent

    reg = AgentRegistry()
    reg.register(claude_agent())
    return reg


def _memory_registry_with_default() -> MemoryRegistry:
    from app.memory.adapters import CheckpointAdapter

    reg = MemoryRegistry()
    reg.register(CheckpointAdapter(), default=True)
    return reg


def _tool_registry_with_one() -> ToolRegistry:
    from app.tools.adapters import ObsidianSyncAdapter

    reg = ToolRegistry()
    reg.register(ObsidianSyncAdapter())
    return reg


@dataclass
class _StubMemoryProvider:
    id: str = "stub"
    name: str = "Stub"
    version: str = "1.0.0"

    def supported_types(self):
        from app.memory.models import MemoryType

        return (MemoryType.KNOWLEDGE,)

    def supported_strategies(self):
        from app.memory.models import RetrievalStrategy

        return (RetrievalStrategy.EXACT,)

    async def store(self, record):
        pass

    async def retrieve(self, key, memory_type=None):
        return None

    async def search(self, query):
        return ()

    async def update(self, key, value, *, memory_type=None):
        pass

    async def delete(self, key, *, memory_type=None):
        pass

    async def exists(self, key, *, memory_type=None):
        return False

    async def health(self):
        from app.memory.models import MemoryHealthResult, MemoryHealthState

        return MemoryHealthResult(MemoryHealthState.HEALTHY)

    def metadata(self):
        from app.memory.models import MemoryType, ProviderMetadata, RetrievalStrategy

        return ProviderMetadata(
            version=self.version,
            author="test",
            supported_types=(MemoryType.KNOWLEDGE,),
            supported_strategies=(RetrievalStrategy.EXACT,),
            backing_system="stub",
        )
