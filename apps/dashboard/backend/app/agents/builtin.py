"""Built-in agents (requirement 12): Claude, Codex, Consulting, Repository
Analysis — converted from the ADR-013 W2 ``Target`` implementations into
runtime ``Agent``s.

**No behavioral change.** Claude genuinely calls the Provider Router (ADR-012)
— unchanged from W2's ``ClaudeSessionTarget.invoke``. Codex, the consulting
skill, and Graphify remain deterministic, side-effect-free placeholders behind
an injectable ``runner`` — unchanged from W2's rationale (external CLI/skill/
MCP surfaces this Python backend doesn't own; see ``app.workflow.targets``'
module docstring for the full argument). Only the WRAPPER changed: these are
now registered ``Agent``s executed via ``AgentRuntime``, not ad-hoc logic
inlined in a ``Target.invoke()`` body.

This module DOES import ``app.workflow.targets`` (for ``WorkflowCategory``) at
the top level — safe, not circular: ``app.workflow.targets`` never imports
``app.agents`` at its OWN top level, only lazily inside each ``Target.invoke``
method body (after the module has already finished loading).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.agents.models import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    AgentState,
    Capability,
    HealthResult,
    HealthState,
)
from app.agents.registry import AgentRegistry
from app.workflow.targets import WorkflowCategory

_C = WorkflowCategory
_W = Capability

RunnerFn = Callable[[AgentRequest], Awaitable[AgentResponse]]


@dataclass
class ClaudeAgent:
    """Primary, always-available session agent. ``execute`` is REAL: it calls
    ``providers.call_with_failover`` (ADR-012), the one target this backend can
    genuinely execute end-to-end. ``agent_name`` embeds ``trace_id`` so Provider
    Router telemetry correlates with Agent/Workflow telemetry without a shared
    global or a new id (requirement 10 "no duplicated telemetry")."""

    id: str = "claude"
    name: str = "Claude"
    version: str = "1.0.0"
    description: str = "Primary session agent; the Provider Router's real client."
    owner: str = "StratAgent"
    is_available: bool = True

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return (
            _W.REASONING,
            _W.CODING,
            _W.DOCUMENTATION,
            _W.RESEARCH,
            _W.REPOSITORY_ANALYSIS,
        )

    @property
    def supported_workflows(self) -> tuple[WorkflowCategory, ...]:
        return (
            _C.CODING,
            _C.DEBUGGING,
            _C.CODE_REVIEW,
            _C.DOCUMENTATION,
            _C.REPOSITORY_ANALYSIS,
            _C.RESEARCH,
            _C.GENERAL_REASONING,
        )

    async def health(self) -> HealthResult:
        return HealthResult(
            HealthState.HEALTHY if self.is_available else HealthState.UNAVAILABLE
        )

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            version=self.version,
            author=self.owner,
            # The full ADR-012 chain, not enumerated by name here — avoids
            # duplicating build_chain()'s own provider list (drift risk already
            # flagged in ADR-012's own risk register).
            supported_providers=("provider-router-chain",),
            min_runtime_version="1.0.0",
        )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        from app.pipeline import providers  # lazy: keep agents importable standalone

        try:
            text = await providers.call_with_failover(
                agent_name=f"workflow:{request.context.trace_id}:claude",
                system="You are Claude, handling a routed unit of work.",
                user=request.work.text or "(no text provided)",
                max_tokens=256,
            )
            return AgentResponse(success=True, output=text)
        except Exception as exc:  # noqa: BLE001 — business logic reports; Runtime maps
            return AgentResponse(success=False, error=f"{type(exc).__name__}: {exc}")


async def _default_codex_runner(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        success=True, output=f"[codex placeholder] would run for: {request.work.text!r}"
    )


@dataclass
class CodexAgent:
    """Independent CLI model for mechanical code work + adversarial review.
    Placeholder ``execute`` (module docstring) — override via ``runner``."""

    id: str = "codex"
    name: str = "Codex"
    version: str = "1.0.0"
    description: str = "Mechanical code work and independent adversarial review."
    owner: str = "OpenAI (Codex plugin)"
    is_available: bool = True
    runner: RunnerFn | None = None

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return (_W.CODING, _W.EVALUATION)

    @property
    def supported_workflows(self) -> tuple[WorkflowCategory, ...]:
        return (_C.CODING, _C.DEBUGGING, _C.CODE_REVIEW, _C.DOCUMENTATION)

    async def health(self) -> HealthResult:
        return HealthResult(
            HealthState.HEALTHY if self.is_available else HealthState.UNAVAILABLE
        )

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            version=self.version,
            author=self.owner,
            required_tools=("codex-cli",),
            min_runtime_version="1.0.0",
        )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        run = self.runner or _default_codex_runner
        try:
            return await run(request)
        except Exception as exc:  # noqa: BLE001 — business logic reports; Runtime maps
            return AgentResponse(success=False, error=f"{type(exc).__name__}: {exc}")


async def _default_consulting_runner(request: AgentRequest) -> AgentResponse:
    return AgentResponse(
        success=True,
        output=(
            f"[solve-case placeholder] would run engagement for: {request.work.text!r}"
        ),
    )


@dataclass
class ConsultingAgent:
    """The governed StratAgent ``solve-case`` pipeline — the ONLY agent
    permitted to own business consulting (Workflow Router guardrail, ADR-013
    §6.4/§8; ADR-010 §6c). Placeholder ``execute`` (module docstring) —
    override via ``runner``."""

    id: str = "consulting"
    name: str = "Consulting"
    version: str = "1.0.0"
    description: str = "Governed StratAgent solve-case engagement pipeline."
    owner: str = "StratAgent"
    is_available: bool = True
    runner: RunnerFn | None = None

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return (_W.CONSULTING, _W.STRATEGY)

    @property
    def supported_workflows(self) -> tuple[WorkflowCategory, ...]:
        return (_C.BUSINESS_CONSULTING,)

    async def health(self) -> HealthResult:
        return HealthResult(
            HealthState.HEALTHY if self.is_available else HealthState.UNAVAILABLE
        )

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            version=self.version,
            author=self.owner,
            required_tools=("solve-case",),
            min_runtime_version="1.0.0",
        )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        run = self.runner or _default_consulting_runner
        try:
            return await run(request)
        except Exception as exc:  # noqa: BLE001 — business logic reports; Runtime maps
            return AgentResponse(success=False, error=f"{type(exc).__name__}: {exc}")


async def _default_repository_analysis_runner(request: AgentRequest) -> AgentResponse:
    """Repository Analysis -> Memory Service -> Graphify Adapter (W4
    requirement 8/13). Graphify is STILL never a registry entry or an
    executable agent of its own (F4) — it is reached only as a
    ``MemoryProvider`` behind ``MemoryService.search``, which is exactly what
    "use an adapter" (requirement 8) means concretely. No behavioral change:
    the Memory Platform's ``GraphifyAdapter`` placeholder body produces the
    same '...graphify...' output shape the pre-W4 inline placeholder did.
    """
    from app.memory.models import MemoryQuery, MemoryType
    from app.memory.service import default_service

    result = await default_service().search(
        MemoryQuery(text=request.work.text, memory_type=MemoryType.REPOSITORY),
        provider_id="graphify",
        trace_id=request.context.trace_id,
    )
    if not result.success:
        return AgentResponse(success=False, error=result.error)
    output = (
        str(result.records[0].value)
        if result.records
        else f"[repo-analysis] no graph data for: {request.work.text!r}"
    )
    return AgentResponse(success=True, output=output)


@dataclass
class RepositoryAnalysisAgent:
    """Answers structural questions USING Graphify's graph tools. Graphify is a
    tool this agent holds (``metadata().required_mcps``), not an agent of its
    own (F4). Placeholder ``execute`` (module docstring) — override via
    ``runner``."""

    id: str = "repository_analysis"
    name: str = "Repository Analysis"
    version: str = "1.0.0"
    description: str = "Structural/graph queries over the codebase via Graphify."
    owner: str = "StratAgent"
    is_available: bool = True
    runner: RunnerFn | None = None

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return (_W.REPOSITORY_ANALYSIS,)

    @property
    def supported_workflows(self) -> tuple[WorkflowCategory, ...]:
        return (_C.REPOSITORY_ANALYSIS,)

    async def health(self) -> HealthResult:
        return HealthResult(
            HealthState.HEALTHY if self.is_available else HealthState.UNAVAILABLE
        )

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            version=self.version,
            author=self.owner,
            required_mcps=("graphify",),
            min_runtime_version="1.0.0",
        )

    async def execute(self, request: AgentRequest) -> AgentResponse:
        run = self.runner or _default_repository_analysis_runner
        try:
            return await run(request)
        except Exception as exc:  # noqa: BLE001 — business logic reports; Runtime maps
            return AgentResponse(success=False, error=f"{type(exc).__name__}: {exc}")


def claude_agent(available: bool = True) -> ClaudeAgent:
    return ClaudeAgent(is_available=available)


def codex_agent(available: bool = True, runner: RunnerFn | None = None) -> CodexAgent:
    return CodexAgent(is_available=available, runner=runner)


def consulting_agent(
    available: bool = True, runner: RunnerFn | None = None
) -> ConsultingAgent:
    return ConsultingAgent(is_available=available, runner=runner)


def repository_analysis_agent(
    available: bool = True, runner: RunnerFn | None = None
) -> RepositoryAnalysisAgent:
    return RepositoryAnalysisAgent(is_available=available, runner=runner)


def default_agent_registry() -> AgentRegistry:
    """The production registry, seeded with the four built-in agents, each
    already transitioned REGISTERED → READY (requirement 4's lifecycle, applied
    to the agents this platform ships with)."""
    registry = AgentRegistry()
    for factory in (
        claude_agent,
        codex_agent,
        consulting_agent,
        repository_analysis_agent,
    ):
        agent = factory()
        registry.register(agent)
        registry.set_state(agent.id, AgentState.READY)
    return registry
