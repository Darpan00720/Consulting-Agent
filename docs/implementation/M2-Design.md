---
title: M2 — Knowledge Library Content (Obsidian Vault) — Design & Evidence, Phase 1
status: PROPOSED — awaiting approval before Phase 2 (implementation)
date: 2026-07-05
milestone: M2 (Knowledge library content); requested as "M1.10" — clarified to mean the roadmap's next top-level milestone (M1 completed at M1.9)
baseline: HEAD 856e792; Architecture v1.0 FROZEN; M1 complete (M1.1–M1.9)
governing_adr: ADR-003 (Knowledge Architecture), ADR-004 (Consulting Knowledge Library); no ADR modified by this milestone
evidence_policy: every statement tagged [Verified] / [Inference] / [Unknown]
---

# M2 — Knowledge Library Content (Design, Phase 1)

**This document is design only.** It proposes no content and no code. The single
artifact of Phase 1 is this file; no `packages/**`, `tests/**`, benchmark, or
other doc is touched. ADRs are not modified.

**Naming note.** This milestone was requested as *"M1.10."* The evidence pass
found M1 completes at M1.9 and no "M1.10" exists anywhere in the repo; you
confirmed the intent is the roadmap's next top-level milestone, **M2 — Knowledge
library content**. This document is named accordingly. [Verified — user decision]

Evidence tags: **[Verified]** = read directly from a repo file at the baseline;
**[Inference]** = reasoned from verified facts; **[Unknown]** = not determinable
from evidence (a decision or a Phase-2 discovery).

---

## 1. Objective

Populate `knowledge-vault/` with StratAgent's institutional consulting knowledge
(ADR-004) as human-readable, git-versioned Obsidian notes that conform to the
ADR-003 §5 frontmatter schema, and add a **frontmatter validator**
(`packages/knowledge/`) that mechanically enforces vault integrity: schema
completeness, provenance, resolvable `[[wikilinks]]`, and ADR-004 coverage.
[Verified — Roadmap M2: "ADR-004 knowledge as vault notes conforming to ADR-003
§5 frontmatter"; components list]

The deliverable is **knowledge-as-data + a validator**, not runtime behaviour.
Indexing, retrieval, and the Knowledge Agent are explicitly M3. [Verified —
Roadmap M3; ADR-004 "Out of scope: agents, orchestration, retrieval, runtime"]

## 2. Scope

1. **Vault content** under `knowledge-vault/`: the 15 `domain` notes; `framework`
   notes (primary + supporting); `issue_tree` templates; `kpi` notes; `industry`
   notes; `deliverable` templates. [Verified — Roadmap M2 components; ADR-004
   §2/§3]
2. **ADR-003 §5 frontmatter** on every note (typed YAML header + per-type fields
   + governance triad `source`/`last_verified`/`status`). [Verified — ADR-003 §5;
   Roadmap M2]
3. **`packages/knowledge/frontmatter_validator.py`** — validates the schema,
   detects dangling `[[wikilinks]]`, asserts ADR-004 coverage, checks governance
   fields and `status ∈ {approved, draft}`. [Verified — Roadmap M2 files + test
   plan]
4. **`tests/knowledge/**`** — validator unit tests + vault-wide assertions.
   [Verified — Roadmap M2]

## 3. Out of scope

- **Graphify indexing / vector index / knowledge graph build** — M3. A
  `knowledge-vault/graphify-out/` directory already exists from prior
  experimentation; M2 neither reads nor writes it. [Verified — Roadmap M3;
  `graphify-out/` present]
- **Knowledge Agent / retrieval / provenance-pinning into state** — M3.
  [Verified — Roadmap M3; ADR-005]
- **The Engagement State engine** (`packages/state`, `packages/persistence`,
  `packages/replay`) — M1, complete and frozen; M2 depends on **none** of it.
  [Verified — Roadmap M2 "Dependencies: M0"; M1-Decomposition M1.9 "completes M1"]
- **Ruflo memory / ReasoningBank curation** — M9. [Verified — Roadmap M9]
- **Runtime execution of frameworks** — ADR-004 defines *what the knowledge is*,
  not how it runs. [Verified — ADR-004 scope]

## 4. Evidence summary

- **Vault is scaffolded but empty of knowledge.** `knowledge-vault/` has typed
  directories (`frameworks/`, `industries/`, `kpis/`, `templates/`, `companies/`,
  `engagements/`, `lessons/`, `playbooks/`, `_meta/`, `_attachments/`) each
  containing only `.gitkeep`; there are **zero** knowledge notes. Plus
  `.obsidian/` (editor config) and `graphify-out/` (prior index output). M2 is a
  from-scratch content population. [Verified — `find knowledge-vault -type f`]
- **`packages/knowledge/` exists as an empty package** (`__init__.py` only). The
  validator module does not yet exist. [Verified — `ls packages/knowledge`]
- **ADR-003 §5** defines a common frontmatter header + per-type typed fields;
  `source` is **required** provenance (§10), `last_verified` drives freshness,
  `confidence` weights ranking; `type` labels the graph node; malformed
  frontmatter is quarantined, not indexed. [Verified — ADR-003 §5/§8/§10]
- **ADR-004** adds note types `domain`, `issue_tree`, `deliverable`,
  `business_problem`, `recommendation`; defines **15 consulting domains** (§2,
  each a `domain` note); defines the **framework asset schema** (§3) with ~11
  required attributes (`id · name · domain(s) · tier{primary|supporting} ·
  purpose · when_to_use · diagnostic_questions · success_metrics(KPI refs) ·
  common_risks · common_mistakes · related_frameworks · source · confidence ·
  version · status`), plus per-domain primary/supporting frameworks, issue-tree
  templates, and decision logic. [Verified — ADR-004 §1–§3]
- **The 15 domains** (§2): Profitability, Revenue Growth, Cost Reduction,
  Pricing, Market Entry, M&A, New Product Launch, Supply Chain, Org Design,
  Digital Transformation, Data & AI Strategy, Corporate/Portfolio Strategy,
  Customer/Retention, Marketing/GTM, Due Diligence. [Verified — ADR-004 §2 entries
  (some labels read via their deliverables lines); the verbatim set is enumerated
  in §2]
- **Reusable seam:** `plugins/ruflo-stratagent/knowledge/frameworks/*.md` — 9
  framework cheat sheets (profitability, growth, cost-reduction, pricing,
  market-entry, ma-acquisition, new-product-launch, turnaround,
  generic-diagnose-recommend). Candidate source material to adapt into vault
  `framework` notes (they lack ADR-003 frontmatter / the 11-attribute schema).
  [Verified — `find`]
- **ADR-003 and ADR-004 are `status: Proposed`** in their frontmatter, though
  part of the v1.0 ADR set. [Verified — ADR headers] → Decision **D-4**.
- **Dependency direction:** M2 depends only on M0 (a frontmatter schema
  convention). It does not depend on M1 and nothing in M1 depends on it — the
  two are orthogonal. [Verified — Roadmap M2/dependency graph]

## 5. Verified / Inference / Unknown table

| # | Statement | Tag |
|---|---|---|
| E1 | Vault has only `.gitkeep` + `.obsidian`/`graphify-out`; no knowledge notes | [Verified] |
| E2 | `packages/knowledge/` exists with only `__init__.py` | [Verified] |
| E3 | ADR-003 §5 common header incl. `source`(required), `last_verified`, `confidence`, `type` | [Verified] |
| E4 | Governance triad `source`/`last_verified`/`status` required on notes | [Verified — Roadmap M2 + ADR-003 §10] |
| E5 | ADR-004 defines 15 domains + framework schema (~11 attrs) + KPI/industry/deliverable/issue-tree catalogs | [Verified] |
| E6 | Exact verbatim domain label strings + the complete common-header field list | [Inference] — read §2/§5 tables in full during Phase 2 |
| E7 | 9 plugin framework cheat sheets are adaptable source for vault `framework` notes | [Inference] |
| E8 | M2 depends on M0 only; orthogonal to M1 | [Verified] |
| E9 | Graphify/retrieval is M3; M2 does not index | [Verified] |
| E10 | The *volume* of content M2 must author (how many supporting frameworks/KPIs/industries) | [Unknown] → D-1 |
| E11 | Who authors the consulting IP (assistant-generated vs human-provided) | [Unknown] → D-6 |
| E12 | Validator implementation shape (pydantic-per-type vs generic schema; deps) | [Unknown] → D-2 |
| E13 | Whether ADR-003/004 must be moved Proposed→Accepted before building | [Unknown] → D-4 |
| E14 | Fate of the 9 plugin cheat sheets once the vault is authoritative (dedupe/derive) | [Unknown] → D-3 |

## 6. Architecture impact

- **New leaf package `packages/knowledge`** (validator) + **content tree
  `knowledge-vault/`**. Both are additive; no existing package changes.
  [Inference — Roadmap files-affected]
- **`knowledge-vault/` becomes the single source of truth for firm knowledge**
  (ADR-003: the vault "be the single source of truth; not edited by automated
  indexers"). This creates an authoritative-store relationship the plugin's
  `knowledge/frameworks/*.md` currently also plays informally → D-3. [Verified —
  ADR-003 responsibilities table]
- **Dependency direction:** `packages/knowledge` (validator) depends on the
  vault layout + a frontmatter schema; nothing depends on it yet (M3 will).
  `packages/state`/`persistence`/`replay` are untouched (zero-diff). [Inference]
- **Architecture v1.0 stays frozen.** M2 realizes the "Knowledge Layer"
  extension point the same way M1.8/M1.9 realized theirs — recorded, not by
  editing the frozen baseline. [Verified — v1.0 extension points; M1.8/M1.9
  precedent]

## 7. Dependency analysis

- **Upstream:** M0 (frontmatter schema convention) [Verified]. ADR-003 + ADR-004
  are the content contracts [Verified].
- **Downstream:** M3 (Graphify + Knowledge Agent) consumes the vault; M4/M5
  (planning/analysis agents) consume knowledge via M3; M7 (MVP) needs the
  library populated. [Verified — Roadmap dependency graph]
- **No coupling to M1.** The validator reads markdown/YAML, not
  `EngagementState`. [Verified]
- **Toolchain:** same as the rest of the repo — `uv`, `ruff`/`black`,
  `mypy --strict`, `pytest`; validator is a normal package under the existing
  gate. [Inference — repo-wide config]

## 8. Public API impact

- **New public surface:** `packages/knowledge` — at minimum a validator entry
  point (function/class) + typed frontmatter models. Shape is **D-2**. [Inference]
- **No change** to the frozen `state`/`persistence`/`replay` public surfaces.
  [Verified — zero-diff intent]
- **Vault "API" is the frontmatter schema itself** — the typed contract every
  note satisfies and Graphify (M3) will parse. [Verified — ADR-003 §5/§8]

## 9. Extension-point analysis

- Realizes the **Knowledge Layer** (Roadmap: "vault content + Graphify indexing +
  Knowledge Agent ship together"; M2 is the *content* portion, M3 the indexing/
  retrieval). [Verified — Roadmap §2 milestone-adjustments note]
- **Clean seam to M3:** M3 indexes `knowledge-vault/` and retrieves via the
  Knowledge Agent; M2 must leave the vault in a state Graphify can parse
  (well-formed frontmatter, resolvable links) — which the validator guarantees.
  [Inference]
- **Provenance pinning (M3)** relies on M2's `source` + note `id` + git commit;
  M2's required-`source` invariant is the precondition. [Verified — ADR-003 §10;
  Roadmap M3]

## 10. Technical-debt interaction

- **No interaction with the M1.9 debt register** (RP-017 wording, `verify_log`
  redundancy, 100k scale) — those are state-layer items, orthogonal to M2.
  [Verified]
- **ADR-003/004 `status: Proposed`** is a latent doc-debt item: building content
  against Proposed ADRs is fine, but they should be moved to Accepted at/By M2
  close for a clean provenance chain → D-4. [Verified — ADR headers]
- **Dual knowledge stores** (plugin `knowledge/frameworks` vs `knowledge-vault`)
  is pre-existing debt M2 must resolve or explicitly defer → D-3. [Verified]
- **`graphify-out/` is stale prior output** not driven by current content;
  harmless but should be regenerated in M3 (not M2). [Inference]

## 11. Risk assessment

- **[High] Content volume & authorship.** A complete ADR-004 catalog (15 domains
  × primary+supporting frameworks + KPI/industry/deliverable/issue-tree notes) is
  a large body of consulting IP. Scope and authorship must be decided up front
  (D-1, D-6), else the milestone is unbounded. Mitigation: a coverage-defined
  minimum (roadmap exit = 15 domains each ≥1 primary framework + catalogs
  complete) with supporting content phased.
- **[Medium] Correctness of consulting content.** Frameworks/KPIs are
  domain-expert assertions; `source` provenance + `confidence` + `status: draft`
  mitigate, but review is needed. Mitigation: `status: draft` for un-reviewed
  notes; validator does not judge *correctness*, only *form*.
- **[Medium] Frontmatter/schema drift from ADR-003/004.** If the validator's
  schema and the ADRs diverge, notes pass validation but violate intent.
  Mitigation: derive the validator schema directly from ADR-003 §5 / ADR-004 §3
  and cite section numbers.
- **[Low] Wikilink integrity at scale.** Many cross-references → dangling links.
  Mitigation: the validator's no-dangling-link check is a hard gate.
- **[Low] Obsidian/`.obsidian` + `_attachments` noise.** Validator must scope to
  knowledge notes and ignore editor config/attachments/`graphify-out`.

## 12. Implementation slices (proposed for Phase 2+)

Approval-gated, mirroring the M1.8/M1.9 cadence. (Order/content subject to D-1.)

- **S1 — frontmatter schema + validator core.** Typed models for the common
  header + per-type fields (ADR-003 §5 / ADR-004 §3); `frontmatter_validator.py`
  validates one note. Tests. No vault content yet.
- **S2 — vault-wide validator.** Dangling-`[[wikilink]]` detection, id
  uniqueness, `status` enum, freshness; scoping rules (ignore `.obsidian`/
  `_attachments`/`graphify-out`). Tests on fixtures.
- **S3 — domain + framework notes.** 15 `domain` notes; ≥1 primary `framework`
  per domain (adapting the 9 plugin cheat sheets where they map). Coverage
  assertion. 
- **S4 — KPI / industry / deliverable / issue-tree catalogs.** Complete the
  ADR-004 catalogs; supporting frameworks per D-1.
- **S5 — finalization.** Coverage assertion green, all notes `approved`/`draft`,
  ADR-003/004 status per D-4, completion report, CHANGELOG.

## 13. Invariant plan (KV-001 … proposed)

| ID | Invariant | Source |
|---|---|---|
| KV-001 | Every note carries a complete ADR-003 §5 frontmatter header (`id`, `type`, `title`, …) | ADR-003 §5 |
| KV-002 | Every note has a non-empty `source` (provenance required) | ADR-003 §10 |
| KV-003 | No dangling `[[wikilinks]]` — every link resolves to an existing note | Roadmap M2 test plan |
| KV-004 | All 15 ADR-004 domains present, each with ≥1 `primary` framework | Roadmap M2 exit; ADR-004 §2/§3 |
| KV-005 | ADR-004 KPI / industry / deliverable catalogs complete | Roadmap M2 exit; ADR-004 |
| KV-006 | Every note `status ∈ {approved, draft}` (no missing/other) | Roadmap M2 exit |
| KV-007 | Every `framework` note carries the ADR-004 §3 required attributes | ADR-004 §3 |
| KV-008 | Note `id`s are unique; `type ∈` the ADR-003+ADR-004 type set | ADR-003 §5; ADR-004 |
| KV-009 | The vault is the single authoritative knowledge store | ADR-003 responsibilities |
| KV-010 | The validator is read-only + deterministic (never mutates the vault) | [Inference] — safety |
| KV-011 | M2 performs no indexing/retrieval (no Graphify invocation) | Roadmap M3 boundary |

Each KV invariant will get description · rationale · severity · owner ·
verification source · milestone in the Phase-2 slice that implements it.

## 14. Test strategy

- **Validator unit tests** (`tests/knowledge/`): valid note per type passes;
  each rejection path (missing `source`, bad `status`, unknown `type`, missing
  required framework attribute) fails with a precise error. Deterministic.
- **Vault-wide assertions:** run the validator over `knowledge-vault/` →
  KV-001..008 pass; ADR-004 coverage (KV-004/005) asserted; no dangling links
  (KV-003).
- **Scoping tests:** `.obsidian/`, `_attachments/`, `graphify-out/` are ignored.
- **Fixtures:** small in-repo fixture vault for negative cases (never mutate the
  real vault). Determinism: no clocks/network in tests.
- **Gate:** the existing six-step gate; `packages/knowledge` coverage target set
  at Phase 2 (D-2). No benchmark (content milestone; not perf-sensitive).

## 15. Definition of Done (Phase 1)

- [x] Evidence pass complete; vault/package/ADR state established.
- [x] 15-section design produced, every statement evidence-tagged.
- [x] Naming ambiguity ("M1.10" → M2) resolved with the user and recorded.
- [x] KV-001…KV-011 invariant plan drafted.
- [x] Risks, dependencies, extension points, tech-debt interactions surfaced.
- [x] Decisions requiring approval enumerated (D-1…D-6).
- [x] Repository behaviour-identical (only this doc added); `packages/**`/`tests/**`
      zero-diff.
- [ ] **Approval to proceed to Phase 2** — pending, gated on D-1…D-6.

---

## Decisions requiring approval

| # | Decision | Options | Lean (not decided) |
|---|---|---|---|
| **D-1** | **Content volume for M2** | (a) roadmap minimum only (15 domains + ≥1 primary framework each + KPI/industry/deliverable catalogs "complete" per ADR-004); (b) full primary+supporting framework catalog; (c) skeleton now, content iterated across sub-slices | (a) as the M2 exit bar, supporting frameworks phased into S4 — bounds the milestone. |
| **D-2** | **Validator architecture** | (a) Pydantic models per note type (reuses the repo's Pydantic-canonical pattern); (b) a generic schema-driven validator; deps: stdlib + PyYAML + pydantic | (a) — matches the codebase; add a YAML parser dep. Set `packages/knowledge` coverage target (e.g. 100% like other packages). |
| **D-3** | **Fate of the 9 plugin cheat sheets** | (a) adapt/migrate them into vault `framework` notes and make the vault authoritative (plugin references the vault); (b) keep both, vault is canonical, plugin copies are derived/dev-only; (c) leave plugin as-is, author vault fresh | (a) — ADR-003 says the vault is the single source of truth; avoids dual-store drift. |
| **D-4** | **ADR-003/004 status** | (a) move Proposed→Accepted before/at M2 (they are being built against); (b) leave Proposed | (a) — a milestone that implements an ADR should ratify it; low effort, clean provenance. |
| **D-5** | **Content authorship review** | (a) assistant drafts all notes `status: draft`, a domain reviewer promotes to `approved`; (b) all `approved` immediately | (a) — `draft` until reviewed keeps the provenance/quality bar honest. |
| **D-6** | **Who authors the consulting IP** | (a) assistant generates the domain/framework/KPI content from ADR-004 + the plugin cheat sheets; (b) user/domain expert supplies content, assistant only structures + validates | **Needs your call** — this determines whether Phase 2 is authoring or scaffolding-for-authoring. No safe default. |

**None of the above is decided.** Phase 2 does not begin until they are ruled —
D-1 and D-6 in particular set the shape and size of the whole milestone.
