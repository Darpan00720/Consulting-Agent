"""M2-S3 authored-content tests — validate the real knowledge-vault/.

Proves the draft domain + framework notes authored in S3 validate cleanly, the
vault has no errors, ADR-004 domain coverage is satisfied, and there are no
dangling links or duplicate ids. Read-only over the committed vault; no
authoring, no fixtures.
"""

from __future__ import annotations

from pathlib import Path

from knowledge import NoteType, validate_note, validate_vault

_VAULT = Path(__file__).resolve().parents[2] / "knowledge-vault"


def _notes() -> list[Path]:
    """Every knowledge note, mirroring the validator's scoping exclusions."""
    return [
        p
        for p in sorted(_VAULT.rglob("*.md"))
        if not any(
            part.startswith((".", "_")) or part == "graphify-out"
            for part in p.relative_to(_VAULT).parts
        )
    ]


def test_vault_directory_exists() -> None:
    assert _VAULT.is_dir()


def test_vault_validates_without_errors() -> None:
    report = validate_vault(_VAULT)
    assert report.errors == ()
    assert report.is_valid


def test_every_note_validates_and_is_draft() -> None:
    notes = _notes()
    assert notes  # the vault is populated
    for path in notes:
        note = validate_note(path.read_text(encoding="utf-8"))
        assert note.status.value == "draft"  # S3 authors drafts only (D-6)


def test_s3_authored_15_domains_and_15_primary_frameworks() -> None:
    domains = list((_VAULT / "domains").glob("*.md"))
    frameworks = list((_VAULT / "frameworks").glob("*.md"))
    assert len(domains) == 15  # one per ADR-004 §2 domain
    assert len(frameworks) >= 15  # >= 1 primary framework per domain
    for path in domains:
        assert validate_note(path.read_text(encoding="utf-8")).type is NoteType.DOMAIN


def test_all_required_domains_are_covered() -> None:
    report = validate_vault(_VAULT)
    assert [i for i in report.warnings if i.rule == "missing_domain"] == []


def test_every_domain_has_a_primary_framework() -> None:
    report = validate_vault(_VAULT)
    assert [
        i for i in report.warnings if i.rule == "domain_without_primary_framework"
    ] == []


def test_no_broken_wikilinks() -> None:
    report = validate_vault(_VAULT)
    assert [i for i in report.issues if i.rule == "broken_wikilink"] == []


def test_no_circular_self_links() -> None:
    report = validate_vault(_VAULT)
    assert [i for i in report.issues if i.rule == "circular_self_link"] == []


def test_no_duplicate_ids() -> None:
    report = validate_vault(_VAULT)
    assert [i for i in report.issues if i.rule == "duplicate_id"] == []


def test_no_duplicate_aliases() -> None:
    report = validate_vault(_VAULT)
    assert [i for i in report.issues if i.rule == "duplicate_alias"] == []
