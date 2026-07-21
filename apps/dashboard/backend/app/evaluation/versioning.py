"""Evaluation Platform versioning (requester's "Versioning" section):
benchmark case versions, evaluation-criteria (metric weighting) versions,
and evaluation history — mirrors ``app.knowledge.versioning.VersioningLedger``'s
shape one layer up: a side ledger, never a mutation of the frozen
``BenchmarkCase``/``EvaluationResult`` records it tracks.

**"No benchmark should become unreproducible"** is the same guarantee
``app.knowledge.versioning`` already makes for frameworks, applied to
benchmark cases: ``register_case_version`` is append-only (a
``(case_id, version)`` pair, once registered, is never overwritten or
removed — the same invariant ``CaseRegistry.register`` already enforces via
``DuplicateCaseError``), and ``mark_case_deprecated`` only adds metadata, it
never deletes a version or its evaluation history.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from .errors import DuplicateCaseError, UnknownCaseError
from .models import BenchmarkCase, BenchmarkVersionInfo, EvaluationResult


@dataclass(frozen=True)
class MetricVersionInfo:
    """A frozen snapshot of the ``EvaluationMetric`` weighting scheme in
    effect at a point in time — so a later change to
    ``app.evaluation.evaluation``'s weights never silently reinterprets an
    old ``EvaluationResult``; the weights that actually produced a given
    score stay attached to that score's version tag."""

    version: str
    weights: dict
    effective_at: float = field(default_factory=time.time)
    notes: str = ""


@dataclass
class EvaluationVersioningLedger:
    _case_versions: dict[str, list[BenchmarkVersionInfo]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _metric_versions: dict[str, MetricVersionInfo] = field(default_factory=dict)
    _evaluation_history: dict[str, list[EvaluationResult]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # ---- benchmark case versions -------------------------------------------

    def register_case_version(
        self, case: BenchmarkCase, *, reason: str = ""
    ) -> BenchmarkVersionInfo:
        existing = {v.version for v in self._case_versions[case.case_id]}
        if case.version in existing:
            raise DuplicateCaseError(
                f"case {case.case_id!r} version {case.version!r} already "
                "has a versioning ledger entry"
            )
        info = BenchmarkVersionInfo(
            case_id=case.case_id,
            version=case.version,
            deprecated=False,
            replaced_by=None,
            reason=reason,
        )
        self._case_versions[case.case_id].append(info)
        return info

    def mark_case_deprecated(
        self,
        case_id: str,
        version: str,
        *,
        replaced_by: str | None = None,
        reason: str = "",
    ) -> BenchmarkVersionInfo:
        entries = self._case_versions.get(case_id, [])
        for i, entry in enumerate(entries):
            if entry.version == version:
                updated = BenchmarkVersionInfo(
                    case_id=case_id,
                    version=version,
                    deprecated=True,
                    replaced_by=replaced_by,
                    reason=reason,
                    created_at=entry.created_at,
                )
                entries[i] = updated
                return updated
        raise UnknownCaseError(
            f"no versioning ledger entry for case {case_id!r} version {version!r}"
        )

    def case_version_history(self, case_id: str) -> tuple[BenchmarkVersionInfo, ...]:
        return tuple(self._case_versions.get(case_id, ()))

    # ---- evaluation-criteria (metric weighting) versions -------------------

    def register_metric_version(
        self, version: str, weights: dict, *, notes: str = ""
    ) -> MetricVersionInfo:
        if version in self._metric_versions:
            raise DuplicateCaseError(
                f"metric weighting version {version!r} is already registered"
            )
        info = MetricVersionInfo(version=version, weights=dict(weights), notes=notes)
        self._metric_versions[version] = info
        return info

    def metric_version(self, version: str) -> MetricVersionInfo | None:
        return self._metric_versions.get(version)

    # ---- evaluation history --------------------------------------------------

    def record_evaluation(self, evaluation: EvaluationResult) -> None:
        self._evaluation_history[evaluation.case_id].append(evaluation)

    def evaluation_history_for(self, case_id: str) -> tuple[EvaluationResult, ...]:
        return tuple(
            sorted(
                self._evaluation_history.get(case_id, ()),
                key=lambda e: e.evaluated_at,
            )
        )

    def latest_evaluation_for(self, case_id: str) -> EvaluationResult | None:
        history = self.evaluation_history_for(case_id)
        return history[-1] if history else None
