"""Adapter: `app.pipeline` -> `app.knowledge` (ADR-014 Phase 1).

Optional, feature-flagged (``config.KNOWLEDGE_LIBRARY_ENABLED``) enrichment
of the framing-phase prompt with `app.knowledge`'s typed framework catalog
(87 frameworks), supplied **alongside, never replacing**, the existing
`knowledge-vault/*.md` index (`app.pipeline.prompts.vault_framework_index`).
These are two different artifacts (see ADR-011's 2026-07-19 note) —
this adapter adds a second, deterministic reference for the framing LLM
call to optionally draw on; it does not touch vault retrieval at all.

Uses ONLY `app.knowledge`'s public package-level API (``import
app.knowledge``) — no submodule import, no private symbol, no internal
registry access, per ADR-014 §7.1/§7.4.

**2026-07-19 end-to-end integration validation finding, fixed here:** this
was originally a module-level import, which meant `app.pipeline.engine`
(the production orchestrator) would fail to import at all — not just fail
to enrich the prompt — if `app.knowledge` ever became unimportable, even
with the feature flag off. Confirmed empirically (stubbing a broken
`app.knowledge` broke `engine.py`'s own import). Moved inside the
function, matching the lazy-import resilience pattern already established
by `app.memory.checkpoint` and `app.evaluation.ai_evaluation`'s own
`app.pipeline.providers` import — so an unimportable `app.knowledge` now
degrades to a caught exception (empty string), never a startup failure.

**Deliberately does not attempt to reconcile which framework(s) the framing
LLM call actually selects against this catalog's ids.** The vault's
filename-based names and this catalog's snake_case ids (e.g.
``porter-five-forces`` vs ``five_forces``) follow different conventions
with no reliable 1:1 mapping; building a fuzzy matcher would be new
judgment logic, not an adapter, and is explicitly out of scope for Phase 1
(see the Phase 1 report's "Integration Design" section for the full
reasoning). This module supplies additional deterministic reference
content only — the framing LLM call and all downstream vault-retrieval
logic (``selected_framework_notes``) are completely unchanged.
"""

from __future__ import annotations


def knowledge_library_index() -> str:
    """A deterministic, human-readable index of `app.knowledge`'s typed
    framework catalog — analogous in shape to
    ``app.pipeline.prompts.vault_framework_index()``, but for the separate
    typed catalog. Never raises: an empty (or unreadable) catalog returns
    an empty string, the same "optional section, silently absent if there
    is nothing to show" convention ``engine.py`` already uses for
    ``knowledge_section``."""
    try:
        import app.knowledge as knowledge

        registry = knowledge.default_framework_registry()
        frameworks = sorted(registry.list(), key=lambda f: f.name)
    except Exception:  # noqa: BLE001 — an optional enrichment must never break framing
        return ""
    return "\n".join(
        f"- {f.name} ({f.category.value}): {f.purpose}" for f in frameworks
    )
