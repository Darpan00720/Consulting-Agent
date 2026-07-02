"""M1.6 runner tests: ValidationReport semantics and raise_if_invalid."""

from __future__ import annotations

import pytest

from state.models import EngagementMetadata, EngagementState
from state.sections.planning import IssueNode
from state.validation import (
    StateValidationError,
    ValidationGroup,
    ViolationSeverity,
    raise_if_invalid,
    validate,
)


def _bare() -> EngagementState:
    return EngagementState(
        metadata=EngagementMetadata(engagement_id="e", tenant_id="t", slug="s")
    )


def _invalid() -> EngagementState:
    # An issue-tree leaf without an owner triggers STRUCT-001 (ERROR).
    return EngagementState(
        metadata=EngagementMetadata(engagement_id="e", tenant_id="t", slug="s"),
        issue_tree=[IssueNode(question="q")],
    )


def test_valid_state_report() -> None:
    report = validate(_bare())
    assert report.valid
    assert report.violations == []
    assert set(report.groups_checked) == set(ValidationGroup)
    assert report.duration_ms >= 0.0
    assert sum(report.counts.values()) == 0


def test_invalid_state_report() -> None:
    report = validate(_invalid())
    assert not report.valid
    assert report.counts[ViolationSeverity.ERROR] >= 1
    assert sum(report.counts.values()) == len(report.violations)


def test_every_violation_has_context() -> None:
    report = validate(_invalid())
    for violation in report.violations:
        assert violation.rule_id
        assert violation.severity
        assert violation.path
        assert violation.message  # object_id may legitimately be None


def test_raise_if_invalid() -> None:
    raise_if_invalid(_bare())  # must not raise
    with pytest.raises(StateValidationError):
        raise_if_invalid(_invalid())
