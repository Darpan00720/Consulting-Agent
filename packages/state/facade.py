"""The Engagement State facade — the sole public entry point (M1.3, M1.7).

Consumers depend on :class:`EngagementProtocol`; :class:`Engagement` is the
in-memory implementation. The facade is a **wiring layer only**: it delegates
to the append pipeline, the S2 arithmetic surface, and the M1.6 validation
runner, and it owns provenance (which constructor was used) while the
pipeline owns capability.

Snapshot semantics (M1.7.1, design D1): state crosses the public boundary
only as **detached deep copies** — ``get_state()`` returns a snapshot and
``from_state`` copies on ingest — so no caller ever holds an alias of the
internal state, and mutating a snapshot can never affect the engagement.

Event API (M1.7.3-S5): state evolves only through ``append_event`` /
``append_events`` — guarded, atomic, all-or-nothing appends. Append
availability by provenance:

=================  ==============================================
``create()``       append supported
replay (M1.9)      append supported (future)
``from_state()``   read-only — appends raise AppendUnsupportedError
``from_json()``    read-only — appends raise AppendUnsupportedError
=================  ==============================================

This restriction is temporary. M1.8 introduces persisted event logs. M1.9
replay-backed engagements remove this limitation. The append capability flag
exists solely during the transition period.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, Self

from state.append import (
    AppendPipeline,
    AppendResult,
)
from state.append import (
    current_sequence as derive_current_sequence,
)
from state.events import Event
from state.identifiers import EngagementId
from state.models import EngagementMetadata, EngagementState
from state.validation import ValidationReport
from state.validation import validate as validate_state

if TYPE_CHECKING:
    from collections.abc import Sequence


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

    def validate(self) -> ValidationReport: ...

    def to_json(self) -> str: ...

    def append_event(self, event: Event, *, expected_version: int) -> AppendResult: ...

    def append_events(
        self, events: Sequence[Event], *, expected_version: int
    ) -> AppendResult: ...

    def current_version(self) -> int: ...

    def current_sequence(self) -> int: ...


class Engagement:
    """In-memory implementation of :class:`EngagementProtocol`."""

    def __init__(self, pipeline: AppendPipeline) -> None:
        self._pipeline = pipeline

    @classmethod
    def create(
        cls,
        engagement_id: str,
        tenant_id: str,
        slug: str,
        created_by: Literal["human", "system"] = "human",
    ) -> Self:
        """Create a new engagement as a valid, bare, append-capable state."""
        metadata = EngagementMetadata(
            engagement_id=EngagementId(engagement_id),
            tenant_id=tenant_id,
            slug=slug,
            created_by=created_by,
        )
        state = EngagementState(metadata=metadata)
        return cls(AppendPipeline(state, append_supported=True))

    @classmethod
    def from_state(cls, state: EngagementState) -> Self:
        """Adopt an existing state (deep-copied on ingest; **read-only**).

        Without the state's event log the engagement cannot append —
        temporary until M1.8/M1.9 (see the module docstring).
        """
        return cls(AppendPipeline(state.model_copy(deep=True), append_supported=False))

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Deserialize an engagement from JSON (**read-only**, as from_state)."""
        return cls(
            AppendPipeline(
                EngagementState.model_validate_json(data), append_supported=False
            )
        )

    def get_state(self) -> EngagementState:
        """Return a detached deep snapshot of the current Engagement State.

        Mutating the snapshot (models, lists, dicts — anywhere in the object
        graph) never affects the engagement. Successive calls return equal but
        distinct objects.
        """
        return self._pipeline.committed().state.model_copy(deep=True)

    def validate(self) -> ValidationReport:
        """Run M1.6 invariant validation; the report is returned unaltered."""
        return validate_state(self._pipeline.committed().state)

    def to_json(self) -> str:
        """Serialize the current state to JSON (the log is not serialized)."""
        return self._pipeline.committed().state.model_dump_json()

    def append_event(self, event: Event, *, expected_version: int) -> AppendResult:
        """Append one event through the pipeline (single delegation)."""
        return self._pipeline.append_event(event, expected_version=expected_version)

    def append_events(
        self, events: Sequence[Event], *, expected_version: int
    ) -> AppendResult:
        """Append an atomic batch through the pipeline (single delegation)."""
        return self._pipeline.append_events(events, expected_version=expected_version)

    def current_version(self) -> int:
        """The committed version — read from the stored snapshot, never derived."""
        return self._pipeline.committed().version

    def current_sequence(self) -> int:
        """The next sequence number — delegated exclusively to S2."""
        return derive_current_sequence(self._pipeline.committed().log)


if TYPE_CHECKING:
    # Static assertion that Engagement satisfies the protocol.
    _conformance: type[EngagementProtocol] = Engagement
