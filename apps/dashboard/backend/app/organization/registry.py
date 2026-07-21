"""``OrganizationRegistry`` — mirrors the shape every registry in this
codebase already established (``AgentRegistry``, ``MemoryRegistry``,
``ToolRegistry``, ``app.consulting.registry.WorkflowRegistry``,
``app.knowledge.registry.FrameworkRegistry``): register, version-aware get,
and search axes. Adds a reporting-chain walk — the one capability this
registry's catalog needs that the others didn't.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.consulting.models import EngagementCategory
from app.organization.errors import DuplicateRoleError, UnknownRoleError
from app.organization.models import DecisionType, Practice, RoleDefinition


@dataclass
class OrganizationRegistry:
    _roles: dict[tuple[str, str], RoleDefinition] = field(default_factory=dict)

    # ---- registration / lookup / versioning ------------------------------

    def register(self, role: RoleDefinition) -> None:
        key = (role.id, role.version)
        if key in self._roles:
            raise DuplicateRoleError(
                f"role {role.id!r} version {role.version!r} already registered"
            )
        self._roles[key] = role

    def get(self, role_id: str, version: str | None = None) -> RoleDefinition:
        if version is not None:
            key = (role_id, version)
            if key not in self._roles:
                raise UnknownRoleError(f"no role {role_id!r} version {version!r}")
            return self._roles[key]
        candidates = [r for (rid, _v), r in self._roles.items() if rid == role_id]
        if not candidates:
            raise UnknownRoleError(f"no role registered under id {role_id!r}")
        return max(candidates, key=lambda r: _version_key(r.version))

    def list(self) -> tuple[RoleDefinition, ...]:
        return tuple(self._roles.values())

    def versions_of(self, role_id: str) -> tuple[str, ...]:
        return tuple(v for (rid, v) in self._roles if rid == role_id)

    def _latest_each(self) -> tuple[RoleDefinition, ...]:
        ids = {rid for (rid, _v) in self._roles}
        return tuple(self.get(rid) for rid in ids)

    # ---- search axes ------------------------------------------------------

    def find_by_practice(self, practice: Practice) -> tuple[RoleDefinition, ...]:
        return tuple(r for r in self._latest_each() if r.practice is practice)

    def find_by_capability(self, capability: str) -> tuple[RoleDefinition, ...]:
        return tuple(
            r for r in self._latest_each() if capability in r.required_capabilities
        )

    def find_by_engagement(
        self, engagement: EngagementCategory
    ) -> tuple[RoleDefinition, ...]:
        return tuple(
            r for r in self._latest_each() if engagement in r.supported_engagement_types
        )

    def find_by_decision_authority(
        self, decision: DecisionType
    ) -> tuple[RoleDefinition, ...]:
        return tuple(r for r in self._latest_each() if decision in r.decision_authority)

    # ---- reporting chain ----------------------------------------------------

    def reporting_chain(self, role_id: str) -> tuple[RoleDefinition, ...]:
        """The role itself, then its manager, then their manager, ... up to
        the top of the firm (``reporting_line is None``). Used by
        ``governance.py`` to walk escalation."""
        chain: list[RoleDefinition] = []
        current: RoleDefinition | None = self.get(role_id)
        seen: set[str] = set()
        while current is not None:
            if current.id in seen:
                break  # a malformed reporting cycle — stop rather than loop forever
            seen.add(current.id)
            chain.append(current)
            current = (
                self.get(current.reporting_line) if current.reporting_line else None
            )
        return tuple(chain)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def default_organization_registry() -> OrganizationRegistry:
    """Pre-registers the full 25-role catalog (``app.organization.catalog``)."""
    from app.organization.catalog import all_role_definitions

    registry = OrganizationRegistry()
    for role in all_role_definitions():
        registry.register(role)
    return registry
