"""Engagement lifecycle enumerations (ADR-002 §2 Lifecycle Status)."""

from __future__ import annotations

from enum import StrEnum


class LifecycleStatus(StrEnum):
    """The engagement state-machine positions defined in ADR-002 §2."""

    INTAKE = "intake"
    CLASSIFYING = "classifying"
    GAP_ANALYSIS = "gap_analysis"
    PLANNING = "planning"
    FRAMING = "framing"
    ISSUE_TREE = "issue_tree"
    KNOWLEDGE = "knowledge"
    ANALYSIS = "analysis"
    EVIDENCE_VALIDATION = "evidence_validation"
    REVIEW = "review"
    CHALLENGE = "challenge"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
