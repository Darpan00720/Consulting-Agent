"""Agent Registry (requirement 2).

Registration, deregistration, lookup, discovery, capability search, version
lookup, and duplicate detection — the platform's agent catalog. The Dispatcher
never hardcodes agent instances (that mandate already holds: the Dispatcher
only ever calls ``Target.invoke()``, unmodified); THIS registry is what makes
agents discoverable/introspectable independent of any one Target's hardwired
choice.

``AgentRuntime.execute()`` does **not** require registry lookup — the two are
independently composable (a caller can execute an unregistered agent
directly). That is what keeps "add a new agent" a pure data operation
(requirement 9: plugin-friendly, no switch/if-else, no Dispatcher change).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agents.agent import Agent
from app.agents.errors import ConfigurationError
from app.agents.models import AgentState, HealthResult, HealthState, is_legal_transition

if TYPE_CHECKING:
    from app.agents.models import Capability
    from app.workflow.targets import WorkflowCategory

log = logging.getLogger(__name__)


class DuplicateAgentError(ConfigurationError):
    """Registering the same ``(id, version)`` twice without ``replace=True``."""


class UnknownAgentError(ConfigurationError):
    """Looked up an agent id/version that was never registered."""


class IllegalTransitionError(ConfigurationError):
    """Attempted lifecycle transition isn't in the legal-transition table
    (``models._LEGAL_TRANSITIONS``) — registry state stays consistent
    (requirement 14: "Agent Registry consistency")."""

    def __init__(self, agent_id: str, current: AgentState, target: AgentState) -> None:
        self.agent_id = agent_id
        self.current = current
        self.target = target
        super().__init__(
            f"illegal transition for '{agent_id}': {current.value} -> {target.value}"
        )


class AgentRegistry:
    """In-process agent catalog. Not a singleton by construction — tests build
    their own; ``builtin.default_agent_registry()`` provides the production
    instance seeded with the four built-in agents (kept out of THIS module to
    avoid a registry → builtin → registry import cycle)."""

    def __init__(self) -> None:
        self._by_id_version: dict[tuple[str, str], Agent] = {}
        self._latest: dict[str, str] = {}  # agent id -> latest registered version
        self._state: dict[tuple[str, str], AgentState] = {}
        self._last_health: dict[tuple[str, str], HealthResult] = {}

    # ---- registration -------------------------------------------------

    def register(self, agent: Agent, *, replace: bool = False) -> None:
        """Duplicate detection (requirement 2): the same ``(id, version)`` pair
        twice is an error unless the caller explicitly opts into replacement."""
        key = (agent.id, agent.version)
        if key in self._by_id_version and not replace:
            raise DuplicateAgentError(
                f"agent '{agent.id}' version '{agent.version}' is already registered"
            )
        self._by_id_version[key] = agent
        self._latest[agent.id] = agent.version
        self._state[key] = AgentState.REGISTERED
        log.debug("agent-registry register id=%s version=%s", agent.id, agent.version)

    def deregister(self, agent_id: str, version: str | None = None) -> None:
        """Remove one version (default: the currently-latest); demotes
        ``latest`` to the next-highest remaining version, or clears it."""
        version = version or self._latest.get(agent_id)
        if version is None:
            return
        key = (agent_id, version)
        self._by_id_version.pop(key, None)
        self._state.pop(key, None)
        self._last_health.pop(key, None)
        if self._latest.get(agent_id) == version:
            remaining = [v for (i, v) in self._by_id_version if i == agent_id]
            if remaining:
                self._latest[agent_id] = sorted(remaining)[-1]
            else:
                self._latest.pop(agent_id, None)
        log.debug("agent-registry deregister id=%s version=%s", agent_id, version)

    # ---- lookup ---------------------------------------------------------

    def get(self, agent_id: str) -> Agent | None:
        """The latest registered version of ``agent_id``, or ``None``."""
        version = self._latest.get(agent_id)
        if version is None:
            return None
        return self._by_id_version.get((agent_id, version))

    def get_version(self, agent_id: str, version: str) -> Agent | None:
        """Version lookup (requirement 2): a SPECIFIC version, not just latest."""
        return self._by_id_version.get((agent_id, version))

    def versions_of(self, agent_id: str) -> tuple[str, ...]:
        return tuple(sorted(v for (i, v) in self._by_id_version if i == agent_id))

    # ---- discovery --------------------------------------------------------

    def discover(self) -> tuple[Agent, ...]:
        """Every registered agent's LATEST version — the discoverable roster
        (requirement 2/9's "dynamic discovery")."""
        found = (self.get(agent_id) for agent_id in self._latest)
        return tuple(a for a in found if a is not None)

    def find_by_capability(self, capability: Capability) -> tuple[Agent, ...]:
        """Capability-based lookup (requirement 3)."""
        return tuple(a for a in self.discover() if capability in a.capabilities)

    def find_by_workflow(self, workflow: WorkflowCategory) -> tuple[Agent, ...]:
        return tuple(a for a in self.discover() if workflow in a.supported_workflows)

    # ---- lifecycle (requirement 4) -------------------------------------

    def state_of(self, agent_id: str, version: str | None = None) -> AgentState:
        version = version or self._latest.get(agent_id)
        if version is None:
            return AgentState.UNKNOWN
        return self._state.get((agent_id, version), AgentState.UNKNOWN)

    def set_state(
        self, agent_id: str, target: AgentState, *, version: str | None = None
    ) -> None:
        """Validated transition — illegal edges raise rather than silently
        applying (requirement 14: registry consistency is a hard invariant)."""
        version = version or self._latest.get(agent_id)
        if version is None:
            raise UnknownAgentError(f"agent '{agent_id}' is not registered")
        key = (agent_id, version)
        current = self._state.get(key, AgentState.UNKNOWN)
        if not is_legal_transition(current, target):
            raise IllegalTransitionError(agent_id, current, target)
        self._state[key] = target
        log.debug(
            "agent-registry transition id=%s %s -> %s",
            agent_id,
            current.value,
            target.value,
        )

    # ---- health (requirement 5) ----------------------------------------
    #
    # "Dispatcher MAY query health through the registry" — a capability this
    # platform offers a host. Today's Dispatcher (unmodified, per constraint)
    # does not call this; it is exposed for a future host/health-check surface,
    # and is fully implemented/tested here regardless.

    async def health(self, agent_id: str, version: str | None = None) -> HealthResult:
        version = version or self._latest.get(agent_id)
        if version is None:
            return HealthResult(HealthState.UNKNOWN, detail="not registered")
        agent = self._by_id_version.get((agent_id, version))
        if agent is None:
            return HealthResult(HealthState.UNKNOWN, detail="not registered")
        try:
            result = await agent.health()
        except Exception as exc:  # noqa: BLE001 — a broken probe means UNAVAILABLE, not a crash
            result = HealthResult(
                HealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
            )
        self._last_health[(agent_id, version)] = result
        self._reconcile_state_from_health(agent_id, version, result)
        return result

    # A health PROBE may only move an agent among {READY, BUSY, FAILED,
    # UNKNOWN} — never out of DISABLED/STOPPED. Those two are ADMIN-only exits
    # (an explicit ``set_state`` call, e.g. a human re-enabling a disabled
    # agent) even though the transition table itself permits DISABLED->READY
    # for that explicit path. Reusing the same table for automatic health
    # reconciliation would let a healthy probe silently resurrect an agent an
    # operator deliberately took offline — a stricter guard than
    # ``is_legal_transition`` is required here specifically.
    _HEALTH_RECONCILE_EXEMPT = frozenset({AgentState.DISABLED, AgentState.STOPPED})

    def _reconcile_state_from_health(
        self, agent_id: str, version: str, result: HealthResult
    ) -> None:
        key = (agent_id, version)
        current = self._state.get(key, AgentState.UNKNOWN)
        if current in self._HEALTH_RECONCILE_EXEMPT:
            return
        target = {
            HealthState.HEALTHY: AgentState.READY,
            HealthState.DEGRADED: AgentState.READY,  # still usable, just degraded
            HealthState.UNAVAILABLE: AgentState.FAILED,
            HealthState.UNKNOWN: AgentState.UNKNOWN,
        }[result.state]
        if is_legal_transition(current, target):
            self._state[key] = target
        # else: leave state as-is — never crash, never force an illegal edge.

    def last_health(
        self, agent_id: str, version: str | None = None
    ) -> HealthResult | None:
        version = version or self._latest.get(agent_id)
        if version is None:
            return None
        return self._last_health.get((agent_id, version))
