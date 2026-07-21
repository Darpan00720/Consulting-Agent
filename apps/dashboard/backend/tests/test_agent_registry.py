"""Tests for the Agent Registry (ADR-013 W3, requirement 2/4/5).

Registration, duplicate detection, lookup, discovery, capability search,
version lookup, lifecycle transitions (+ illegal-transition rejection), health
changes (+ state reconciliation), and overall registry consistency.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from app.agents.errors import ConfigurationError
from app.agents.models import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    AgentState,
    Capability,
    HealthResult,
    HealthState,
)
from app.agents.registry import (
    AgentRegistry,
    DuplicateAgentError,
    IllegalTransitionError,
    UnknownAgentError,
)
from app.workflow.targets import WorkflowCategory as C


@dataclass
class StubAgent:
    id: str
    version: str = "1.0.0"
    name: str = "Stub"
    description: str = "test stub"
    owner: str = "test"
    caps: tuple[Capability, ...] = (Capability.REASONING,)
    workflows: tuple[C, ...] = (C.GENERAL_REASONING,)
    health_state: HealthState = HealthState.HEALTHY

    @property
    def capabilities(self):
        return self.caps

    @property
    def supported_workflows(self):
        return self.workflows

    async def health(self) -> HealthResult:
        return HealthResult(self.health_state)

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(version=self.version, author=self.owner)

    async def execute(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(success=True, output="stub")


def _run(coro):
    return asyncio.run(coro)


# ---- Registration -----------------------------------------------------------


def test_register_and_get():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    assert reg.get("a").id == "a"


def test_duplicate_registration_raises():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0"))
    try:
        reg.register(StubAgent(id="a", version="1.0.0"))
        raise AssertionError("expected DuplicateAgentError")
    except DuplicateAgentError:
        pass


def test_duplicate_registration_allowed_with_replace():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0", name="v1"))
    reg.register(StubAgent(id="a", version="1.0.0", name="v2"), replace=True)
    assert reg.get("a").name == "v2"


def test_different_versions_are_not_duplicates():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0"))
    reg.register(StubAgent(id="a", version="2.0.0"))  # no error
    assert reg.versions_of("a") == ("1.0.0", "2.0.0")


def test_duplicate_agent_error_is_a_configuration_error():
    assert issubclass(DuplicateAgentError, ConfigurationError)


# ---- Version lookup -----------------------------------------------------


def test_get_returns_latest_registered_version():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0"))
    reg.register(StubAgent(id="a", version="2.0.0"))
    assert reg.get("a").version == "2.0.0"


def test_get_version_returns_a_specific_version():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0"))
    reg.register(StubAgent(id="a", version="2.0.0"))
    assert reg.get_version("a", "1.0.0").version == "1.0.0"
    assert reg.get_version("a", "9.9.9") is None


def test_get_unknown_agent_returns_none():
    reg = AgentRegistry()
    assert reg.get("ghost") is None


# ---- Deregistration -----------------------------------------------------


def test_deregister_removes_agent():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.deregister("a")
    assert reg.get("a") is None


def test_deregister_falls_back_to_next_highest_version():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0"))
    reg.register(StubAgent(id="a", version="2.0.0"))
    reg.deregister("a", version="2.0.0")
    assert reg.get("a").version == "1.0.0"


# ---- Discovery / capability / workflow lookup ---------------------------


def test_dynamic_discovery_lists_every_registered_agent():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.register(StubAgent(id="b"))
    assert {a.id for a in reg.discover()} == {"a", "b"}


def test_capability_based_lookup():
    reg = AgentRegistry()
    reg.register(StubAgent(id="coder", caps=(Capability.CODING,)))
    reg.register(StubAgent(id="researcher", caps=(Capability.RESEARCH,)))
    found = reg.find_by_capability(Capability.CODING)
    assert [a.id for a in found] == ["coder"]


def test_workflow_based_lookup():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", workflows=(C.CODING,)))
    reg.register(StubAgent(id="b", workflows=(C.RESEARCH,)))
    found = reg.find_by_workflow(C.CODING)
    assert [a.id for a in found] == ["a"]


def test_discovery_reflects_deregistration():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.deregister("a")
    assert reg.discover() == ()


# ---- Lifecycle transitions (requirement 4) --------------------------------


def test_new_agent_starts_registered():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    assert reg.state_of("a") is AgentState.REGISTERED


def test_legal_transition_registered_to_ready():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.set_state("a", AgentState.READY)
    assert reg.state_of("a") is AgentState.READY


def test_legal_transition_ready_to_busy_to_ready():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.set_state("a", AgentState.READY)
    reg.set_state("a", AgentState.BUSY)
    reg.set_state("a", AgentState.READY)
    assert reg.state_of("a") is AgentState.READY


def test_temporary_failure_recovers_without_unregistering():
    """Requirement 4: 'support temporary failures without unregistering' —
    FAILED -> READY is the explicit recovery path."""
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.set_state("a", AgentState.READY)
    reg.set_state("a", AgentState.FAILED)
    assert reg.get("a") is not None  # still registered
    reg.set_state("a", AgentState.READY)  # recovers
    assert reg.state_of("a") is AgentState.READY


def test_illegal_transition_is_rejected():
    """STOPPED is terminal — nothing transitions out of it."""
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.set_state("a", AgentState.STOPPED)
    try:
        reg.set_state("a", AgentState.READY)
        raise AssertionError("expected IllegalTransitionError")
    except IllegalTransitionError as exc:
        assert exc.current is AgentState.STOPPED
        assert exc.target is AgentState.READY


def test_illegal_transition_leaves_state_unchanged():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.set_state("a", AgentState.STOPPED)
    with contextlib.suppress(IllegalTransitionError):
        reg.set_state("a", AgentState.BUSY)
    assert reg.state_of("a") is AgentState.STOPPED  # unchanged, consistent


def test_set_state_on_unregistered_agent_raises():
    reg = AgentRegistry()
    try:
        reg.set_state("ghost", AgentState.READY)
        raise AssertionError("expected UnknownAgentError")
    except UnknownAgentError:
        pass


def test_same_state_transition_is_always_legal_idempotent():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a"))
    reg.set_state("a", AgentState.REGISTERED)  # no-op, must not raise
    assert reg.state_of("a") is AgentState.REGISTERED


# ---- Health (requirement 5) + state reconciliation -----------------------


def test_health_query_through_registry():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", health_state=HealthState.HEALTHY))
    result = _run(reg.health("a"))
    assert result.state is HealthState.HEALTHY


def test_health_changes_reconcile_lifecycle_state():
    reg = AgentRegistry()
    agent = StubAgent(id="a", health_state=HealthState.HEALTHY)
    reg.register(agent)
    reg.set_state("a", AgentState.READY)
    _run(reg.health("a"))  # HEALTHY -> stays READY
    assert reg.state_of("a") is AgentState.READY

    agent.health_state = HealthState.UNAVAILABLE
    _run(reg.health("a"))
    assert reg.state_of("a") is AgentState.FAILED  # reconciled from health


def test_health_reconciliation_never_resurrects_disabled_agent():
    reg = AgentRegistry()
    agent = StubAgent(id="a", health_state=HealthState.HEALTHY)
    reg.register(agent)
    reg.set_state("a", AgentState.DISABLED)
    _run(reg.health("a"))  # healthy probe must NOT silently re-enable it
    assert reg.state_of("a") is AgentState.DISABLED


def test_health_probe_exception_is_unavailable_not_a_crash():
    @dataclass
    class BrokenHealthAgent(StubAgent):
        async def health(self) -> HealthResult:
            raise RuntimeError("probe boom")

    reg = AgentRegistry()
    reg.register(BrokenHealthAgent(id="broken"))
    result = _run(reg.health("broken"))  # must not raise
    assert result.state is HealthState.UNAVAILABLE
    assert "probe boom" in result.detail


def test_health_of_unregistered_agent_is_unknown():
    reg = AgentRegistry()
    result = _run(reg.health("ghost"))
    assert result.state is HealthState.UNKNOWN


def test_last_health_is_cached():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", health_state=HealthState.DEGRADED))
    assert reg.last_health("a") is None  # not queried yet
    _run(reg.health("a"))
    assert reg.last_health("a").state is HealthState.DEGRADED


# ---- Registry consistency (requirement 14) --------------------------------


def test_registry_consistency_across_register_transition_deregister():
    reg = AgentRegistry()
    reg.register(StubAgent(id="a", version="1.0.0"))
    reg.set_state("a", AgentState.READY)
    reg.register(StubAgent(id="a", version="2.0.0"))
    assert reg.state_of("a", version="2.0.0") is AgentState.REGISTERED
    assert reg.state_of("a", version="1.0.0") is AgentState.READY  # untouched
    reg.deregister("a", version="1.0.0")
    assert reg.versions_of("a") == ("2.0.0",)
    assert reg.get("a").version == "2.0.0"
