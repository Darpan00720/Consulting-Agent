# RC1.2 Migration Guide

What changed in the RC1.2 convergence sprint and what (if anything) you must do.

## 1. Framework store → single source of truth

**Before:** frameworks lived in two places — the plugin's
`knowledge/frameworks/*.md` cheat sheets and `knowledge-vault/frameworks/`.

**After:** `knowledge-vault/frameworks/` is canonical. The 9 plugin cheat sheets
are deprecated **redirect stubs**.

**Action required:**
- If your code/agents read a plugin cheat sheet for framework *content*, switch
  to the vault via the Knowledge Agent / `knowledge.retrieve(...)`.
- The archetype → vault-framework index lives at
  `plugins/ruflo-stratagent/knowledge/frameworks/_MIGRATION.md`.
- Old paths still resolve (stubs), so nothing breaks immediately.
- **Note:** `CLAUDE.md`'s "Framework library" line still describes the old
  cheat-sheet model; update it to point at the vault when convenient (left
  unedited here as it is user-owned project instruction).

## 2. Governance gates are mandatory

**Before:** the `solve-case` SKILL allowed a "lightweight" path that skipped the
Reviewer.

**After:** Reviewer **and** Challenger run on every engagement (ADR-006).
"Lightweight" = fewer analysts only.

**Action required:** none for callers. If you built tooling that assumed a
report could exist without `reviewer_notes`, note that the live gate now blocks
that case.

## 3. Live validation gate (Phase 8)

**New:** before a report is produced, the orchestrator emits
`engagements/<slug>/state.json` and runs:

```
uv run python scripts/validate_engagement.py <slug>
```

Exit 0 → report may proceed. Exit 1 → blocked, with diagnostics. Integrate this
into any custom orchestration that produces reports.

**state.json shape:** conforms to `EngagementState`
(`state.model_dump_json()`); minimally needs metadata, the analysis block(s),
assumptions with breakevens, and both governance verdicts.

## 4. Evidence Providers (opt-in, none shipped)

**New:** `packages/evidence/`. Nothing to do unless you want to attach a sourced
external-evidence provider. Implement the `EvidenceProvider` Protocol, register
it on a `ProviderRegistry`, and promote `ProviderResult`s into the Evidence
Ledger as `external_source` records. See ADR-007.

## 5. Version

`pyproject.toml` version → `0.1.0-rc2` (the RC1.2 convergence sprint).

## Nothing changed in

`packages/state`, `packages/persistence`, `packages/replay`,
`packages/reporting` (behaviour), or `knowledge-vault/` note content.
