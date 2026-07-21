"""Operational validation (requirement 8) — run BEFORE startup completes.

Validates configuration, registry contents, required-provider presence,
provider-chain sanity, capability consistency, and version compatibility.
Reports every issue found (not just the first) so an operator sees the whole
picture in one pass, exactly as requirement 8 asks.

Honest scope note on "dependency graph" / "startup sequence" validation:
this is a COMPOSITION-only phase over five already-built layers, not a
static import-graph analyzer. "Dependency graph valid" here means each
layer's registry/runtime was constructed successfully, in the declared
order, with its own dependencies (if any) already available — the practical,
structural form of that check ``bootstrap()`` can actually perform, not an
exhaustive graph-theoretic one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.registry import AgentRegistry
    from app.memory.registry import MemoryRegistry
    from app.pipeline.providers import Provider
    from app.platform.config import PlatformConfig
    from app.tools.registry import ToolRegistry
    from app.workflow.targets import Target

PLATFORM_VERSION = "1.0.0"


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    component: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")

    @property
    def has_blocking_issues(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_valid(self) -> bool:
        return not self.has_blocking_issues


def validate_platform(
    *,
    config: PlatformConfig,
    workflow_registry: dict[str, Target],
    agent_registry: AgentRegistry,
    memory_registry: MemoryRegistry,
    tool_registry: ToolRegistry,
    provider_chain: list[Provider],
) -> ValidationReport:
    """Run every validation category (requirement 8) and return ALL issues —
    never stops at the first one."""
    issues: list[ValidationIssue] = []
    issues += _validate_config(config)
    issues += _validate_registries_nonempty(
        workflow_registry, agent_registry, memory_registry, tool_registry
    )
    issues += _validate_no_duplicate_ids(agent_registry, memory_registry, tool_registry)
    issues += _validate_required_providers(memory_registry, tool_registry)
    issues += _validate_provider_chain(provider_chain, config)
    issues += _validate_capability_consistency(agent_registry, workflow_registry)
    issues += _validate_version_compatibility(
        agent_registry, memory_registry, tool_registry
    )
    return ValidationReport(tuple(issues))


def _validate_config(config: PlatformConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if config.environment not in ("development", "production", "test"):
        issues.append(
            ValidationIssue(
                "warning", "config", f"unrecognized environment '{config.environment}'"
            )
        )
    if config.memory_cache_ttl_s <= 0:
        issues.append(
            ValidationIssue("error", "config", "memory_cache_ttl_s must be positive")
        )
    if config.environment == "production" and config.local_shell_allowed_commands:
        issues.append(
            ValidationIssue(
                "warning",
                "config",
                "local shell commands are allow-listed in a production environment — "
                "confirm this is intentional",
            )
        )
    return issues


def _validate_registries_nonempty(
    workflow_registry: dict[str, Target],
    agent_registry: AgentRegistry,
    memory_registry: MemoryRegistry,
    tool_registry: ToolRegistry,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not workflow_registry:
        issues.append(
            ValidationIssue("error", "workflow_router", "target registry is empty")
        )
    if not agent_registry.discover():
        issues.append(
            ValidationIssue("error", "agent_runtime", "agent registry is empty")
        )
    if not memory_registry.discover():
        issues.append(
            ValidationIssue("error", "memory_platform", "memory registry is empty")
        )
    if not tool_registry.discover():
        issues.append(
            ValidationIssue("error", "tool_platform", "tool registry is empty")
        )
    return issues


def _validate_no_duplicate_ids(
    agent_registry: AgentRegistry,
    memory_registry: MemoryRegistry,
    tool_registry: ToolRegistry,
) -> list[ValidationIssue]:
    """Each registry already REJECTS duplicate registration at ``register()``
    time (W3/W4/W5) — this re-confirms the structural invariant holds
    (``discover()`` never returns a duplicate id), catching the case where a
    future registry implementation regresses that guarantee silently."""
    issues: list[ValidationIssue] = []
    for name, registry in (
        ("agent_runtime", agent_registry),
        ("memory_platform", memory_registry),
        ("tool_platform", tool_registry),
    ):
        ids = [item.id for item in registry.discover()]
        if len(ids) != len(set(ids)):
            issues.append(
                ValidationIssue(
                    "error", name, f"duplicate ids found in {name} registry"
                )
            )
    return issues


def _validate_required_providers(
    memory_registry: MemoryRegistry, tool_registry: ToolRegistry
) -> list[ValidationIssue]:
    """The platform's DEFAULT provider for memory is ``checkpoint`` — its
    absence would silently change every unqualified memory call's resolution
    target, so its presence is validated explicitly."""
    issues: list[ValidationIssue] = []
    if memory_registry.default_provider() is None:
        issues.append(
            ValidationIssue(
                "error", "memory_platform", "no default memory provider registered"
            )
        )
    if tool_registry.get("obsidian") is None:
        issues.append(
            ValidationIssue(
                "warning",
                "tool_platform",
                "obsidian knowledge-sync tool not registered",
            )
        )
    return issues


def _validate_provider_chain(
    provider_chain: list[Provider], config: PlatformConfig
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not provider_chain and not config.ollama_enabled:
        issues.append(
            ValidationIssue(
                "warning",
                "provider_router",
                "no LLM provider configured (chain empty, Ollama disabled) — "
                "fine for validation-only runs, fatal for live execution",
            )
        )
    return issues


#  Targets that delegate their default (no-runner-override) invoke() to a
# same-id Agent Platform agent, per the wiring `app.agents.builtin` actually
# implements (W3). This is a fact about today's composition, not a structural
# guarantee the Target/Agent Protocols enforce — Target.invoke() delegates via
# a lazy import inside its method body, not an inspectable attribute, so this
# is the honest limit of what a STATIC cross-check can verify without
# executing (and thus redesigning) either layer.
_TARGET_TO_AGENT_BY_CONVENTION = ("claude", "codex", "repository_analysis")


def _validate_capability_consistency(
    agent_registry: AgentRegistry, workflow_registry: dict[str, Target]
) -> list[ValidationIssue]:
    """Cross-check the KNOWN target->agent id convention (see note above) —
    a warning, not an error, since it documents today's wiring rather than
    enforcing a contract the Protocols themselves define."""
    issues: list[ValidationIssue] = []
    agent_ids = {a.id for a in agent_registry.discover()}
    for target_id in _TARGET_TO_AGENT_BY_CONVENTION:
        if target_id in workflow_registry and target_id not in agent_ids:
            issues.append(
                ValidationIssue(
                    "warning",
                    "capability_consistency",
                    f"target '{target_id}' has no same-id agent registered "
                    "(breaks the current Target->Agent delegation convention)",
                )
            )
    return issues


def _validate_version_compatibility(
    agent_registry: AgentRegistry,
    memory_registry: MemoryRegistry,
    tool_registry: ToolRegistry,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for name, registry in (
        ("agent", agent_registry),
        ("memory", memory_registry),
        ("tool", tool_registry),
    ):
        for item in registry.discover():
            meta = item.metadata()
            min_version = getattr(meta, "min_runtime_version", None)
            if min_version and min_version > PLATFORM_VERSION:
                issues.append(
                    ValidationIssue(
                        "error",
                        f"{name}_platform",
                        f"'{item.id}' requires runtime >= {min_version}, "
                        f"platform is {PLATFORM_VERSION}",
                    )
                )
    return issues
