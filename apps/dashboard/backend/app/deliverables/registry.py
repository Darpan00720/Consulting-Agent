"""``DeliverableRegistry`` — mirrors the shape every registry in this
codebase already established (``AgentRegistry``, ``FrameworkRegistry``,
``OrganizationRegistry``): register, version-aware get, search axes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.consulting.models import EngagementCategory
from app.deliverables.errors import (
    DuplicateDeliverableTypeError,
    UnknownDeliverableTypeError,
)
from app.deliverables.models import Audience, DeliverableDefinition


@dataclass
class DeliverableRegistry:
    _deliverables: dict[tuple[str, str], DeliverableDefinition] = field(
        default_factory=dict
    )

    def register(self, deliverable: DeliverableDefinition) -> None:
        key = (deliverable.id, deliverable.version)
        if key in self._deliverables:
            raise DuplicateDeliverableTypeError(
                f"deliverable {deliverable.id!r} version {deliverable.version!r} "
                "already registered"
            )
        self._deliverables[key] = deliverable

    def get(
        self, deliverable_id: str, version: str | None = None
    ) -> DeliverableDefinition:
        if version is not None:
            key = (deliverable_id, version)
            if key not in self._deliverables:
                raise UnknownDeliverableTypeError(
                    f"no deliverable {deliverable_id!r} version {version!r}"
                )
            return self._deliverables[key]
        candidates = [
            d for (did, _v), d in self._deliverables.items() if did == deliverable_id
        ]
        if not candidates:
            raise UnknownDeliverableTypeError(
                f"no deliverable registered under id {deliverable_id!r}"
            )
        return max(candidates, key=lambda d: _version_key(d.version))

    def list(self) -> tuple[DeliverableDefinition, ...]:
        return tuple(self._deliverables.values())

    def _latest_each(self) -> tuple[DeliverableDefinition, ...]:
        ids = {did for (did, _v) in self._deliverables}
        return tuple(self.get(did) for did in ids)

    def find_by_audience(self, audience: Audience) -> tuple[DeliverableDefinition, ...]:
        return tuple(d for d in self._latest_each() if audience in d.audience)

    def find_by_engagement(
        self, engagement: EngagementCategory
    ) -> tuple[DeliverableDefinition, ...]:
        return tuple(
            d for d in self._latest_each() if engagement in d.supported_engagement_types
        )

    def find_by_tag(self, tag: str) -> tuple[DeliverableDefinition, ...]:
        return tuple(d for d in self._latest_each() if tag in d.tags)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def default_deliverable_registry() -> DeliverableRegistry:
    """Pre-registers the full 20-type catalog (``app.deliverables.catalog``)."""
    from app.deliverables.catalog import all_deliverable_definitions

    registry = DeliverableRegistry()
    for deliverable in all_deliverable_definitions():
        registry.register(deliverable)
    return registry
