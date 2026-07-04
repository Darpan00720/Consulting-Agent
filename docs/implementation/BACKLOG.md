# StratAgent — Backlog & Technical Debt

The **authoritative technical-debt register** (reconciled with the Architecture
Checkpoint M1 register at M1.7.8). Each item has exactly one disposition —
**Open**, **Closed**, or **Deferred** — and every Deferred item names its owning
milestone. Nothing here is actioned outside its target milestone without explicit
approval.

## Register (disposition summary)

| TD | Disposition | Owner / resolved by |
|---|---|---|
| TD-001 | **Open** | decide before M1 completes (see below) |
| TD-002 | **Closed** | M1.7.5 — LIFE-005..008 gate-entry rules |
| TD-003 | **Deferred → M6** | approval-actor/role rules (see below) |
| TD-004 | **Closed** | M1.7.5 — traceability disposition table |
| TD-005 | **Closed** | M1.7.1 — snapshot semantics (design D1) |
| TD-006 | **Closed** | M1.7.3/M1.7.4 — seq/ordering contract (D2) |
| TD-007 | **Deferred → M1.8** | event schema upcasting (M1.7.4 §R16) |
| TD-008 | **Closed** | M1.7.8 — tooling aligned on Python 3.12 |
| TD-009 | **Closed** | M1.7.8 — M1-Decomposition §M1.7 corrected |
| TD-010 | **Closed** | M1.7.7 — validation/append/snapshot/replay baselines |
| TD-011 | **Deferred** | centralize duplicated analysis-field maps on the third consumer |
| TD-012 | **Deferred** | adopt PEP 695 `type` aliases repo-wide (see below) |

## Open

### TD-001 — Evaluate renaming `Evidence.source`
- **Type:** Technical debt / API design.
- **Raised:** 2026-06-30 (M1.1 review).
- **Status:** Open — **review during the Engagement State milestone (M1)**, before external APIs stabilize.
- **Context:** `Evidence.source` (ADR-002 §14, implemented in M1.1) is overloaded — it
  carries a citation for `external_source` and a reference for `assumption`. A more
  neutral name (`reference` or `origin`) may read better and age better once the
  model is exposed through external / FastAPI APIs.
- **Constraints:** Do **not** change in M1.1. A rename touches ADR-002 §14, the model,
  tests, and the generated schema — if adopted, treat as a small ADR-002 amendment.
  Cost is low now (schema/API not yet externalized); decide before M1 completes.
- **Options:** keep `source` · rename → `reference` · rename → `origin`.

## Deferred

### TD-003 — Approval-actor / role enforcement
- **Type:** Technical debt / governance.
- **Status:** **Deferred → M6** (Agent Manager / role registry).
- **Context:** ADR-002's approval rules (analysis gate approved only by the
  Reviewer, recommendation gate only by the Challenger, final acceptance by
  Human/Manager; no self-approval) require knowing *which role* is acting.
  `EventMetadata.actor` is a free string and there is no role registry until
  agents exist (M4–M6). M1.7.6 shipped the ownership **data** (`state.ownership`)
  the enforcement will consume; `QualityGate.by` already captures the approving
  actor, so no information is lost by waiting.
- **Owner:** M6 (Agent Manager). Enforced against the M1.7.6 datasets.

### TD-007 — Event schema upcasting
- **Type:** Technical debt / persistence.
- **Status:** **Deferred → M1.8.**
- **Context:** every event carries `schema_version` (currently 1). Handling
  `schema_version > 1` (upcasting old persisted events on load) has no design yet
  because no persisted events exist pre-M1.8 (M1.7.4 §R16). The replay
  `ReplayErrorCode` namespace is additive-frozen so M1.8 can extend it.
- **Owner:** M1.8 (persistence), when a storage format exists to design against.

### TD-011 — Duplicated analysis-field maps
- **Type:** Technical debt / maintainability.
- **Status:** **Deferred** (no target milestone; act on the third consumer).
- **Context:** the analysis-name → state-field mapping appears in projection and
  validation helpers. Two consumers do not yet justify a shared constant; the
  standing rule is to centralize when a third consumer appears.

### TD-012 — Adopt PEP 695 `type` aliases repo-wide
- **Type:** Technical debt / modernization.
- **Raised:** 2026-07-04 (M1.7.8, from the Python 3.12 target bump).
- **Status:** **Deferred** (no target milestone; opportunistic).
- **Context:** with the 3.12 target, ruff `UP040` suggests converting
  `X: TypeAlias = ...` to `type X = ...`. Deferred for `common/values.py`
  (`Identifier`/`Reference`/`ConfidenceScore`) via documented `# noqa: UP040`
  because `ConfidenceScore` is `Annotated[float, Field(...)]` and converting it
  to a lazy PEP 695 alias risks pydantic's resolution of the constraint metadata
  — out of scope for M1.7.8 (no runtime behaviour change). The related `UP047`
  (function generics) *was* adopted in `projection._replace`.
- **Constraints:** verify pydantic enforces `ConfidenceScore`'s 0–1 bound through
  a `type` alias before adopting; otherwise keep the `TypeAlias` form.
