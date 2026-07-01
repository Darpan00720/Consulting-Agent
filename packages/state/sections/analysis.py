"""Analysis-phase section models (ADR-002 §15–§19).

All five specialist analyses share the ``AnalysisBlock`` shape.
"""

from __future__ import annotations

from common.models import DomainObject
from common.values import ConfidenceScore, Reference
from state.sections.enums import AnalysisStatus


class Finding(DomainObject):
    """A single specialist finding within an analysis block."""

    question: str
    answer: str | None = None
    method: str | None = None
    evidence_refs: list[Reference] = []
    assumption_refs: list[Reference] = []
    confidence: ConfidenceScore | None = None


class SensitivityCase(DomainObject):
    """A single sensitivity case (a driver stressed to test the answer)."""

    driver: str
    base: str | None = None
    stress: str | None = None
    effect: str | None = None


class AnalysisBlock(DomainObject):
    """ADR-002 §15–§19 — the shared analysis block used by every specialist."""

    owner: str | None = None
    node_refs: list[Reference] = []
    findings: list[Finding] = []
    sensitivity: list[SensitivityCase] = []
    status: AnalysisStatus = AnalysisStatus.PENDING
