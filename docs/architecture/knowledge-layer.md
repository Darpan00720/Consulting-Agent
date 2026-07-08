---
title: Knowledge Layer — Architecture Addendum (post-M2)
status: Stable addendum to the frozen v1.0 baseline
date: 2026-07-08
supplements: docs/reviews/Architecture-v1.0.md (FROZEN — not modified)
governing_adr: ADR-003, ADR-004 (neither ADR modified by M2)
evidence-discipline: every claim [Verified] / [Inference] / [Unknown]
---

# Knowledge Layer — Architecture Addendum

**Architecture v1.0 remains frozen and unmodified** (`docs/reviews/Architecture-v1.0.md`,
`status: FROZEN`, immutable unless a new ADR changes it). That baseline named the
Knowledge Layer a future extension point; this addendum records that the **vault
content and validator** portion of that layer is now **implemented** by M2, without
altering the baseline — the same way M1.8 and M1.9 realized the persistence and
replay extension points without editing v1.0. [Verified — v1.0 "Extension Points";
M2 zero-diff on packages/state, packages/persistence, packages/replay]

---

## What M2 delivered

### Vault content (`knowledge-vault/`)

`knowledge-vault/` is now populated with StratAgent's institutional consulting
knowledge as human-readable, git-versioned Obsidian notes conforming to ADR-003 §5
frontmatter. [Verified — validate_vault: 132 notes, is_valid=True, 0 errors]

| Category | Directory | Count | Authority |
|---|---|---|---|
| Consulting domains | `domains/` | 15 | ADR-004 §2 |
| Frameworks (primary) | `frameworks/` | 15 | ADR-004 §3 |
| Frameworks (supporting) | `frameworks/` | 48 | ADR-004 §3 |
| Issue trees | `issue-trees/` | 15 | ADR-004 §4 |
| KPI catalog | `kpis/` | 14 | ADR-004 §5 |
| Industry model | `industries/` | 10 | ADR-004 §6 |
| Business problems | `business-problems/` | 15 | ADR-004 §8 |
| **Total** | | **132** | |

All notes carry `status: draft` (Hybrid D-6 authorship policy: AI-drafted,
reviewer-promoted). No benchmark values, no proprietary knowledge, no company-
specific data are authored. Every statement is evidence-classified. [Verified —
Hybrid D-6 policy; D-6 memory record]

### Validator (`packages/knowledge`)

A new leaf package — a **pure, read-only** frontmatter validator. [Verified — zero
IO side-effects confirmed; KV-010]

| Component | What it does |
|---|---|
| `frontmatter.py` | Pydantic models for all 13 note types (ADR-003 §5 + ADR-004 additions) |
| `frontmatter_validator.py` | `parse_frontmatter` (YAML extraction) + `validate_note` (per-type dispatch) |
| `vault_validator.py` | `validate_vault` (cross-note: broken wikilinks, duplicate ids/aliases, ADR-004 coverage, missing directories) |
| `__init__.py` | Exports 28 symbols (frozen public surface) |

Public entry points (frozen):
- `parse_frontmatter(text: str) -> dict[str, object]` — YAML block extraction
- `validate_note(text: str) -> CommonHeader` — single-note schema validation
- `validate_vault(vault_dir: Path) -> VaultReport` — vault-wide validation

**Coverage: 100% (260/260 statements).** [Verified — pytest --cov]

### Wikilink graph (in-vault)

M2 enforces a **no-dangling-links** invariant (KV-003) with `validate_vault`. The
in-vault link graph is dense: [Verified — 0 broken_wikilink errors]

- **Domain ↔ Framework**: 63 framework notes each carry `[[domains/...]]` in their
  `domains:` frontmatter field; 15 domain notes each carry `[[frameworks/...]]`
  in the body.
- **Issue tree → Domain**: all 15 issue trees link to their domain.
- **Business problem → Issue tree → Domain**: all 15 business problem notes link to
  an issue tree and a domain.
- **KPI → Domain + Framework**: all 14 KPI notes link to at least one domain and at
  least one framework.
- **Industry → Domain + KPI**: all 10 industry notes link to at least one domain;
  those with canonical KPI matches (8 of 10) carry `[[kpis/...]]` links.
- **KPI → KPI**: LTV:CAC links to LTV and CAC; LTV links to Customer Churn.

Graphify (M3) will derive a typed-edge graph from these wikilinks. The wikilink
discipline established in M2 is a precondition for that step. [Inference — ADR-003 §6]

---

## Extension points — updated view

The v1.0 baseline listed these as *future*. Post-M2 status:

- **Persistence (M1.8)** — ✅ implemented (`packages/persistence`). [Verified]
- **Replay (M1.9)** — ✅ implemented (`packages/replay`). [Verified]
- **Knowledge Layer — vault content (M2)** — ✅ implemented (`knowledge-vault/`,
  `packages/knowledge`). The vault is the authoritative firm-knowledge store
  (ADR-003: "the single source of truth"). Validator enforces KV-001…KV-011. [Verified]
- **Knowledge Layer — Graphify indexing, vector index, Knowledge Agent (M3)** —
  🔲 future. M3 will watch the vault, parse frontmatter+wikilinks, generate the
  knowledge graph and vector index, and expose them to the Knowledge Agent.
  [Verified — Roadmap M3; ADR-003 §6/§7]
- **Agent Manager (M6), Authorization (M6), Ruflo/MCP integration** — 🔲 future.
  [Verified]

---

## Open decisions (deferred to M3 / standalone reviews)

| ID | Decision | Status |
|---|---|---|
| D-3 | Plugin cheat-sheet migration into vault (vault as sole authority) | Deferred to M3 |
| D-4 | Ratify ADR-003/004: `Proposed` → `Accepted` | Deferred — standalone review |
| D-5 | Enforce draft-until-reviewed via gate (not only convention) | Deferred to M3 |
| D-8 | 5 ADR-004-added types lack per-type frontmatter schemas | Deferred to M3 |
| D-9 | Per-note `schema_version` field | Deferred to M3 |

---

## What did not change

No ADR; no `packages/state`, `packages/persistence`, or `packages/replay` files;
Architecture v1.0; validator logic (frozen after S2); note count below 132 (all
new content is additive). Any schema change or new validator rule still requires a
new ADR and explicit approval. [Verified — zero-diff on frozen packages; S5 gate green]
