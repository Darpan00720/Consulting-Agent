"""Organization Layer error hierarchy — mirrors ``app.knowledge.errors``' and
``app.consulting.errors``' shape and the same "raise only for a domain
invariant" discipline."""

from __future__ import annotations


class OrganizationError(Exception):
    """Base class for every Organization Layer error."""


class UnknownRoleError(OrganizationError):
    """No role registered under the given id/version."""


class DuplicateRoleError(OrganizationError):
    """A role with this (id, version) is already registered."""


class ResponsibilityConflictError(OrganizationError):
    """Raised only by callers that opt into strict RACI validation; the
    default ``detect_conflicts`` reports conflicts rather than raising, the
    same "report, don't raise" discipline used everywhere else in this
    platform for an expected, not exceptional, outcome."""


class UnknownRequestError(OrganizationError):
    """No collaboration request exists under the given id."""


class InsufficientAuthorityError(OrganizationError):
    """Raised only when an approval escalates all the way up the reporting
    chain with no role holding the required authority — a genuine
    organizational gap, not a normal outcome."""


class RoleNotEligibleError(OrganizationError):
    """Raised when a role is asked to execute work outside its declared
    engagement types or framework support — assigning the wrong role to a
    piece of work is a genuine organizational rule violation, not an
    expected outcome."""
