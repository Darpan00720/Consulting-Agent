"""``FrameworkRegistry`` — mirrors the shape every other registry in this
codebase already established (``AgentRegistry``, ``MemoryRegistry``,
``ToolRegistry``, ``app.consulting.registry.WorkflowRegistry``): register,
get (version-aware), category/tag/industry/engagement/company-size search.
Adds dependency resolution (topological ordering, cycle detection) and a
compatibility lookup — the two capabilities this library's catalog actually
needs that the prior registries didn't.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.consulting.models import EngagementCategory
from app.knowledge.errors import (
    CircularDependencyError,
    DuplicateFrameworkError,
    UnknownFrameworkError,
)
from app.knowledge.models import CompanySize, FrameworkCategory, FrameworkDefinition


@dataclass
class FrameworkRegistry:
    _frameworks: dict[tuple[str, str], FrameworkDefinition] = field(
        default_factory=dict
    )

    # ---- registration / lookup / versioning ------------------------------

    def register(self, framework: FrameworkDefinition) -> None:
        key = (framework.id, framework.version)
        if key in self._frameworks:
            raise DuplicateFrameworkError(
                f"framework {framework.id!r} version {framework.version!r} "
                "already registered"
            )
        self._frameworks[key] = framework

    def get(self, framework_id: str, version: str | None = None) -> FrameworkDefinition:
        if version is not None:
            key = (framework_id, version)
            if key not in self._frameworks:
                raise UnknownFrameworkError(
                    f"no framework {framework_id!r} version {version!r}"
                )
            return self._frameworks[key]
        candidates = [
            f for (fid, _v), f in self._frameworks.items() if fid == framework_id
        ]
        if not candidates:
            raise UnknownFrameworkError(
                f"no framework registered under id {framework_id!r}"
            )
        return max(candidates, key=lambda f: _version_key(f.version))

    def list(self) -> tuple[FrameworkDefinition, ...]:
        return tuple(self._frameworks.values())

    def versions_of(self, framework_id: str) -> tuple[str, ...]:
        return tuple(v for (fid, v) in self._frameworks if fid == framework_id)

    # ---- search axes ------------------------------------------------------

    def find_by_category(
        self, category: FrameworkCategory
    ) -> tuple[FrameworkDefinition, ...]:
        return tuple(f for f in self._latest_each() if f.category is category)

    def find_by_tag(self, tag: str) -> tuple[FrameworkDefinition, ...]:
        return tuple(f for f in self._latest_each() if tag in f.tags)

    def find_by_industry(self, industry: str) -> tuple[FrameworkDefinition, ...]:
        return tuple(
            f
            for f in self._latest_each()
            if "all" in f.supported_industries or industry in f.supported_industries
        )

    def find_by_engagement(
        self, engagement: EngagementCategory
    ) -> tuple[FrameworkDefinition, ...]:
        return tuple(
            f for f in self._latest_each() if engagement in f.supported_engagements
        )

    def find_by_company_size(
        self, size: CompanySize
    ) -> tuple[FrameworkDefinition, ...]:
        return tuple(
            f for f in self._latest_each() if size in f.supported_company_sizes
        )

    def _latest_each(self) -> tuple[FrameworkDefinition, ...]:
        """One entry per framework id — the latest registered version — so
        search results never return two versions of the same framework."""
        ids = {fid for (fid, _v) in self._frameworks}
        return tuple(self.get(fid) for fid in ids)

    # ---- compatibility + dependency resolution -----------------------------

    def is_compatible(
        self,
        framework_id: str,
        engagement: EngagementCategory,
        *,
        industry: str = "all",
        company_size: CompanySize | None = None,
    ) -> bool:
        framework = self.get(framework_id)
        if engagement not in framework.supported_engagements:
            return False
        industry_ok = "all" in framework.supported_industries or (
            industry in framework.supported_industries
        )
        if industry != "all" and not industry_ok:
            return False
        return not (
            company_size is not None
            and company_size not in framework.supported_company_sizes
        )

    def resolve_dependency_order(
        self, framework_ids: tuple[str, ...]
    ) -> tuple[str, ...]:
        """Topological sort of ``framework_ids`` (plus any declared
        dependencies not already in the list) so dependencies always execute
        before their dependents. Raises ``CircularDependencyError`` on a
        cycle, ``UnknownFrameworkError`` if a dependency isn't registered."""
        visited: dict[str, int] = {}  # 0 = visiting, 1 = done
        order: list[str] = []

        def visit(fid: str, path: tuple[str, ...]) -> None:
            state = visited.get(fid)
            if state == 1:
                return
            if state == 0:
                cycle = " -> ".join((*path, fid))
                raise CircularDependencyError(f"circular framework dependency: {cycle}")
            visited[fid] = 0
            framework = self.get(fid)  # raises UnknownFrameworkError if missing
            for dep in framework.dependencies:
                visit(dep, (*path, fid))
            visited[fid] = 1
            order.append(fid)

        for fid in framework_ids:
            visit(fid, ())
        return tuple(order)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def default_framework_registry() -> FrameworkRegistry:
    """Pre-registers the full 86-framework catalog (``app.knowledge.catalog``)."""
    from app.knowledge.catalog import all_framework_definitions

    registry = FrameworkRegistry()
    for framework in all_framework_definitions():
        registry.register(framework)
    return registry
