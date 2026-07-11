# StratAgent RC1.2 — Architecture Convergence: Final Report

**Principal Architect · Convergence sprint (evaluation findings → implementation)**
**Date:** 2026-07-09 · **Version:** `0.1.0-rc2` · **Base:** `3cb863a` (0.1.0-rc1)

Mission: eliminate the verified architecture inconsistencies from the RC1
validation campaign. No new consulting features; no scope expansion.

---

## 1. Architecture changes (by work item)

| WI | Finding (RC1) | Decision | Mechanism |
|---|---|---|---|
| **1** | Classifier & selector read different framework stores | `knowledge-vault/frameworks/` is the single source of truth; cheat sheets → redirect stubs | agent + SKILL repoint; `_MIGRATION.md` index |
| **2** | Deterministic validation not on the live path | State-bridge + blocking gate before report delivery | `packages/orchestration/` + `scripts/validate_engagement.py`; ADR-006 |
| **3** | Lightweight pipeline skipped the Reviewer | ADR-002 already makes gates mandatory → Reviewer always runs | SKILL rule removed; ADR-006 ratifies |
| **4** | Vault has no benchmarks (by design) | Build the *extension seam*, populate nothing | `packages/evidence/`; ADR-007 |

---

## 2. Before / After

### Framework knowledge (WI-1)

```
BEFORE                                   AFTER
case-classifier ─► plugin/knowledge/     case-classifier ─┐
                    frameworks (9)        framework-selector ─┤
framework-selector ─► knowledge-vault/    planner ───────────┼─► knowledge-vault/
                       frameworks (65)     knowledge-agent ──┘     frameworks (65)
   two stores, divergent coverage            one source of truth
                                          plugin cheat sheets = redirect stubs
```

### Report path (WI-2 / WI-3)

```
BEFORE                                   AFTER
… analysts                               … analysts
   └► (lightweight: skip Reviewer)          └► Reviewer  (MANDATORY, every mode)
   └► Challenger                            └► Challenger (MANDATORY)
   └► report-writer ─► report.md            └► state.json ─► GATE ─┬─ pass ─► report-writer
        (no deterministic gate)                 enforce_render_ready │
                                                + validate_consistency└─ fail ─► BLOCK + diagnostics
```

### Evidence (WI-4)

```
BEFORE  vault (frameworks only) ─► analysts label every number [ASSUMPTION]
AFTER   vault ─► analysts                  (unchanged; no providers populated)
        + packages/evidence/  ◄── optional EvidenceProvider registry (attach later)
```

---

## 3. Files modified

**New code (`packages/`, `scripts/`):**
- `packages/evidence/` — `__init__`, `provider.py`, `cache.py`, `registry.py`, `errors.py`
- `packages/orchestration/` — `__init__`, `report_gate.py`
- `scripts/validate_engagement.py`

**New tests:** `tests/evidence/`, `tests/orchestration/`, `tests/convergence/` (+ `__init__` markers)

**New docs:** `ADR-006`, `ADR-007`, `Execution-Flow.md`, `DEVELOPER_GUIDE.md`,
`RC1.2-Release-Notes.md`, `RC1.2-Migration-Guide.md`, this report,
`knowledge/frameworks/_MIGRATION.md`

**Edited (intentional):** `case-classifier.md`, `framework-strategist.md`,
`solve-case/SKILL.md`, the 9 framework cheat sheets (→ stubs), `pyproject.toml`
(version + first-party), `CHANGELOG.md`

**Edited (black formatting only, no logic change):** `governance/{gates,transitions}.py`,
`planning/{mece_validator,preconditions}.py`, `reporting/{__init__,renderer,validation}.py`,
and several test files — collapsing now-fitting lines so `black --check` passes.

**Untouched (as required):** `packages/state/**`, `persistence/**`, `replay/**`,
`reporting` *behaviour*, and all `knowledge-vault/` note content.

---

## 4. Benchmarks (deterministic re-run)

LLM engagements are non-reproducible; the meaningful re-run is the deterministic
layer on **real pilot data**. Built `engagements/northwind-eu-entry/state.json`
from the Northwind pilot (MARKET_ENTRY, assumption-backed findings, both
verdicts) and ran the live gate:

| Check | Result |
|---|---|
| Live gate on valid Northwind state | ✓ **PASSED** (exit 0) — render-ready + consistent |
| Same recommendation preserved | ✓ "Enter EU now via direct-build" |
| Same governance preserved | ✓ Reviewer approved · Challenger stands_with_caveats |
| Live gate on broken state (reviewer dropped + finding unevidenced) | ✓ **BLOCKED** (exit 1), 2 actionable diagnostics |
| Improved consistency | ✓ the gate now blocks what previously slipped through (the C09-class inconsistency) |

Full suite (regression):

| Gate | Result |
|---|---|
| ruff | clean |
| black --check | clean (158 files) |
| mypy --strict | clean (80 source files, +8) |
| pytest | **915 passed** (+54 vs RC1's 861) |

---

## 5. Coverage

| Package | Coverage |
|---|---|
| `packages/evidence/` | 98% (provider/cache/errors 100%; registry 96%) |
| `packages/orchestration/` | 100% |
| New-package total | **98%** |

Tests added: 24 provider-interface, 15 report-gate, 12 convergence guards, 3
registry edge cases = **54**.

---

## 6. Migration notes

See `RC1.2-Migration-Guide.md`. Summary: backwards compatible. Old cheat-sheet
paths resolve as stubs; no state/persistence/replay changes; engagement
behaviour identical with no providers registered. Custom orchestration that
produces reports must call the Phase-8 gate. One doc left for the owner to
update: `CLAUDE.md`'s "Framework library" line still describes the old model.

---

## 7. Remaining technical debt

1. **Evidence providers are unpopulated by design.** The empty-benchmark
   limitation (F-1) is now *addressable by configuration*, but until a provider
   is attached, numbers remain labeled assumptions.
2. **The provider registry is not wired into `knowledge.retrieval_adapter`.**
   Deliberate (M3 module frozen); a future sprint decides the retrieval-time
   promotion of `ProviderResult` → Evidence Ledger.
3. **`state.json` emission is orchestrator (LLM) responsibility.** The gate is
   deterministic, but its input is LLM-produced; it validates *structure*, not
   truth. A schema-guided emitter would harden this.
4. **`render_report()` remains off the live path** (LLM writes the narrative).
   Acceptable per ADR-006; revisit if fully-deterministic reports are wanted.
5. **`CLAUDE.md` framework-library description** is stale (owner-owned file).
6. **ADR-001–005 remain `status: Proposed`** (RC1 audit A-1); ADR-006/007 are
   `Accepted`. Ratifying the earlier ADRs is a separate governance task.

---

## 8. Completion criteria

| Criterion | Status |
|---|---|
| One framework repository | ✓ vault canonical; cheat sheets stubbed |
| Live validation active | ✓ blocking gate + script; proven on pilot data |
| Reviewer architecture resolved | ✓ mandatory in every mode (ADR-006) |
| Evidence Provider interface complete | ✓ interface/lifecycle/cache/traceability/failure (ADR-007) |
| Tests passing | ✓ 915 passed |
| Benchmarks passing | ✓ deterministic gate re-run green |
| No architecture drift | ✓ frozen packages untouched; guards pinned by tests |
| Repository clean | ✓ ruff/black/mypy clean; working tree coherent |

---

**StratAgent RC1.2 COMPLETE**
