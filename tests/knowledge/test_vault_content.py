"""M2-S3/S4A authored-content tests — validate the real knowledge-vault/.

S3 proves: draft domain + framework notes validate cleanly, vault has no errors,
ADR-004 domain coverage satisfied, no dangling links, no duplicate ids.

S4A proves: supporting frameworks (all 48, tier=supporting), issue trees (15,
one per domain), and business problem notes (15, one per domain) are present,
valid, linked correctly, and free of broken wikilinks or duplicate ids.

Read-only over the committed vault; no authoring, no fixtures.
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


# ── M2-S4A content tests ───────────────────────────────────────────────────


def test_s4a_supporting_frameworks_authored() -> None:
    from knowledge import FrameworkNote, NoteType

    supporting = [
        path
        for path in sorted((_VAULT / "frameworks").glob("*.md"))
        if (
            lambda n: (
                n.type is NoteType.FRAMEWORK
                and isinstance(n, FrameworkNote)
                and n.tier.value == "supporting"
            )
        )(validate_note(path.read_text(encoding="utf-8")))
    ]
    assert len(supporting) == 48  # one per ADR-004 §3 supporting framework entry


def test_s4a_issue_trees_authored() -> None:
    it_dir = _VAULT / "issue-trees"
    assert it_dir.is_dir(), "issue-trees/ directory missing"
    issue_trees = list(it_dir.glob("*.md"))
    assert len(issue_trees) == 15  # one per ADR-004 §4 domain


def test_s4a_business_problems_authored() -> None:
    bp_dir = _VAULT / "business-problems"
    assert bp_dir.is_dir(), "business-problems/ directory missing"
    bps = list(bp_dir.glob("*.md"))
    assert len(bps) == 15  # one per ADR-004 §2 domain


def test_all_s4a_notes_are_draft() -> None:
    s4a_dirs = ["issue-trees", "business-problems"]
    for dir_name in s4a_dirs:
        for path in (_VAULT / dir_name).glob("*.md"):
            note = validate_note(path.read_text(encoding="utf-8"))
            assert note.status.value == "draft", f"{path.name} must be draft"


def test_all_supporting_frameworks_are_draft() -> None:
    from knowledge import FrameworkNote, NoteType

    for path in sorted((_VAULT / "frameworks").glob("*.md")):
        note = validate_note(path.read_text(encoding="utf-8"))
        if (
            note.type is NoteType.FRAMEWORK
            and isinstance(note, FrameworkNote)
            and note.tier.value == "supporting"
        ):
            assert note.status.value == "draft", f"{path.name} must be draft"


def test_issue_trees_link_to_domains() -> None:
    import re

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    for path in sorted((_VAULT / "issue-trees").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        has_domain_link = any(
            "domains/" in m.group(1) for m in wikilink_re.finditer(text)
        )
        assert has_domain_link, f"{path.name} must contain a [[domains/...]] wikilink"


def test_business_problems_link_to_issue_trees() -> None:
    import re

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    for path in sorted((_VAULT / "business-problems").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        has_it_link = any(
            "issue-trees/" in m.group(1) for m in wikilink_re.finditer(text)
        )
        assert has_it_link, f"{path.name} must link to an [[issue-trees/...]] note"


def test_business_problems_link_to_domains() -> None:
    import re

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    for path in sorted((_VAULT / "business-problems").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        has_domain_link = any(
            "domains/" in m.group(1) for m in wikilink_re.finditer(text)
        )
        assert has_domain_link, f"{path.name} must link to a [[domains/...]] note"


def test_missing_directory_warnings_reduced_after_s4a() -> None:
    report = validate_vault(_VAULT)
    missing = {i.message for i in report.warnings if i.rule == "missing_directory"}
    assert not any(
        "issue-trees/" in m for m in missing
    ), "issue-trees/ dir should exist after S4A"
    assert not any(
        "business-problems/" in m for m in missing
    ), "business-problems/ dir should exist after S4A"
    assert len(missing) == 3  # only deliverables, prior-cases, recommendations


# ── M2-S4B content tests ───────────────────────────────────────────────────


def test_s4b_kpi_catalog_authored() -> None:
    kpi_dir = _VAULT / "kpis"
    assert kpi_dir.is_dir(), "kpis/ directory missing"
    kpis = list(kpi_dir.glob("*.md"))
    assert len(kpis) == 14  # per ADR-004 §5 canonical catalog


def test_s4b_industry_catalog_authored() -> None:
    ind_dir = _VAULT / "industries"
    assert ind_dir.is_dir(), "industries/ directory missing"
    industries = list(ind_dir.glob("*.md"))
    assert len(industries) == 10  # per ADR-004 §6 industry model


def test_all_kpi_notes_are_draft() -> None:
    for path in (_VAULT / "kpis").glob("*.md"):
        note = validate_note(path.read_text(encoding="utf-8"))
        assert note.status.value == "draft", f"{path.name} must be draft"


def test_all_industry_notes_are_draft() -> None:
    for path in (_VAULT / "industries").glob("*.md"):
        note = validate_note(path.read_text(encoding="utf-8"))
        assert note.status.value == "draft", f"{path.name} must be draft"


def test_kpi_notes_correct_type() -> None:
    for path in (_VAULT / "kpis").glob("*.md"):
        note = validate_note(path.read_text(encoding="utf-8"))
        assert note.type is NoteType.KPI, f"{path.name} must have type=kpi"


def test_industry_notes_correct_type() -> None:
    for path in (_VAULT / "industries").glob("*.md"):
        note = validate_note(path.read_text(encoding="utf-8"))
        assert note.type is NoteType.INDUSTRY, f"{path.name} must have type=industry"


def test_kpi_notes_link_to_domains() -> None:
    import re

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    for path in sorted((_VAULT / "kpis").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        has_domain_link = any(
            "domains/" in m.group(1) for m in wikilink_re.finditer(text)
        )
        assert has_domain_link, f"{path.name} must contain a [[domains/...]] wikilink"


def test_industry_notes_link_to_domains() -> None:
    import re

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    for path in sorted((_VAULT / "industries").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        has_domain_link = any(
            "domains/" in m.group(1) for m in wikilink_re.finditer(text)
        )
        assert has_domain_link, f"{path.name} must contain a [[domains/...]] wikilink"


def test_ltv_cac_links_component_kpis() -> None:
    import re

    wikilink_re = re.compile(r"\[\[([^\]]+)\]\]")
    ltv_cac = (_VAULT / "kpis" / "ltv-cac-ratio.md").read_text(encoding="utf-8")
    links = {m.group(1).split("|")[0] for m in wikilink_re.finditer(ltv_cac)}
    assert any("kpis/ltv" in lk for lk in links), "ltv-cac-ratio must link to kpis/ltv"
    assert any("kpis/cac" in lk for lk in links), "ltv-cac-ratio must link to kpis/cac"


def test_total_vault_note_count_after_s4b() -> None:
    assert len(_notes()) == 132  # 108 S3+S4A + 14 KPIs + 10 industries


def test_missing_directory_warnings_unchanged_after_s4b() -> None:
    report = validate_vault(_VAULT)
    missing = {i.message for i in report.warnings if i.rule == "missing_directory"}
    assert not any("kpis/" in m for m in missing), "kpis/ dir should exist after S4B"
    assert not any(
        "industries/" in m for m in missing
    ), "industries/ dir should exist after S4B"
    assert len(missing) == 3  # deliverables, prior-cases, recommendations only
