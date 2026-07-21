"""Deliverables Engine error hierarchy — mirrors ``app.consulting.errors``'/
``app.knowledge.errors``'/``app.organization.errors``'/``app.synthesis.errors``'
shape and the same "raise only for a domain invariant" discipline."""

from __future__ import annotations


class DeliverableError(Exception):
    """Base class for every Deliverables Engine error."""


class UnknownDeliverableTypeError(DeliverableError):
    """No deliverable definition registered under the given id/version."""


class DuplicateDeliverableTypeError(DeliverableError):
    """A deliverable definition with this (id, version) is already registered."""


class UnknownSectionError(DeliverableError):
    """A deliverable references a section id that isn't in the shared
    section library."""


class MissingTraceabilityError(DeliverableError):
    """Raised when a generated section would carry content with no
    reference to the synthesized recommendation/finding/insight/narrative it
    came from — "no deliverable may invent unsupported content" is a hard
    invariant, not a lint, the same principled exception to "never raise"
    ``app.synthesis.tracking`` already carved out one layer down."""


class QualityValidationFailedError(DeliverableError):
    """Raised when export is attempted on a deliverable that hasn't passed
    quality validation — "no deliverable may publish without validation" is
    enforced here, not by convention."""


class UnsupportedExportFormatError(DeliverableError):
    """No exporter registered for the requested ``ExportFormat``."""
