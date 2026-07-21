"""Framework Library error hierarchy — mirrors ``app.consulting.errors``'
shape and the same "raise only for a domain invariant" discipline."""

from __future__ import annotations


class FrameworkError(Exception):
    """Base class for every Framework Library error."""


class UnknownFrameworkError(FrameworkError):
    """No framework registered under the given id/version."""


class DuplicateFrameworkError(FrameworkError):
    """A framework with this (id, version) is already registered."""


class MissingRequiredInputError(FrameworkError):
    """A framework execution was attempted without a declared required input."""


class MissingRequiredEvidenceError(FrameworkError):
    """A framework execution was attempted without declared required evidence."""


class IncompatibleCompositionError(FrameworkError):
    """A requested framework composition violates a compatibility/dependency
    rule (wrong order, missing dependency, unsupported engagement type)."""


class CircularDependencyError(FrameworkError):
    """A framework's declared ``dependencies`` form a cycle — cannot resolve
    an execution order."""


class DeprecatedFrameworkError(FrameworkError):
    """Raised only when a caller resolves a deprecated framework with no
    replacement AND explicitly opts out of backward-compatible fallback."""
