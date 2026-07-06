"""M2-S2 vault-wide validator tests — one deterministic test per rule.

No randomness, no network; the filesystem is used only via pytest ``tmp_path``
fixtures. Notes are rendered from dicts to a YAML frontmatter block + body.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from knowledge import (
    EXPECTED_CATEGORY_DIRS,
    ValidationSeverity,
    validate_vault,
)


def _render(fields: dict[str, Any], body: str = "body text") -> str:
    return f"---\n{yaml.safe_dump(fields, sort_keys=False)}---\n{body}\n"


def _base(id_: str, type_: str, title: str, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": id_,
        "type": type_,
        "title": title,
        "source": "ADR test fixture",
        "last_verified": "2026-01-01",
        "status": "draft",
        "visibility": "global",
    }
    base.update(extra)
    return base


def _write(vault: Path, rel: str, fields: dict[str, Any], body: str = "body") -> None:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render(fields, body), encoding="utf-8")


def _make_all_dirs(vault: Path) -> None:
    for name in EXPECTED_CATEGORY_DIRS:
        (vault / name).mkdir(parents=True, exist_ok=True)


def _framework_fields(
    id_: str, title: str, domains: list[str], tier: str = "primary"
) -> dict[str, Any]:
    return _base(
        id_,
        "framework",
        title,
        name=title,
        domains=domains,
        tier=tier,
        purpose="p",
        when_to_use="w",
        diagnostic_questions=["q?"],
        success_metrics=["m"],
        common_risks=["r"],
        common_mistakes=["mm"],
        related_frameworks=[],
        version="1.0",
    )


def _rules(report: Any) -> set[str]:
    return {issue.rule for issue in report.issues}


# --- entry point / directory ---------------------------------------------------


def test_not_a_directory_is_error(tmp_path: Path) -> None:
    report = validate_vault(tmp_path / "does-not-exist")
    assert report.note_count == 0
    assert not report.is_valid
    assert _rules(report) == {"vault_directory"}


def test_present_empty_vault_has_no_errors(tmp_path: Path) -> None:
    _make_all_dirs(tmp_path)
    report = validate_vault(tmp_path)
    assert report.note_count == 0
    assert report.is_valid  # only warnings (all 15 domains missing)
    assert "missing_directory" not in _rules(report)
    assert len([i for i in report.warnings if i.rule == "missing_domain"]) == 15


# --- per-note validation propagation ------------------------------------------


def test_invalid_frontmatter_note_is_error(tmp_path: Path) -> None:
    fields = _base("k1", "kpi", "K1")
    del fields["source"]  # missing required field
    _write(tmp_path, "kpis/k1.md", fields)
    report = validate_vault(tmp_path)
    assert not report.is_valid
    assert "frontmatter" in _rules(report)


def test_valid_note_produces_no_error(tmp_path: Path) -> None:
    _make_all_dirs(tmp_path)
    _write(tmp_path, "kpis/k1.md", _base("k1", "kpi", "Operating Margin"))
    report = validate_vault(tmp_path)
    assert report.note_count == 1
    assert report.errors == ()


# --- cross-note rules ---------------------------------------------------------


def test_duplicate_id_is_error(tmp_path: Path) -> None:
    _write(tmp_path, "kpis/a.md", _base("dup", "kpi", "A"))
    _write(tmp_path, "kpis/b.md", _base("dup", "kpi", "B"))
    report = validate_vault(tmp_path)
    assert "duplicate_id" in {i.rule for i in report.errors}


def test_duplicate_alias_is_error(tmp_path: Path) -> None:
    _write(tmp_path, "kpis/a.md", _base("a", "kpi", "A", aliases=["shared"]))
    _write(tmp_path, "kpis/b.md", _base("b", "kpi", "B", aliases=["shared"]))
    report = validate_vault(tmp_path)
    assert "duplicate_alias" in {i.rule for i in report.errors}


def test_broken_wikilink_is_error(tmp_path: Path) -> None:
    _write(tmp_path, "kpis/a.md", _base("a", "kpi", "A"), body="see [[ghost]]")
    report = validate_vault(tmp_path)
    assert "broken_wikilink" in {i.rule for i in report.errors}


def test_resolved_wikilink_ok(tmp_path: Path) -> None:
    _write(tmp_path, "kpis/a.md", _base("a", "kpi", "A"), body="see [[b]]")
    _write(tmp_path, "kpis/b.md", _base("b", "kpi", "B"))
    report = validate_vault(tmp_path)
    assert "broken_wikilink" not in _rules(report)


def test_circular_self_link_is_error(tmp_path: Path) -> None:
    _write(tmp_path, "kpis/a.md", _base("a", "kpi", "A"), body="see [[a]]")
    report = validate_vault(tmp_path)
    assert "circular_self_link" in {i.rule for i in report.errors}


def test_empty_link_target_ignored(tmp_path: Path) -> None:
    # a bare anchor link has no addressable target → neither broken nor circular
    _write(tmp_path, "kpis/a.md", _base("a", "kpi", "A"), body="jump to [[#section]]")
    report = validate_vault(tmp_path)
    assert "broken_wikilink" not in _rules(report)
    assert "circular_self_link" not in _rules(report)


# --- structural / coverage rules ----------------------------------------------


def test_missing_directory_warning(tmp_path: Path) -> None:
    # only one category dir exists → the rest are reported (as warnings)
    (tmp_path / "kpis").mkdir()
    report = validate_vault(tmp_path)
    missing = {i.message for i in report.warnings if i.rule == "missing_directory"}
    assert any("frameworks/" in m for m in missing)
    assert report.is_valid  # missing dirs are warnings, not errors


def test_missing_domain_warning(tmp_path: Path) -> None:
    _make_all_dirs(tmp_path)
    _write(
        tmp_path,
        "domains/profitability.md",
        _base("dom_prof", "domain", "Profitability"),
    )
    report = validate_vault(tmp_path)
    missing = {i.message for i in report.warnings if i.rule == "missing_domain"}
    assert not any("Profitability" in m for m in missing)  # covered
    assert any("Pricing" in m for m in missing)  # not covered


def test_domain_without_primary_framework_warns(tmp_path: Path) -> None:
    _make_all_dirs(tmp_path)
    _write(
        tmp_path,
        "domains/profitability.md",
        _base("dom_prof", "domain", "Profitability"),
    )
    report = validate_vault(tmp_path)
    assert "domain_without_primary_framework" in _rules(report)


def test_domain_with_primary_framework_ok(tmp_path: Path) -> None:
    _make_all_dirs(tmp_path)
    _write(
        tmp_path,
        "domains/profitability.md",
        _base("dom_prof", "domain", "Profitability"),
    )
    _write(
        tmp_path,
        "frameworks/profit-tree.md",
        _framework_fields(
            "fw_pt", "Profit Tree", domains=["[[domains/profitability]]"]
        ),
    )
    report = validate_vault(tmp_path)
    assert "domain_without_primary_framework" not in _rules(report)
    assert "broken_wikilink" not in _rules(report)  # the domain ref resolves


def test_primary_framework_bare_id_ref_ok(tmp_path: Path) -> None:
    # a framework may reference a domain by bare id (no [[ ]]) as well
    _make_all_dirs(tmp_path)
    _write(
        tmp_path,
        "domains/profitability.md",
        _base("dom_prof", "domain", "Profitability"),
    )
    _write(
        tmp_path,
        "frameworks/profit-tree.md",
        _framework_fields("fw_pt", "Profit Tree", domains=["dom_prof"]),
    )
    report = validate_vault(tmp_path)
    assert "domain_without_primary_framework" not in _rules(report)


# --- scoping ------------------------------------------------------------------


def test_excluded_directories_are_skipped(tmp_path: Path) -> None:
    # a malformed note inside an excluded dir must not be validated
    for excluded in ("_attachments", ".obsidian", "graphify-out"):
        (tmp_path / excluded).mkdir()
        (tmp_path / excluded / "junk.md").write_text("not a note", encoding="utf-8")
    report = validate_vault(tmp_path)
    assert report.note_count == 0
    assert "frontmatter" not in _rules(report)


# --- report structure ---------------------------------------------------------


def test_report_partitions_errors_and_warnings(tmp_path: Path) -> None:
    _write(tmp_path, "kpis/a.md", _base("a", "kpi", "A"), body="[[ghost]]")  # error
    report = validate_vault(tmp_path)
    assert all(i.severity is ValidationSeverity.ERROR for i in report.errors)
    assert all(i.severity is ValidationSeverity.WARNING for i in report.warnings)
    assert set(report.issues) == set(report.errors) | set(report.warnings)
    assert not report.is_valid
