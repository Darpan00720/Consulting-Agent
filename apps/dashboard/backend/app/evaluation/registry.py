"""``CaseRegistry`` — lookup over the benchmark case library.

Mirrors ``app.knowledge.registry.FrameworkRegistry``'s shape exactly,
including its public method names (``list``/``get``/``find_by_*``) — a
2026-07-19 architecture review corrected an earlier draft that had drifted
to ``all_cases``/``by_engagement_type``/``by_difficulty``, the one
registry in this codebase not following the convention every other
registry (``WorkflowRegistry``, ``FrameworkRegistry``, ``OrganizationRegistry``,
``DeliverableRegistry``) already established: a thin, in-memory index keyed
by id, plus a version dimension (cases are immutable, so multiple versions
of the same ``case_id`` may coexist side by side).
"""

from __future__ import annotations

from .case_library import all_benchmark_cases
from .errors import DuplicateCaseError, UnknownCaseError
from .models import BenchmarkCase


class CaseRegistry:
    def __init__(self) -> None:
        self._cases: dict[tuple[str, str], BenchmarkCase] = {}

    def register(self, case: BenchmarkCase) -> None:
        key = (case.case_id, case.version)
        if key in self._cases:
            raise DuplicateCaseError(
                f"case {case.case_id!r} version {case.version!r} already registered"
            )
        self._cases[key] = case

    def get(self, case_id: str, version: str | None = None) -> BenchmarkCase:
        if version is not None:
            key = (case_id, version)
            if key not in self._cases:
                raise UnknownCaseError(f"unknown case {case_id!r} version {version!r}")
            return self._cases[key]
        matches = [c for (cid, _v), c in self._cases.items() if cid == case_id]
        if not matches:
            raise UnknownCaseError(f"unknown case {case_id!r}")
        return max(matches, key=lambda c: c.version)

    def versions_of(self, case_id: str) -> tuple[BenchmarkCase, ...]:
        return tuple(
            sorted(
                (c for (cid, _v), c in self._cases.items() if cid == case_id),
                key=lambda c: c.version,
            )
        )

    def list(self) -> tuple[BenchmarkCase, ...]:
        return tuple(self._cases.values())

    def find_by_engagement(self, engagement_type) -> tuple[BenchmarkCase, ...]:
        return tuple(
            c for c in self._cases.values() if c.engagement_type == engagement_type
        )

    def find_by_difficulty(self, difficulty) -> tuple[BenchmarkCase, ...]:
        return tuple(c for c in self._cases.values() if c.difficulty == difficulty)


def default_case_registry() -> CaseRegistry:
    registry = CaseRegistry()
    for case in all_benchmark_cases():
        registry.register(case)
    return registry
