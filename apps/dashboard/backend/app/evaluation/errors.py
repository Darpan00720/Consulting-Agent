"""Evaluation Platform error hierarchy — mirrors every prior layer's shape
and the same "raise only for a domain invariant" discipline."""

from __future__ import annotations


class EvaluationError(Exception):
    """Base class for every Evaluation Platform error."""


class UnknownCaseError(EvaluationError):
    """No benchmark case registered under the given id/version."""


class DuplicateCaseError(EvaluationError):
    """A benchmark case with this (id, version) is already registered —
    cases are immutable, so a content change must be a new version."""


class ReplayFailedError(EvaluationError):
    """A case replay could not complete — a genuine execution failure, not
    a normal evaluation outcome (a POOR score is a normal outcome; a replay
    that never produced a result is not)."""


class InsufficientDataError(EvaluationError):
    """An evaluation, comparison, or dashboard computation was attempted
    with too little history to produce a meaningful result."""
