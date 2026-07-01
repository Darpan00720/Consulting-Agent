# StratAgent — Backlog & Technical Debt

Deferred improvements and technical debt. Each item has an ID, type, status, and
target review point. Nothing here is actioned outside its target milestone without
explicit approval.

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
