"""Tests for the built-in agents (ADR-013 W3, requirement 12) and forward
compatibility with future/plugin agents (requirement 9/13).

Verifies the four converted agents (Claude, Codex, Consulting, Repository
Analysis) satisfy the Agent contract with sane, honest metadata, and proves —
concretely, not by assertion alone — that a completely novel third-party-style
agent can be registered, discovered, and executed with ZERO changes to
registry.py, runtime.py, or any built-in agent (the "plugin-friendly design"
and "future compatibility" requirements, demonstrated rather than stubbed).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.agents.agent import Agent
from app.agents.builtin import (
    claude_agent,
    codex_agent,
    consulting_agent,
    default_agent_registry,
    repository_analysis_agent,
)
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
from app.agents.runtime import AgentRuntime
from app.workflow.router import RoutingContext, Work
from app.workflow.targets import WorkflowCategory as C


def _run(coro):
    return asyncio.run(coro)


def _ctx(category=None):
    return RoutingContext(trace_id="t-1", category=category, classified=True)


# ---- The four built-in agents satisfy the Agent contract ------------------


def test_all_builtin_agents_satisfy_the_agent_protocol():
    for factory in (
        claude_agent,
        codex_agent,
        consulting_agent,
        repository_analysis_agent,
    ):
        assert isinstance(factory(), Agent)


def test_builtin_agent_ids_are_stable():
    assert claude_agent().id == "claude"
    assert codex_agent().id == "codex"
    assert consulting_agent().id == "consulting"
    assert repository_analysis_agent().id == "repository_analysis"


# ---- Metadata validation (requirement 8) -----------------------------------


def test_every_builtin_agent_has_valid_metadata():
    for factory in (
        claude_agent,
        codex_agent,
        consulting_agent,
        repository_analysis_agent,
    ):
        meta = factory().metadata()
        assert isinstance(meta, AgentMetadata)
        assert meta.version  # non-empty
        assert meta.author  # non-empty
        assert meta.min_runtime_version


def test_repository_analysis_metadata_declares_graphify_as_required_mcp():
    """Graphify is a REQUIRED TOOL/MCP for this agent, never an agent itself (F4)."""
    meta = repository_analysis_agent().metadata()
    assert "graphify" in meta.required_mcps


def test_codex_metadata_declares_its_cli_dependency():
    meta = codex_agent().metadata()
    assert "codex-cli" in meta.required_tools


def test_claude_metadata_declares_the_provider_chain_symbolically():
    """Not enumerated by provider name — avoids duplicating build_chain()'s own
    list (drift risk already flagged in ADR-012's risk register)."""
    meta = claude_agent().metadata()
    assert meta.supported_providers == ("provider-router-chain",)


# ---- Capabilities / supported_workflows mirror W2's Targets exactly -------


def test_claude_supports_every_engineering_category_and_general_reasoning():
    agent = claude_agent()
    assert set(agent.supported_workflows) == {
        C.CODING,
        C.DEBUGGING,
        C.CODE_REVIEW,
        C.DOCUMENTATION,
        C.REPOSITORY_ANALYSIS,
        C.RESEARCH,
        C.GENERAL_REASONING,
    }
    assert C.BUSINESS_CONSULTING not in agent.supported_workflows  # governed elsewhere


def test_consulting_supports_only_business_consulting():
    assert consulting_agent().supported_workflows == (C.BUSINESS_CONSULTING,)


def test_repository_analysis_supports_only_repository_analysis():
    assert repository_analysis_agent().supported_workflows == (C.REPOSITORY_ANALYSIS,)


def test_codex_declares_coding_and_evaluation_capabilities():
    assert Capability.CODING in codex_agent().capabilities
    assert Capability.EVALUATION in codex_agent().capabilities


# ---- Health ------------------------------------------------------------------


def test_builtin_agents_report_healthy_when_available():
    for factory in (
        claude_agent,
        codex_agent,
        consulting_agent,
        repository_analysis_agent,
    ):
        result = _run(factory(available=True).health())
        assert result.state is HealthState.HEALTHY


def test_builtin_agents_report_unavailable_when_flagged_down():
    for factory in (codex_agent, consulting_agent, repository_analysis_agent):
        result = _run(factory(available=False).health())
        assert result.state is HealthState.UNAVAILABLE


# ---- default_agent_registry() ----------------------------------------------


def test_default_agent_registry_contains_all_four_ready():
    reg = default_agent_registry()
    assert {a.id for a in reg.discover()} == {
        "claude",
        "codex",
        "consulting",
        "repository_analysis",
    }
    for agent_id in ("claude", "codex", "consulting", "repository_analysis"):
        assert reg.state_of(agent_id) is AgentState.READY


def test_default_agent_registry_capability_search():
    reg = default_agent_registry()
    consulting_agents = reg.find_by_capability(Capability.CONSULTING)
    assert [a.id for a in consulting_agents] == ["consulting"]


# ---- Behavior preservation (requirement 12: "no behavioral changes") ------


def test_codex_default_execute_matches_w2_placeholder_shape():
    result = _run(
        codex_agent().execute(
            AgentRequest(work=Work(text="refactor x"), context=_ExecCtx())
        )
    )
    assert result.success is True
    assert "codex" in result.output.lower()


def test_consulting_default_execute_matches_w2_placeholder_shape():
    result = _run(
        consulting_agent().execute(
            AgentRequest(work=Work(text="pricing"), context=_ExecCtx())
        )
    )
    assert "solve-case" in result.output.lower()


def test_repository_analysis_default_execute_mentions_graphify():
    result = _run(
        repository_analysis_agent().execute(
            AgentRequest(work=Work(text="what calls this"), context=_ExecCtx())
        )
    )
    assert "graphify" in result.output.lower()


def test_codex_runner_override_still_works():
    async def fake_runner(request: AgentRequest) -> AgentResponse:
        return AgentResponse(success=False, error="quota exceeded")

    agent = codex_agent(runner=fake_runner)
    result = _run(agent.execute(AgentRequest(work=Work(text="x"), context=_ExecCtx())))
    assert result.success is False
    assert "quota" in result.error


def _ExecCtx():
    from app.agents.models import ExecutionContext

    return ExecutionContext(
        trace_id="t-1",
        workflow=None,
        routing_context=_ctx(),
        caller="test",
        started_at=0.0,
        correlation_id="t-1",
    )


# ---- Plugin registration / dynamic discovery (requirement 9/13) -----------
#
# A completely NOVEL agent — modeling a future integration (Gemini, Kimi,
# OpenAI Responses API, Deep Research, CrewAI, ...) — registers, is
# discovered, and executes with ZERO changes anywhere in the platform. This is
# the concrete proof, not just an architectural claim.


@dataclass
class PluginAgent:
    """A stand-in for a hypothetical future agent this package has NEVER seen."""

    id: str = "future-plugin"
    name: str = "Future Plugin"
    version: str = "0.1.0"
    description: str = "A hypothetical third-party agent (e.g. Gemini, CrewAI)."
    owner: str = "third-party"
    calls: list = field(default_factory=list)

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        return (Capability.RESEARCH, Capability.EVALUATION)

    @property
    def supported_workflows(self) -> tuple[C, ...]:
        return (C.RESEARCH,)

    async def health(self) -> HealthResult:
        return HealthResult(HealthState.HEALTHY)

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(version=self.version, author=self.owner)

    async def execute(self, request: AgentRequest) -> AgentResponse:
        self.calls.append(request)
        return AgentResponse(success=True, output="plugin handled it")


def test_plugin_agent_satisfies_the_protocol_without_subclassing_anything():
    assert isinstance(PluginAgent(), Agent)


def test_plugin_agent_registers_into_the_production_registry():
    reg = default_agent_registry()  # the real, built-in-seeded registry
    reg.register(PluginAgent())
    assert reg.get("future-plugin") is not None
    # the four built-ins are UNCHANGED by the plugin's presence
    assert {a.id for a in reg.discover()} == {
        "claude",
        "codex",
        "consulting",
        "repository_analysis",
        "future-plugin",
    }


def test_plugin_agent_is_dynamically_discoverable_by_capability():
    reg = AgentRegistry()
    reg.register(PluginAgent())
    found = reg.find_by_capability(Capability.RESEARCH)
    assert [a.id for a in found] == ["future-plugin"]


def test_plugin_agent_executes_through_the_unmodified_runtime():
    plugin = PluginAgent()
    runtime = AgentRuntime()  # the SAME AgentRuntime class every builtin uses
    result = _run(
        runtime.execute(plugin, Work(text="investigate x"), _ctx(category=C.RESEARCH))
    )
    assert result.success is True
    assert result.output == "plugin handled it"
    assert result.agent_id == "future-plugin"


def test_plugin_agent_lifecycle_works_through_the_unmodified_registry():
    reg = AgentRegistry()
    reg.register(PluginAgent())
    reg.set_state("future-plugin", AgentState.READY)
    reg.set_state("future-plugin", AgentState.BUSY)
    reg.set_state("future-plugin", AgentState.READY)
    assert reg.state_of("future-plugin") is AgentState.READY
