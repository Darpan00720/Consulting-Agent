"""Governance-phase section models (ADR-002 §20–§21)."""

from __future__ import annotations

from common.models import DomainObject
from state.sections.enums import (
    ChallengeVerdict,
    CheckResult,
    ReviewCheckName,
    ReviewVerdict,
)


class ReviewCheck(DomainObject):
    """A single reviewer check result (ADR-002 §20)."""

    name: ReviewCheckName
    result: CheckResult
    detail: str | None = None


class ReviewerNotes(DomainObject):
    """ADR-002 §20 — Reviewer Notes."""

    checks: list[ReviewCheck] = []
    verdict: ReviewVerdict | None = None
    issues: list[str] = []


class ChallengeNotes(DomainObject):
    """ADR-002 §21 — Challenge Notes."""

    loadbearing_test: str | None = None
    counter_case: str | None = None
    what_would_change: list[str] = []
    verdict: ChallengeVerdict | None = None
