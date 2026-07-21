"""Tests for the REAL Obsidian vault sync adapter (ADR-013 W5, requirement 8).

Every test uses a pytest ``tmp_path`` vault — genuine filesystem operations
(scan/parse/change-detection), fully isolated from the real
``knowledge-vault/`` and from other tests (the W4 DB-isolation lesson applied
from the start here).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import pytest

from app.tools.adapters import ObsidianSyncAdapter, VaultNote, _parse_frontmatter
from app.tools.models import ToolHealthState, ToolRequest, ToolResponse


def _run(coro):
    return asyncio.run(coro)


def _write_note(vault: object, rel_path: str, content: str) -> None:
    path = vault / rel_path  # type: ignore[operator]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "vault"


# ---- Frontmatter parsing ----------------------------------------------------


def test_parse_frontmatter_extracts_key_value_pairs():
    text = "---\ntitle: Market Entry\nstatus: draft\n---\nBody text here."
    fm, body = _parse_frontmatter(text)
    assert fm == {"title": "Market Entry", "status": "draft"}
    assert body == "Body text here."


def test_parse_frontmatter_handles_quoted_values():
    text = '---\ntitle: "Quoted Title"\n---\nBody.'
    fm, body = _parse_frontmatter(text)
    assert fm["title"] == "Quoted Title"


def test_parse_frontmatter_missing_returns_empty_and_full_text():
    text = "No frontmatter here, just body text."
    fm, body = _parse_frontmatter(text)
    assert fm == {}
    assert body == text


def test_parse_frontmatter_malformed_delimiter_falls_back():
    text = "---\nonly one delimiter, no closing"
    fm, body = _parse_frontmatter(text)
    assert fm == {}


# ---- Vault scan (real filesystem) ------------------------------------------


def test_scan_vault_finds_markdown_files(vault):
    vault.mkdir()
    _write_note(vault, "note1.md", "---\ntitle: A\n---\nBody A")
    _write_note(vault, "sub/note2.md", "---\ntitle: B\n---\nBody B")
    _write_note(vault, "not-markdown.txt", "ignore me")

    adapter = ObsidianSyncAdapter(vault_dir=vault)
    found = adapter.scan_vault()
    assert set(found) == {"note1.md", "sub/note2.md"}


def test_scan_vault_missing_directory_returns_empty():
    adapter = ObsidianSyncAdapter(vault_dir="/nonexistent/vault/path/xyz")
    assert adapter.scan_vault() == ()


def test_scan_vault_empty_directory_returns_empty(vault):
    vault.mkdir()
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    assert adapter.scan_vault() == ()


# ---- Note parsing (real filesystem) ----------------------------------------


def test_parse_note_reads_real_file(vault):
    vault.mkdir()
    _write_note(
        vault, "note.md", "---\ntitle: Test Note\ntype: framework\n---\nThe body."
    )
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    note = adapter.parse_note("note.md")
    assert isinstance(note, VaultNote)
    assert note.frontmatter == {"title": "Test Note", "type": "framework"}
    assert note.body == "The body."
    assert note.mtime > 0


def test_parse_note_missing_file_raises_file_not_found(vault):
    vault.mkdir()
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    with pytest.raises(FileNotFoundError):
        adapter.parse_note("ghost.md")


# ---- Change detection (real mtime) -----------------------------------------


def test_detect_changes_finds_new_notes(vault):
    vault.mkdir()
    _write_note(vault, "note1.md", "content")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    assert adapter.detect_changes() == ("note1.md",)


def test_detect_changes_empty_after_sync(vault):
    vault.mkdir()
    _write_note(vault, "note1.md", "content")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    adapter.sync()  # advances the baseline
    assert adapter.detect_changes() == ()


def test_detect_changes_finds_modified_note_after_sync(vault):
    vault.mkdir()
    _write_note(vault, "note1.md", "v1")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    adapter.sync()
    assert adapter.detect_changes() == ()

    time.sleep(0.01)  # ensure a distinct mtime
    _write_note(vault, "note1.md", "v2 — changed")
    assert adapter.detect_changes() == ("note1.md",)


def test_detect_changes_does_not_flag_untouched_notes(vault):
    vault.mkdir()
    _write_note(vault, "a.md", "a")
    _write_note(vault, "b.md", "b")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    adapter.sync()

    time.sleep(0.01)
    _write_note(vault, "a.md", "a changed")
    assert adapter.detect_changes() == ("a.md",)  # b.md untouched, not flagged


# ---- Sync pipeline ----------------------------------------------------------


def test_sync_returns_parsed_changed_notes(vault):
    vault.mkdir()
    _write_note(vault, "note1.md", "---\ntitle: One\n---\nBody 1")
    _write_note(vault, "note2.md", "---\ntitle: Two\n---\nBody 2")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    notes = adapter.sync()
    assert {n.path for n in notes} == {"note1.md", "note2.md"}
    assert {n.frontmatter["title"] for n in notes} == {"One", "Two"}


def test_sync_only_returns_notes_changed_since_last_sync(vault):
    vault.mkdir()
    _write_note(vault, "note1.md", "v1")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    first = adapter.sync()
    assert len(first) == 1

    second = adapter.sync()  # nothing changed since
    assert second == ()


# ---- Graphify indexing hook (requirement 8) --------------------------------


def test_index_note_placeholder_mode(vault):
    vault.mkdir()
    _write_note(vault, "note.md", "content")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    note = adapter.parse_note("note.md")
    result = _run(adapter.index_note(note))
    assert result.success is True
    assert "graphify" in result.output.lower()


def test_index_note_uses_injected_indexer(vault):
    @dataclass
    class FakeIndexer:
        indexed: list

        async def invoke(self, operation, parameters):
            self.indexed.append(parameters["path"])
            return ToolResponse(success=True, output="indexed")

        async def ping(self):
            return True

    vault.mkdir()
    _write_note(vault, "note.md", "content")
    indexer = FakeIndexer(indexed=[])
    adapter = ObsidianSyncAdapter(vault_dir=vault, graphify_indexer=indexer)
    note = adapter.parse_note("note.md")
    result = _run(adapter.index_note(note))
    assert result.output == "indexed"
    assert indexer.indexed == ["note.md"]


# ---- Tool interface (execute/health/metadata) ------------------------------


def test_execute_scan_vault_operation(vault):
    vault.mkdir()
    _write_note(vault, "note.md", "content")
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    result = _run(adapter.execute(ToolRequest(operation="scan_vault")))
    assert result.success is True
    assert result.output == ("note.md",)


def test_execute_unsupported_operation(vault):
    vault.mkdir()
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    result = _run(adapter.execute(ToolRequest(operation="ghost_op")))
    assert result.success is False


def test_health_reflects_missing_vault():
    adapter = ObsidianSyncAdapter(vault_dir="/nonexistent/vault/xyz")
    result = _run(adapter.health())
    assert result.state is ToolHealthState.UNAVAILABLE


def test_health_reflects_present_vault(vault):
    vault.mkdir()
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    result = _run(adapter.health())
    assert result.state is ToolHealthState.HEALTHY


def test_metadata_declares_sync_read_only_and_index_write(vault):
    adapter = ObsidianSyncAdapter(vault_dir=vault)
    meta = adapter.metadata()
    assert meta.operation_classes["sync"].value == "read-only"
    assert meta.operation_classes["index_note"].value == "write"


def test_obsidian_is_not_a_memory_provider():
    """Requirement 8's own framing: Obsidian is a human knowledge workspace,
    not a runtime memory provider — confirmed structurally: ObsidianSyncAdapter
    satisfies Tool, not MemoryProvider (no store/retrieve/search/update/delete/
    exists methods)."""
    adapter = ObsidianSyncAdapter()
    for method in ("store", "retrieve", "search", "update", "delete", "exists"):
        assert not hasattr(adapter, method)
