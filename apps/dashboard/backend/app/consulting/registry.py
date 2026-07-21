"""``WorkflowRegistry`` — mirrors the shape ``AgentRegistry``/``MemoryRegistry``/
``ToolRegistry`` already established (register/get/list/find-by-category,
version-aware), so this package's registration story looks like every other
platform layer's rather than inventing a new pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.consulting.errors import DuplicateWorkflowError, UnknownWorkflowError
from app.consulting.models import EngagementCategory
from app.consulting.quality_gates import standard_gates
from app.consulting.workflow import WorkflowDefinition, standard_workflow


@dataclass
class WorkflowRegistry:
    """Keyed by ``(id, version)`` — the same versioning shape ``ToolRegistry``
    (W5) uses. ``get(id)`` without a version returns the highest registered
    version (semver-string comparison via a simple tuple-of-ints parse)."""

    _workflows: dict[tuple[str, str], WorkflowDefinition] = field(default_factory=dict)

    def register(self, workflow: WorkflowDefinition) -> None:
        key = (workflow.id, workflow.version)
        if key in self._workflows:
            raise DuplicateWorkflowError(
                f"workflow {workflow.id!r} version {workflow.version!r} "
                "already registered"
            )
        self._workflows[key] = workflow

    def get(self, workflow_id: str, version: str | None = None) -> WorkflowDefinition:
        if version is not None:
            key = (workflow_id, version)
            if key not in self._workflows:
                raise UnknownWorkflowError(
                    f"no workflow {workflow_id!r} version {version!r}"
                )
            return self._workflows[key]
        candidates = [
            w for (wid, _v), w in self._workflows.items() if wid == workflow_id
        ]
        if not candidates:
            raise UnknownWorkflowError(
                f"no workflow registered under id {workflow_id!r}"
            )
        return max(candidates, key=lambda w: _version_key(w.version))

    def find_by_category(
        self, category: EngagementCategory
    ) -> tuple[WorkflowDefinition, ...]:
        return tuple(w for w in self._workflows.values() if w.category is category)

    def list(self) -> tuple[WorkflowDefinition, ...]:
        return tuple(self._workflows.values())

    def versions_of(self, workflow_id: str) -> tuple[str, ...]:
        return tuple(v for (wid, v) in self._workflows if wid == workflow_id)


def _version_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in version.split("."))
    except ValueError:
        return (0,)


def default_workflow_registry() -> WorkflowRegistry:
    """Pre-registers a standardized workflow for every ``EngagementCategory``
    (28, across the 7 families the requester listed) via ``standard_workflow``
    — data-driven registration, not 28 hand-written classes. Registering
    category 29 is one more line here; nothing else in this package changes."""
    registry = WorkflowRegistry()
    gates = standard_gates()
    for category in EngagementCategory:
        registry.register(standard_workflow(category, quality_gates=gates))
    return registry
