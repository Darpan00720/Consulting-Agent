"""M2-S5 API freeze: the knowledge package public surface is pinned exactly.

Mirrors the persistence and replay freeze tests. These tests fail the moment
the surface drifts — a new/renamed export, a changed signature, a redefined
type, or a dropped model. Behaviour is exercised in test_frontmatter.py and
test_vault_validator.py; here we pin *shape* only.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import knowledge as knowledge_pkg
from common.errors import StratAgentError
from knowledge import (
    CommonHeader,
    FrameworkNote,
    FrontmatterError,
    NoteStatus,
    NoteType,
    ValidationIssue,
    ValidationSeverity,
    VaultReport,
    parse_frontmatter,
    validate_note,
    validate_vault,
)

# Exactly 28 symbols — any addition, removal, or rename fails this set.
_FROZEN_ALL: frozenset[str] = frozenset(
    {
        "EXPECTED_CATEGORY_DIRS",
        "REQUIRED_DOMAINS",
        "BusinessProblemNote",
        "CommonHeader",
        "CompanyNote",
        "DeliverableKind",
        "DeliverableNote",
        "DomainNote",
        "FrameworkNote",
        "FrameworkTier",
        "FrontmatterError",
        "IndustryNote",
        "IssueTreeNote",
        "KpiNote",
        "LessonNote",
        "NoteStatus",
        "NoteType",
        "PlaybookNote",
        "PriorCaseNote",
        "RecommendationNote",
        "TemplateNote",
        "ValidationIssue",
        "ValidationSeverity",
        "VaultReport",
        "Visibility",
        "parse_frontmatter",
        "validate_note",
        "validate_vault",
    }
)


def test_public_all_is_frozen() -> None:
    assert set(knowledge_pkg.__all__) == _FROZEN_ALL
    assert len(knowledge_pkg.__all__) == len(set(knowledge_pkg.__all__))  # no dups
    for name in knowledge_pkg.__all__:
        assert hasattr(knowledge_pkg, name), f"__all__ entry missing attribute: {name}"


def test_frozen_all_has_exact_count() -> None:
    assert len(_FROZEN_ALL) == 28


def test_note_type_values_are_frozen() -> None:
    expected = {
        "framework",
        "playbook",
        "industry",
        "company",
        "kpi",
        "prior_case",
        "lesson",
        "template",
        "domain",
        "issue_tree",
        "deliverable",
        "business_problem",
        "recommendation",
    }
    assert {t.value for t in NoteType} == expected
    assert len(NoteType) == 13


def test_note_status_values_are_frozen() -> None:
    assert {s.value for s in NoteStatus} == {"approved", "draft"}
    assert len(NoteStatus) == 2


def test_validation_severity_values_are_frozen() -> None:
    assert {s.value for s in ValidationSeverity} == {"error", "warning"}
    assert len(ValidationSeverity) == 2


def test_validate_note_signature_is_frozen() -> None:
    sig = inspect.signature(validate_note)
    assert list(sig.parameters) == ["text"]
    hints = get_type_hints(validate_note)
    assert hints["text"] is str
    assert hints["return"] is CommonHeader


def test_validate_vault_signature_is_frozen() -> None:
    sig = inspect.signature(validate_vault)
    assert list(sig.parameters) == ["vault_dir"]
    hints = get_type_hints(validate_vault)
    assert hints["vault_dir"] is Path
    assert hints["return"] is VaultReport


def test_parse_frontmatter_signature_is_frozen() -> None:
    sig = inspect.signature(parse_frontmatter)
    assert list(sig.parameters) == ["text"]
    hints = get_type_hints(parse_frontmatter)
    assert hints["text"] is str
    # return type is dict[str, object] — verify it is a dict annotation
    ret = hints["return"]
    assert getattr(ret, "__origin__", None) is dict


def test_vault_report_api_surface_is_frozen() -> None:
    # Dataclass fields: in __dataclass_fields__; properties: on the class.
    for field in ("issues", "note_count"):
        assert (
            field in VaultReport.__dataclass_fields__
        ), f"VaultReport missing field: {field}"
    for prop in ("errors", "warnings", "is_valid"):
        assert hasattr(VaultReport, prop), f"VaultReport missing property: {prop}"


def test_validation_issue_api_surface_is_frozen() -> None:
    # ValidationIssue is a frozen dataclass — all four are dataclass fields.
    for field in ("rule", "severity", "message", "note"):
        assert (
            field in ValidationIssue.__dataclass_fields__
        ), f"ValidationIssue missing field: {field}"


def test_frontmatter_error_hierarchy_is_frozen() -> None:
    assert issubclass(FrontmatterError, StratAgentError)


def test_framework_note_required_fields_are_frozen() -> None:
    required = {
        "name",
        "domains",
        "tier",
        "purpose",
        "when_to_use",
        "diagnostic_questions",
        "success_metrics",
        "common_risks",
        "common_mistakes",
        "related_frameworks",
        "version",
    }
    assert required <= set(FrameworkNote.model_fields.keys())


def test_common_header_required_fields_are_frozen() -> None:
    required = {
        "id",
        "type",
        "title",
        "source",
        "last_verified",
        "status",
        "visibility",
    }
    assert required <= set(CommonHeader.model_fields.keys())


def test_validate_note_raises_frontmatter_error_on_invalid() -> None:
    try:
        validate_note("no frontmatter here")
        raise AssertionError("expected FrontmatterError")
    except FrontmatterError:
        pass


def test_validate_vault_returns_vault_report() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        report = validate_vault(Path(tmp))
        assert isinstance(report, VaultReport)
        assert isinstance(report.note_count, int)
        assert isinstance(report.is_valid, bool)
        assert isinstance(report.errors, tuple)
        assert isinstance(report.warnings, tuple)
