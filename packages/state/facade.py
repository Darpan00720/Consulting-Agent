"""The Engagement State facade — the sole public entry point (M1.3).

Consumers depend on :class:`EngagementProtocol`; :class:`Engagement` is the
in-memory implementation. Future implementations (file-backed, AgentDB-backed,
testing) can satisfy the same protocol without changing consumers.

The public API is frozen to exactly six operations: ``create``, ``from_state``,
``from_json`` (constructors), ``get_state``, ``validate``, ``to_json``. State
evolves only through the event API (a later sub-milestone); this facade
intentionally exposes **no mutation methods**.

Snapshot semantics (M1.7, design D1): state crosses the public boundary only as
**detached deep copies** — ``get_state()`` returns a snapshot and ``from_state``
copies on ingest — so no caller ever holds an alias of the internal state, and
mutating a snapshot can never affect the engagement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, Self

from state.identifiers import EngagementId
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
            engagement_id=EngagementId(engagement_id),
            tenant_id=tenant_id,
            slug=slug,
            created_by=created_by,
        )
        return cls(EngagementState(metadata=metadata))

    @classmethod
    def from_state(cls, state: EngagementState) -> Self:
        """Adopt an existing Engagement State (deep-copied on ingest).

        The caller's instance is never aliased: mutating it after this call has
        no effect on the engagement.
        """
        return cls(state.model_copy(deep=True))

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Deserialize an engagement from JSON."""
        return cls(EngagementState.model_validate_json(data))

    def get_state(self) -> EngagementState:
        """Return a detached deep snapshot of the current Engagement State.

        Mutating the snapshot (models, lists, dicts — anywhere in the object
        graph) never affects the engagement. Successive calls return equal but
        distinct objects.
        """
        return self._state.model_copy(deep=True)

    def validate(self) -> None:
        """Re-validate the current state; raises on any violation."""
        EngagementState.model_validate(self._state.model_dump())

    def to_json(self) -> str:
        """Serialize the current state to JSON."""
        return self._state.model_dump_json()


if TYPE_CHECKING:
    # Static assertion that Engagement satisfies the protocol.
    _conformance: type[EngagementProtocol] = Engagement
