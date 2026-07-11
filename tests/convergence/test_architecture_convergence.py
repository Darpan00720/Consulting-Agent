"""RC1.2 architecture-convergence guards (WI-1 & WI-3).

These tests pin the convergence decisions so they cannot silently regress:
one framework source of truth, and mandatory governance gates in every mode.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_FW = _ROOT / "plugins/ruflo-stratagent/knowledge/frameworks"
_VAULT_FW = _ROOT / "knowledge-vault/frameworks"
_AGENTS = _ROOT / "plugins/ruflo-stratagent/agents"
_SKILL = _ROOT / "plugins/ruflo-stratagent/skills/solve-case/SKILL.md"
_ARCH = _ROOT / "docs/architecture"

_STUBBED_ARCHETYPES = [
    "cost-reduction",
    "growth",
    "ma-acquisition",
    "market-entry",
    "new-product-launch",
    "pricing",
    "profitability",
    "turnaround",
    "generic-diagnose-recommend",
]


# ---------------------------------------------------------------------------
# WI-1 — single framework source of truth
# ---------------------------------------------------------------------------


def test_vault_is_the_richer_store() -> None:
    vault_notes = list(_VAULT_FW.glob("*.md"))
    assert len(vault_notes) > len(
        _STUBBED_ARCHETYPES
    ), "vault should hold many more framework notes than the 9 legacy stubs"


def test_migration_index_exists() -> None:
    migration = _PLUGIN_FW / "_MIGRATION.md"
    assert migration.is_file()
    text = migration.read_text(encoding="utf-8")
    assert "knowledge-vault/frameworks/" in text
    assert "single" in text.lower()


@pytest.mark.parametrize("archetype", _STUBBED_ARCHETYPES)
def test_plugin_cheat_sheets_are_redirect_stubs(archetype: str) -> None:
    path = _PLUGIN_FW / f"{archetype}.md"
    assert path.is_file(), "stub must remain for backwards compatibility"
    text = path.read_text(encoding="utf-8")
    assert "DEPRECATED" in text
    assert "knowledge-vault/frameworks/" in text
    # a stub is short — it must not smuggle back framework content
    assert len(text.splitlines()) < 25


def test_classifier_and_strategist_point_to_vault() -> None:
    for agent in ("case-classifier.md", "framework-strategist.md"):
        text = (_AGENTS / agent).read_text(encoding="utf-8")
        assert "knowledge-vault/frameworks/" in text


def test_skill_frameworks_reference_the_vault() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "knowledge-vault/frameworks/" in text


# ---------------------------------------------------------------------------
# WI-3 — mandatory governance gates in every mode
# ---------------------------------------------------------------------------


def test_skill_declares_gates_mandatory() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "Governance gates are mandatory" in text


def test_skill_no_longer_permits_skipping_the_reviewer() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    # the retired lightweight rule skipped straight from a specialist to the
    # challenger; the converged rule must route through the reviewer.
    assert "one specialist →\n  `challenger`" not in text
    assert "never drop the Reviewer or Challenger" in text


def test_adr_006_accepted() -> None:
    adr = _ARCH / "ADR-006-Governance-and-Live-Validation.md"
    assert adr.is_file()
    assert "status: Accepted" in adr.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# WI-2 & WI-4 — ADRs present
# ---------------------------------------------------------------------------


def test_adr_007_evidence_providers_accepted() -> None:
    adr = _ARCH / "ADR-007-Evidence-Providers.md"
    assert adr.is_file()
    assert "status: Accepted" in adr.read_text(encoding="utf-8")


def test_skill_phase8_runs_the_validation_gate() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    assert "scripts/validate_engagement.py" in text
