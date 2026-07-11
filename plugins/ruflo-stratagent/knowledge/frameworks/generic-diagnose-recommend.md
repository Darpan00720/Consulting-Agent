# generic-diagnose-recommend — DEPRECATED (RC1.2)

> **Moved.** Framework content now lives in the governed knowledge vault at
> `knowledge-vault/frameworks/` (ADR-003 / ADR-004), the single source of truth.
>
> This cheat sheet is a **redirect stub** kept for backwards compatibility.
> It contains no framework content.

**How to get frameworks for the `generic-diagnose-recommend` archetype:**
Query the vault via the **Knowledge Agent** (or `knowledge.retrieve(...)`,
default `vault_dir=knowledge-vault`). The adapter ranks framework notes by
archetype using each note's `domains` / `tags` / `when_to_use` fields.

See [`_MIGRATION.md`](./_MIGRATION.md) for the archetype → vault-framework index
and the full migration rationale.
