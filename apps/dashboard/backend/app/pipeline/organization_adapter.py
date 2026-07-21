"""Adapter: `app.pipeline` -> `app.organization` (ADR-014 Phase 2).

Optional, feature-flagged (``config.ORGANIZATION_LAYER_ENABLED``) enrichment
of the planning-phase prompt with `app.organization`'s typed role catalog
(25 roles), supplied **alongside, never replacing**, the planner agent's own
free-text engagement plan. `app.pipeline` has no existing typed team/role
concept to migrate — `ANALYSTS` (engine.py) is a fixed, hardcoded five-name
roster dispatched identically for every engagement, not a dynamic staffing
decision — so this adapter adds a reference the planner can optionally draw
on, exactly as Phase 1 added a framework reference to the framing phase.

Uses ONLY `app.organization`'s public package-level API (``import
app.organization``) — no submodule import, no private symbol, no internal
registry access, per ADR-014 §7.2/§7.4.

**2026-07-19 end-to-end integration validation finding, fixed here:** this
was originally a module-level import, which meant `app.pipeline.engine`
(the production orchestrator) would fail to import at all — not just fail
to enrich the prompt — if `app.organization` ever became unimportable,
even with the feature flag off. Moved inside the function, matching the
lazy-import resilience pattern already established by
`app.memory.checkpoint` and `app.evaluation.ai_evaluation`, and applied
identically to `app.pipeline.knowledge_adapter` in the same pass.

**Deliberately does not call `app.organization.allocation.allocate_team`.**
``allocate_team`` requires a typed ``AllocationContext`` (an
``EngagementCategory`` and a ``ConsultingStage``) that `app.pipeline` has no
way to produce faithfully — it is a pure LLM/free-text system with no
existing case classifier that emits a typed engagement category. Building
one to satisfy `allocate_team`'s signature would be new classification
logic, not an adapter — the same reasoning ADR-014's Phase 1 already applied
to framework-name reconciliation, deliberately preserved here rather than
"fixed." This module supplies additional deterministic reference content
only, via `OrganizationRegistry.list()` — the planning phase and all
downstream analyst-dispatch logic (`ANALYSTS`) are completely unchanged.
"""

from __future__ import annotations


def organization_layer_index() -> str:
    """A deterministic, human-readable index of `app.organization`'s typed
    role catalog — analogous in shape to
    ``app.pipeline.knowledge_adapter.knowledge_library_index()``, but for
    roles instead of frameworks. Never raises: an empty (or unreadable)
    catalog returns an empty string, the same "optional section, silently
    absent if there is nothing to show" convention Phase 1 established."""
    try:
        import app.organization as organization

        registry = organization.default_organization_registry()
        roles = sorted(registry.list(), key=lambda r: r.name)
    except Exception:  # noqa: BLE001 — an optional enrichment must never break planning
        return ""
    return "\n".join(f"- {r.name} ({r.practice.value}): {r.description}" for r in roles)
