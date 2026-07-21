"""Synthesis Engine error hierarchy — mirrors ``app.consulting.errors``'/
``app.knowledge.errors``'/``app.organization.errors``' shape and the same
"raise only for a domain invariant" discipline."""

from __future__ import annotations


class SynthesisError(Exception):
    """Base class for every Synthesis Engine error."""


class UnknownEvidenceError(SynthesisError):
    """A finding referenced an evidence id that doesn't exist in the
    underlying engagement — the base of the traceability chain."""


class UnknownFindingError(SynthesisError):
    """An insight referenced a finding id that doesn't exist."""


class UnknownInsightError(SynthesisError):
    """An opportunity referenced an insight id that doesn't exist."""


class UnknownOpportunityError(SynthesisError):
    """A recommendation referenced an opportunity id that doesn't exist."""


class UnknownRecommendationError(SynthesisError):
    """An implementation theme or narrative referenced a recommendation id
    that doesn't exist."""


class UnknownImplementationThemeError(SynthesisError):
    """A narrative referenced an implementation theme id that doesn't exist."""


class MissingTraceabilityError(SynthesisError):
    """Raised when a synthesis node is constructed with no supporting
    reference to the layer beneath it — "every recommendation must originate
    from findings; every finding must originate from evidence" is a hard
    invariant, not a lint, the same principled exception to "never raise"
    ``app.consulting.tracking`` already carved out for evidence-linkage."""
