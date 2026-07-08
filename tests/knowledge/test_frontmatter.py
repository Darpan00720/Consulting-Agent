"""M2-S1 frontmatter validator core tests.

Deterministic; no filesystem, no clocks. Notes are rendered from dicts to a
YAML frontmatter block + body. Covers the common header (ADR-003 §5/§10), the
ADR-004 §3 framework schema (decision D-7), and the parse/reject paths.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

import knowledge as knowledge_pkg
from knowledge import (
    CommonHeader,
    FrameworkNote,
    FrontmatterError,
    NoteType,
    TemplateNote,
    parse_frontmatter,
    validate_note,
)
from knowledge.frontmatter import MODEL_BY_TYPE


def _render(fields: dict[str, Any]) -> str:
    """A markdown note: YAML frontmatter block + body."""
    return f"---\n{yaml.safe_dump(fields, sort_keys=False)}---\nbody text\n"


def _common(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "kpi_operating_margin",
        "type": "kpi",
        "title": "Operating Margin",
        "source": "ADR-004 §4 KPI catalog",
        "last_verified": "2026-06-28",
        "status": "approved",
        "visibility": "global",
    }
    base.update(overrides)
    return base


def _framework(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "fw_profit_tree",
        "type": "framework",
        "title": "Profit Tree",
        "source": "ADR-004 §3",
        "last_verified": "2026-06-28",
        "status": "draft",
        "visibility": "global",
        "name": "Profit Tree",
        "domains": ["[[domains/profitability]]"],
        "tier": "primary",
        "purpose": "Decompose profit into revenue and cost drivers.",
        "when_to_use": "Any margin or profit-change diagnosis.",
        "diagnostic_questions": ["Is the delta driven by revenue or cost?"],
        "success_metrics": ["[[kpis/operating-margin]]"],
        "common_risks": ["Double-counting drivers."],
        "common_mistakes": ["Ignoring the mix effect."],
        "related_frameworks": [],
        "version": "1.0",
    }
    base.update(overrides)
    return base


# --- happy paths -------------------------------------------------------------


def test_valid_common_note_passes() -> None:
    note = validate_note(_render(_common()))
    assert isinstance(note, CommonHeader)
    assert note.type is NoteType.KPI
    assert note.visibility.value == "global"


def test_valid_framework_note_passes() -> None:
    note = validate_note(_render(_framework()))
    assert isinstance(note, FrameworkNote)
    assert note.tier.value == "primary"
    assert note.domains == ["[[domains/profitability]]"]


def test_valid_tenant_note_passes() -> None:
    note = validate_note(_render(_common(visibility="tenant", tenant="t_meridian")))
    assert note.tenant == "t_meridian"


def test_extra_per_type_fields_allowed() -> None:
    # a kpi's typed fields (validated in a later slice) must not fail the header
    note = validate_note(_render(_common(formula="op_income / revenue", unit="%")))
    assert isinstance(note, CommonHeader)


def test_parse_frontmatter_returns_mapping() -> None:
    data = parse_frontmatter(_render(_common()))
    assert data["type"] == "kpi"


# --- common-header rejections ------------------------------------------------


def test_missing_source_rejected() -> None:
    fields = _common()
    del fields["source"]
    with pytest.raises(FrontmatterError):
        validate_note(_render(fields))


def test_bad_status_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(_render(_common(status="published")))


def test_unknown_type_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(_render(_common(type="bogus")))


def test_tenant_visibility_requires_tenant() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(_render(_common(visibility="tenant")))


def test_global_visibility_forbids_tenant() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(_render(_common(visibility="global", tenant="t_x")))


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(_render(_common(confidence=1.5)))


# --- framework (ADR-004 §3) rejections ---------------------------------------


def test_framework_missing_required_attr_rejected() -> None:
    fields = _framework()
    del fields["diagnostic_questions"]
    with pytest.raises(FrontmatterError):
        validate_note(_render(fields))


def test_framework_empty_content_list_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(_render(_framework(success_metrics=[])))


# --- structural / parse rejections -------------------------------------------


def test_no_frontmatter_block_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note("no frontmatter here\njust body\n")


def test_empty_text_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note("")


def test_unterminated_frontmatter_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note("---\nid: x\ntype: kpi\n")


def test_malformed_yaml_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note("---\nid: [unclosed\n---\nbody\n")


def test_non_mapping_frontmatter_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note("---\n- a\n- b\n---\nbody\n")


def test_empty_mapping_frontmatter_rejected() -> None:
    # an empty YAML block parses to None → not a mapping
    with pytest.raises(FrontmatterError):
        validate_note("---\n\n---\nbody\n")


# --- public surface ----------------------------------------------------------


def test_public_surface() -> None:
    assert set(knowledge_pkg.__all__) == {
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
        "KnowledgeRetrievalError",
        "KpiNote",
        "LessonNote",
        "NoteStatus",
        "NoteType",
        "PlaybookNote",
        "PriorCaseNote",
        "RecommendationNote",
        "RetrievalQuery",
        "RetrievalResult",
        "TemplateNote",
        "ValidationIssue",
        "ValidationSeverity",
        "VaultReport",
        "Visibility",
        "parse_frontmatter",
        "retrieve",
        "validate_note",
        "validate_vault",
    }


# --- S2: per-type models -----------------------------------------------------


def test_every_note_type_has_a_model() -> None:
    # MODEL_BY_TYPE dispatches every one of the 13 note types
    assert set(MODEL_BY_TYPE) == {t.value for t in NoteType}
    for model in MODEL_BY_TYPE.values():
        assert issubclass(model, CommonHeader)


@pytest.mark.parametrize(
    "note_type",
    [t.value for t in NoteType if t is not NoteType.FRAMEWORK],
)
def test_non_framework_types_validate_at_header_level(note_type: str) -> None:
    # every non-framework type validates with just the common header (their
    # per-type fields are optional / unmodelled)
    note = validate_note(_render(_common(id=f"n_{note_type}", type=note_type)))
    assert isinstance(note, MODEL_BY_TYPE[note_type])
    assert note.type.value == note_type


def test_template_valid_deliverable_kind_passes() -> None:
    note = validate_note(
        _render(_common(id="tpl", type="template", deliverable_kind="deck"))
    )
    assert isinstance(note, TemplateNote)
    assert note.deliverable_kind is not None
    assert note.deliverable_kind.value == "deck"


def test_template_invalid_deliverable_kind_rejected() -> None:
    with pytest.raises(FrontmatterError):
        validate_note(
            _render(_common(id="tpl", type="template", deliverable_kind="slides"))
        )
