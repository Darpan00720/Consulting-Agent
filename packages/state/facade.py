"""The Engagement State facade — the sole public entry point (M1.3).

Consumers depend on :class:`EngagementProtocol`; :class:`Engagement` is the
in-memory implementation. Future implementations (file-backed, AgentDB-backed,
testing) can satisfy the same protocol without changing consumers.

The public API is frozen to exactly six operations: ``create``, ``from_state``,
``from_json`` (constructors), ``get_state``, ``validate``, ``to_json``. State
evolves only through the event API (a later sub-milestone); this facade
intentionally exposes **no mutation methods**, and the current state is reached
via ``get_state()`` rather than a public attribute so an immutable/projected view
can be introduced later without breaking callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, Self

from state.models import EngagementMetadata, EngagementState


class EngagementProtocol(Protocol):
    """The public facade contract (see docs/api/EngagementState.md)."""

    @classmethod
    def create(
        cls,
        engagement_id: str,
        tenant_id: str,
        slug: str,
        created_by: Literal["human", "system"] = "human",
    ) -> Self: ...

    @classmethod
    def from_state(cls, state: EngagementState) -> Self: ...

    @classmethod
    def from_json(cls, data: str) -> Self: ...

    def get_state(self) -> EngagementState: ...

    def validate(self) -> None: ...

    def to_json(self) -> str: ...


class Engagement:
    """In-memory implementation of :class:`EngagementProtocol`."""

    def __init__(self, state: EngagementState) -> None:
        self._state = state

    @classmethod
    def create(
        cls,
        engagement_id: str,
        tenant_id: str,
        slug: str,
        created_by: Literal["human", "system"] = "human",
    ) -> Self:
        """Create a new engagement as a valid, bare Engagement State."""
        metadata = EngagementMetadata(
            engagement_id=engagement_id,
            tenant_id=tenant_id,
            slug=slug,
            created_by=created_by,
        )
        return cls(EngagementState(metadata=metadata))

    @classmethod
    def from_state(cls, state: EngagementState) -> Self:
        """Wrap an existing Engagement State."""
        return cls(state)

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Deserialize an engagement from JSON."""
        return cls(EngagementState.model_validate_json(data))

    def get_state(self) -> EngagementState:
        """Return the current Engagement State."""
        return self._state

    def validate(self) -> None:
        """Re-validate the current state; raises on any violation."""
        EngagementState.model_validate(self._state.model_dump())

    def to_json(self) -> str:
        """Serialize the current state to JSON."""
        return self._state.model_dump_json()


if TYPE_CHECKING:
    # Static assertion that Engagement satisfies the protocol.
    _conformance: type[EngagementProtocol] = Engagement
