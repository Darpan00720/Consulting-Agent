"""Consulting Workflow Engine error hierarchy.

Mirrors the typed-error discipline every lower platform layer already commits
to (``app.agents.errors``, ``app.memory.errors``, ``app.tools.errors``) — one
base class, narrow subclasses per failure mode.

**Deliberate exception to "never raise" (documented, not accidental):** every
lower platform layer reports failures as a result object rather than raising,
because those are INFRASTRUCTURE failure modes (a provider is down, a target
timed out) that a caller must always be able to handle without a try/except.
``MissingEvidenceError``/``UnknownEvidenceError`` are different in kind — they
guard a DOMAIN invariant the requester explicitly mandated ("No recommendation
should be generated without supporting evidence", "No unsupported findings").
Silently returning a "failed" recommendation object would let a caller ignore
the return value and treat an unsupported claim as if it were valid; raising
is the one place in this platform where refusing outright is the correct
behavior, the same principled asymmetry ``app.tools.permissions`` already
established for fail-closed permission decisions.
"""

from __future__ import annotations


class ConsultingError(Exception):
    """Base class for every Consulting Workflow Engine error."""


class UnknownWorkflowError(ConsultingError):
    """No workflow registered under the given id/version."""


class DuplicateWorkflowError(ConsultingError):
    """A workflow with this (id, version) is already registered."""


class UnknownEngagementError(ConsultingError):
    """No engagement state exists for the given engagement_id."""


class UnknownHypothesisError(ConsultingError):
    """The referenced hypothesis_id does not exist in this engagement."""


class UnknownAssumptionError(ConsultingError):
    """The referenced assumption_id does not exist in this engagement."""


class UnknownEvidenceError(ConsultingError):
    """A recommendation/hypothesis referenced an evidence_id that doesn't exist —
    the referential-integrity half of "no unsupported findings"."""


class MissingEvidenceError(ConsultingError):
    """A recommendation (or a hypothesis confirm/reject) was attempted with zero
    supporting evidence — the hard-invariant half of "no unsupported findings"."""


class QualityGateBlocked(ConsultingError):
    """Raised only by callers that opt into strict advancement; the engine's own
    ``advance_stage`` does NOT raise this — it reports a blocked
    ``QualityGateResult`` instead, consistent with the rest of the platform's
    "report, don't raise" discipline for a normal, expected outcome (a gate
    failing is not exceptional — an engagement stalling on evidence is the
    everyday case this whole system exists to catch)."""
