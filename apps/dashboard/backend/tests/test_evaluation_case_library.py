"""Tests for the benchmark case library and its registry: every case's
declared frameworks must be real and engagement-compatible."""

from __future__ import annotations

import pytest

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.errors import DuplicateCaseError, UnknownCaseError
from app.evaluation.registry import CaseRegistry, default_case_registry
from app.knowledge.registry import default_framework_registry


def test_at_least_4_real_benchmark_cases_registered():
    cases = all_benchmark_cases()
    assert len(cases) >= 4
    assert len({c.case_id for c in cases}) == len(cases)


def test_every_expected_framework_is_real_and_engagement_compatible():
    fw_registry = default_framework_registry()
    for case in all_benchmark_cases():
        assert case.expected_frameworks, case.case_id
        for framework_id in case.expected_frameworks:
            framework = fw_registry.get(framework_id)
            assert case.engagement_type in framework.supported_engagements, (
                case.case_id,
                framework_id,
            )


def test_every_case_has_findings_and_recommendations():
    for case in all_benchmark_cases():
        assert case.expected_findings, case.case_id
        assert case.expected_recommendations, case.case_id
        assert case.expected_deliverables, case.case_id


def test_registry_get_returns_latest_version():
    registry = default_case_registry()
    case = registry.get(all_benchmark_cases()[0].case_id)
    assert case.case_id == all_benchmark_cases()[0].case_id


def test_registry_get_unknown_case_raises():
    registry = default_case_registry()
    with pytest.raises(UnknownCaseError):
        registry.get("no-such-case")


def test_registry_rejects_duplicate_case_version():
    registry = CaseRegistry()
    case = all_benchmark_cases()[0]
    registry.register(case)
    with pytest.raises(DuplicateCaseError):
        registry.register(case)


def test_registry_find_by_engagement_and_difficulty():
    registry = default_case_registry()
    case = all_benchmark_cases()[0]
    by_engagement = registry.find_by_engagement(case.engagement_type)
    assert case.case_id in {c.case_id for c in by_engagement}
    by_difficulty = registry.find_by_difficulty(case.difficulty)
    assert case.case_id in {c.case_id for c in by_difficulty}
