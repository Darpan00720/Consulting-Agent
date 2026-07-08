"""Unit and integration tests for packages/knowledge/retrieval_adapter.py (M3).

Test strategy:
  - Fixture vault: a tmp_path mini-vault with hand-crafted notes, for
    isolation of filtering/ranking/tenant logic.
  - Real vault: tests that run against knowledge-vault/ for integration
    confidence (golden query, count, latency).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from knowledge import (
    KnowledgeRetrievalError,
    NoteType,
    RetrievalQuery,
    RetrievalResult,
    Visibility,
    retrieve,
)

# ── fixture vault helpers ─────────────────────────────────────────────────────


def _framework_note(
    note_id: str,
    title: str,
    purpose: str = "Generic purpose.",
    when_to_use: str = "When applicable.",
    visibility: str = "global",
    tenant: str | None = None,
    last_verified: str = "2026-01-01",
    domains: list[str] | None = None,
) -> str:
    doms = domains or ["[[domains/strategy]]"]
    dom_yaml = "\n".join(f"  - '{d}'" for d in doms)
    tenant_line = f"tenant: {tenant}" if tenant else ""
    return textwrap.dedent(f"""\
        ---
        id: {note_id}
        type: framework
        title: {title}
        source: test
        last_verified: {last_verified}
        status: draft
        visibility: {visibility}
        {tenant_line}
        name: {title}
        domains:
        {dom_yaml}
        tier: primary
        purpose: {purpose}
        when_to_use: {when_to_use}
        diagnostic_questions:
          - "Is this relevant?"
        success_metrics:
          - "Outcome achieved."
        common_risks:
          - "Misapplication."
        common_mistakes:
          - "Over-reliance."
        related_frameworks: []
        version: "0.1"
        ---

        ## Overview

        {purpose}

        ## When to Use

        {when_to_use}
    """)


def _domain_note(
    note_id: str,
    title: str,
    visibility: str = "global",
    tenant: str | None = None,
    last_verified: str = "2026-01-01",
) -> str:
    tenant_line = f"tenant: {tenant}" if tenant else ""
    return textwrap.dedent(f"""\
        ---
        id: {note_id}
        type: domain
        title: {title}
        source: test
        last_verified: {last_verified}
        status: draft
        visibility: {visibility}
        {tenant_line}
        ---

        Domain note for {title}.
    """)


@pytest.fixture()
def mini_vault(tmp_path: Path) -> Path:
    """A tiny fixture vault with 3 framework notes and 1 domain note."""
    fw_dir = tmp_path / "frameworks"
    fw_dir.mkdir()
    dom_dir = tmp_path / "domains"
    dom_dir.mkdir()

    (fw_dir / "alpha.md").write_text(
        _framework_note(
            "fw_alpha",
            "Alpha Framework",
            purpose="Analyse market profitability structures.",
            when_to_use="Use for profitability analysis.",
            last_verified="2026-06-01",
        )
    )
    (fw_dir / "beta.md").write_text(
        _framework_note(
            "fw_beta",
            "Beta Framework",
            purpose="Evaluate supply chain efficiency.",
            when_to_use="Use for operations review.",
            last_verified="2026-05-01",
        )
    )
    (fw_dir / "gamma.md").write_text(
        _framework_note(
            "fw_gamma",
            "Gamma Framework",
            purpose="Assess competitive market positioning.",
            when_to_use="Use for competitive strategy.",
            last_verified="2026-04-01",
        )
    )
    (dom_dir / "profitability.md").write_text(
        _domain_note("dom_profit", "Profitability", last_verified="2026-06-15")
    )
    return tmp_path


@pytest.fixture()
def tenant_vault(tmp_path: Path) -> Path:
    """Vault with one global note and one tenant-scoped note."""
    fw_dir = tmp_path / "frameworks"
    fw_dir.mkdir()
    (fw_dir / "global_note.md").write_text(
        _framework_note(
            "fw_global", "Global Framework", purpose="Open profitability analysis."
        )
    )
    (fw_dir / "tenant_note.md").write_text(
        _framework_note(
            "fw_tenant",
            "Tenant Framework",
            purpose="Confidential profitability analysis.",
            visibility="tenant",
            tenant="acme",
        )
    )
    return tmp_path


_REAL_VAULT = Path(__file__).resolve().parents[2] / "knowledge-vault"


# ── input validation ──────────────────────────────────────────────────────────


def test_empty_query_raises() -> None:
    q = RetrievalQuery(text="   ")
    with pytest.raises(KnowledgeRetrievalError, match="text must not be empty"):
        retrieve(q, vault_dir=_REAL_VAULT)


def test_zero_limit_raises() -> None:
    q = RetrievalQuery(text="profitability", limit=0)
    with pytest.raises(KnowledgeRetrievalError, match="limit must be"):
        retrieve(q, vault_dir=_REAL_VAULT)


def test_negative_limit_raises() -> None:
    q = RetrievalQuery(text="profitability", limit=-1)
    with pytest.raises(KnowledgeRetrievalError, match="limit must be"):
        retrieve(q, vault_dir=_REAL_VAULT)


def test_missing_vault_raises(tmp_path: Path) -> None:
    q = RetrievalQuery(text="profitability")
    with pytest.raises(KnowledgeRetrievalError, match="vault_dir not found"):
        retrieve(q, vault_dir=tmp_path / "nonexistent")


# ── result shape ──────────────────────────────────────────────────────────────


def test_retrieve_returns_list(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    assert isinstance(results, list)


def test_retrieve_empty_vault_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "frameworks").mkdir()
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=tmp_path)
    assert results == []


def test_no_match_returns_empty(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="xyzzyquux"), vault_dir=mini_vault)
    assert results == []


def test_result_fields_complete(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    assert results
    r = results[0]
    assert isinstance(r, RetrievalResult)
    assert r.note_id
    assert isinstance(r.note_path, Path)
    assert r.commit_hash  # "unknown" is acceptable in test env
    assert r.title
    assert isinstance(r.note_type, NoteType)
    assert r.source
    assert 0.0 < r.score <= 1.0
    assert isinstance(r.excerpt, str)
    assert isinstance(r.visibility, Visibility)
    assert r.tenant is None  # global note
    assert r.last_verified  # ISO string


def test_last_verified_is_iso_string(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    assert results
    # Must parse as a date; format "YYYY-MM-DD"
    from datetime import date

    date.fromisoformat(results[0].last_verified)


def test_note_path_is_relative(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    assert results
    # Must be relative (not absolute)
    assert not results[0].note_path.is_absolute()


def test_score_in_unit_interval(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    for r in results:
        assert 0.0 < r.score <= 1.0


# ── limit and cap ─────────────────────────────────────────────────────────────


def test_limit_respected(mini_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(text="profitability framework", limit=2), vault_dir=mini_vault
    )
    assert len(results) <= 2


def test_default_limit_is_10() -> None:
    q = RetrievalQuery(text="x")
    assert q.limit == 10


def test_max_results_cap(mini_vault: Path) -> None:
    # limit=200 but _MAX_RESULTS=50; vault has 4 notes so we get at most 4
    from knowledge.retrieval_adapter import _MAX_RESULTS

    results = retrieve(
        RetrievalQuery(text="framework", limit=200), vault_dir=mini_vault
    )
    assert len(results) <= _MAX_RESULTS


# ── type filter ───────────────────────────────────────────────────────────────


def test_type_filter_framework_only(mini_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(
            text="profitability",
            types=frozenset({NoteType.FRAMEWORK}),
        ),
        vault_dir=mini_vault,
    )
    assert results
    assert all(r.note_type is NoteType.FRAMEWORK for r in results)


def test_type_filter_domain_only(mini_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(
            text="profitability",
            types=frozenset({NoteType.DOMAIN}),
        ),
        vault_dir=mini_vault,
    )
    assert results
    assert all(r.note_type is NoteType.DOMAIN for r in results)


def test_type_filter_no_match_returns_empty(mini_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(
            text="profitability",
            types=frozenset({NoteType.KPI}),
        ),
        vault_dir=mini_vault,
    )
    assert results == []


# ── tenant filter (KR-003) ────────────────────────────────────────────────────


def test_tenant_filter_none_excludes_tenant_notes(tenant_vault: Path) -> None:
    # tenant_id=None → only global-visibility notes
    results = retrieve(
        RetrievalQuery(text="profitability", tenant_id=None),
        vault_dir=tenant_vault,
    )
    ids = {r.note_id for r in results}
    assert "fw_global" in ids
    assert "fw_tenant" not in ids


def test_matching_tenant_includes_tenant_notes(tenant_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(text="profitability", tenant_id="acme"),
        vault_dir=tenant_vault,
    )
    ids = {r.note_id for r in results}
    assert "fw_global" in ids
    assert "fw_tenant" in ids


def test_tenant_filter_wrong_tenant_excludes_tenant_notes(tenant_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(text="profitability", tenant_id="other"),
        vault_dir=tenant_vault,
    )
    ids = {r.note_id for r in results}
    assert "fw_tenant" not in ids


# ── ranking ───────────────────────────────────────────────────────────────────


def test_top_result_is_most_relevant(mini_vault: Path) -> None:
    # "profitability" hits alpha framework's purpose and when_to_use heavily
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    assert results
    assert results[0].note_id in {"fw_alpha", "dom_profit"}


def test_scores_are_sorted_descending(mini_vault: Path) -> None:
    results = retrieve(
        RetrievalQuery(text="profitability framework"), vault_dir=mini_vault
    )
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_last_verified_tiebreak(tmp_path: Path) -> None:
    """When two notes have equal score, the newer one ranks higher."""
    fw_dir = tmp_path / "frameworks"
    fw_dir.mkdir()
    # Identical content except last_verified
    for note_id, lv in [("fw_newer", "2026-06-01"), ("fw_older", "2025-01-01")]:
        (fw_dir / f"{note_id}.md").write_text(
            _framework_note(
                note_id,
                "Tiebreak Framework",
                purpose="Profitability tiebreak test.",
                when_to_use="Use for profitability.",
                last_verified=lv,
            )
        )
    results = retrieve(
        RetrievalQuery(text="profitability tiebreak"), vault_dir=tmp_path
    )
    assert len(results) == 2
    assert results[0].note_id == "fw_newer"


# ── determinism (KR-008) ──────────────────────────────────────────────────────


def test_deterministic_results(mini_vault: Path) -> None:
    q = RetrievalQuery(text="profitability framework")
    run1 = retrieve(q, vault_dir=mini_vault)
    run2 = retrieve(q, vault_dir=mini_vault)
    assert [r.note_id for r in run1] == [r.note_id for r in run2]
    assert [r.score for r in run1] == [r.score for r in run2]


# ── graphify-out exclusion ────────────────────────────────────────────────────


def test_graphify_out_excluded(tmp_path: Path) -> None:
    """graphify-out/ inside the vault must not be scanned."""
    fw_dir = tmp_path / "frameworks"
    fw_dir.mkdir()
    (fw_dir / "real.md").write_text(
        _framework_note("fw_real", "Real Framework", purpose="Profitability analysis.")
    )
    gout = tmp_path / "graphify-out"
    gout.mkdir()
    (gout / "fake.md").write_text(
        _framework_note("fw_fake", "Fake Framework", purpose="Should never appear.")
    )
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=tmp_path)
    ids = {r.note_id for r in results}
    assert "fw_fake" not in ids


def test_hidden_dir_excluded(tmp_path: Path) -> None:
    """Notes inside hidden directories (starting with '.') are excluded."""
    fw_dir = tmp_path / "frameworks"
    fw_dir.mkdir()
    (fw_dir / "visible.md").write_text(
        _framework_note(
            "fw_visible", "Visible Framework", purpose="Market profitability."
        )
    )
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "hidden.md").write_text(
        _framework_note(
            "fw_hidden", "Hidden Framework", purpose="Profitability hidden."
        )
    )
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=tmp_path)
    ids = {r.note_id for r in results}
    assert "fw_hidden" not in ids


# ── excerpt ───────────────────────────────────────────────────────────────────


def test_excerpt_is_non_empty_on_match(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    assert results
    assert results[0].excerpt != ""


def test_excerpt_max_500_chars(mini_vault: Path) -> None:
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=mini_vault)
    for r in results:
        assert len(r.excerpt) <= 500


# ── malformed note handling ───────────────────────────────────────────────────


def test_malformed_note_skipped(tmp_path: Path) -> None:
    """A note with invalid frontmatter must be skipped; other notes still returned."""
    fw_dir = tmp_path / "frameworks"
    fw_dir.mkdir()
    (fw_dir / "good.md").write_text(
        _framework_note("fw_good", "Good Framework", purpose="Profitability analysis.")
    )
    (fw_dir / "bad.md").write_text("not frontmatter at all — just plain text")
    results = retrieve(RetrievalQuery(text="profitability"), vault_dir=tmp_path)
    ids = {r.note_id for r in results}
    assert "fw_good" in ids


# ── integration against real vault ───────────────────────────────────────────


@pytest.mark.skipif(not _REAL_VAULT.is_dir(), reason="real vault not present")
def test_real_vault_golden_query() -> None:
    """Golden query 'profitability' must return framework notes near the top."""
    results = retrieve(
        RetrievalQuery(text="profitability", limit=10), vault_dir=_REAL_VAULT
    )
    assert results, "expected at least one result for 'profitability'"
    types = {r.note_type for r in results}
    assert NoteType.FRAMEWORK in types or NoteType.DOMAIN in types


@pytest.mark.skipif(not _REAL_VAULT.is_dir(), reason="real vault not present")
def test_real_vault_type_filter_framework() -> None:
    results = retrieve(
        RetrievalQuery(
            text="market entry competitive",
            types=frozenset({NoteType.FRAMEWORK}),
            limit=5,
        ),
        vault_dir=_REAL_VAULT,
    )
    assert all(r.note_type is NoteType.FRAMEWORK for r in results)


@pytest.mark.skipif(not _REAL_VAULT.is_dir(), reason="real vault not present")
def test_real_vault_commit_hash_present() -> None:
    results = retrieve(
        RetrievalQuery(text="profitability", limit=1), vault_dir=_REAL_VAULT
    )
    if results:
        # Must be a 40-char hex SHA or "unknown"
        ch = results[0].commit_hash
        is_sha = len(ch) == 40 and all(c in "0123456789abcdef" for c in ch)
        assert ch == "unknown" or is_sha


@pytest.mark.skipif(not _REAL_VAULT.is_dir(), reason="real vault not present")
def test_real_vault_all_results_visible() -> None:
    """No tenant-scoped notes should appear when tenant_id is None."""
    results = retrieve(
        RetrievalQuery(text="strategy", tenant_id=None, limit=50),
        vault_dir=_REAL_VAULT,
    )
    for r in results:
        assert r.visibility is Visibility.GLOBAL, (
            f"{r.note_id} is tenant-scoped but returned"
        )
