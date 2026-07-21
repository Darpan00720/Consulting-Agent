"""The Agent abstraction (requirement 1).

Every executable agent implements this Protocol. Structural typing (like
``Target``, ADR-013 §4a) — no ABC, no required inheritance, so a future
third-party-style agent (Gemini, Kimi, CrewAI, ...) can satisfy it without
importing anything from this package (requirement 13's forward compatibility).

No agent-specific code lives in the Dispatcher, the Runtime, or the Registry
beyond this interface — every method here is exactly what ``AgentRuntime`` and
``AgentRegistry`` need, nothing more.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.agents.models import AgentMetadata, AgentRequest, AgentResponse, HealthResult

if TYPE_CHECKING:
    from app.agents.models import Capability
    from app.workflow.targets import WorkflowCategory


@runtime_checkable
class Agent(Protocol):
    """The minimum contract every runtime agent satisfies (requirement 1)."""

    id: str
    name: str
    version: str
    description: str
    owner: str
    capabilities: tuple[Capability, ...]
    supported_workflows: tuple[WorkflowCategory, ...]

    async def health(self) -> HealthResult: ...
    async def execute(self, request: AgentRequest) -> AgentResponse: ...
    def metadata(self) -> AgentMetadata: ...
