# ADR-008 — Repository Topology: Three Artifacts, One Product Line

**Status:** Accepted · **Date:** 2026-07-15 · **Supersedes:** none · **Amends:** ADR-001

## Context

An independent audit (2026-07-15) surfaced a structural fact that no prior
document stated: this repository contains **three parallel implementations of
the consulting engagement**, and a new contributor cannot tell which one to
modify. The three are real, and the confusion is legitimate:

| Artifact | LOC | Tests | Language | Consumer |
|---|---:|---:|---|---|
| `packages/` | ~10,070 | 954 | Python library | **its own tests only** |
| `apps/dashboard/` | ~2,860 | 61 | FastAPI + Next.js | **end users (the web product)** |
| `plugins/ruflo-stratagent/` | 16 agents (Markdown) | — | Claude Code plugin | Claude Code users; **also read by the dashboard** |

The audit correctly flagged that the README's headline "954 tests" describes
`packages/`, which **no shipping artifact imports**, while the code users
actually run (`apps/dashboard/`) contributed 61 tests and carried all lint
debt. This ADR does not change that topology — it **names it**, so the
ambiguity stops costing contributors and reviewers time.

## Decision

We acknowledge three artifacts with distinct, non-overlapping roles:

### 1. `plugins/ruflo-stratagent/` — the canonical **domain definition**
The 16 agent prompts, the `solve-case` skill, and the `knowledge-vault/`
frameworks are the **single source of truth for consulting behaviour**. This is
what makes StratAgent StratAgent. It is executed directly by Claude Code, and —
critically — **the dashboard reads these same `agents/*.md` files at runtime**
(`apps/dashboard/backend/app/pipeline/prompts.py` →
`config.AGENTS_DIR / f"{agent}.md"`). This is the one genuine shared seam, and
it is deliberate: prompt/vault edits propagate to both surfaces.

### 2. `apps/dashboard/` — the **primary shipping product**
The public web application. It orchestrates the same agents through its own
Python pipeline (`engine.py`) with production concerns the plugin cannot express
in Markdown: multi-provider failover, checkpoint/auto-resume, persistence, SSE
streaming, BYOK, quotas. **This is what "is StratAgent production-ready?" refers
to.** New product work happens here.

### 3. `packages/` — the **reference core library**
An event-sourced, `mypy --strict`, 954-test implementation of the engagement
domain (state, replay, governance, knowledge, evidence, telemetry). It was built
first, milestone-by-milestone (M0–M9, ADR-001–007), as the rigorous model of the
domain.

**Partially on the execution path as of 1.0.0-beta.1.** `packages/telemetry` is
now imported by the dashboard (`app/telemetry_bridge.py`) and is the shipping
product's only source of operational observability. The rest (state, replay,
governance, knowledge, evidence) remains off the path, retained as: (a) the
executable specification the dashboard is checked against by humans, and (b) the
substrate for a future non-dashboard runtime.

**Wiring telemetry produced hard evidence for the open question below:**
`packages/telemetry` **cannot be taken on its own** — it imports
`state.identifiers.new_event_id`, pulling in `state` → `common` → `core`. The
dashboard image ships the entire `packages/` tree on `PYTHONPATH` to import one
subsystem. The core is not modular at the package boundary; it is modular only
as a whole. Any future extraction faces the same closure problem.

## Consequences

**Honest, and now stated:**
- `packages/` is **not dead code by accident** — it is a frozen reference core
  with no current production consumer. That is a deliberate (if debatable)
  choice, not an oversight. The audit's "orphaned" reading was correct on the
  facts; this ADR supplies the missing intent.
- The dashboard and the core **duplicate** the governance/pipeline logic. Nothing
  enforces their agreement. This is accepted debt for the beta; see Risks.

**Rules for contributors (also in the PR template):**
- Changing **consulting behaviour** (what an agent does, a framework) → edit
  `plugins/ruflo-stratagent/`. Both surfaces inherit it.
- Changing the **web product** (pipeline, resilience, UI, persistence) → edit
  `apps/dashboard/`.
- Changing the **reference core** → edit `packages/`; do not assume the
  dashboard picks it up (it does not).

**Documentation obligations discharged by this ADR:**
- README now reports test counts **per artifact** rather than a single number
  that describes only the core.
- CI runs **both** suites (`.github/workflows/ci.yml`).

## Open question (deferred, not decided here)

**Should `packages/` and `apps/dashboard/` be unified?** Options considered:

1. **Dashboard imports the core** — eliminates duplication, but requires
   packaging `packages/` as a wheel and re-expressing the failover/persistence
   layer against it. Largest effort; best long-term.
2. **Retire `packages/`** — delete 10k tested lines; loses replay/telemetry and
   the strict-typed domain model the dashboard was validated against.
3. **Status quo (this ADR)** — name the split, gate both in CI, revisit at 1.0.

We choose **(3) for the beta** because unification is a multi-week effort that
should not block a limited beta, and deletion discards genuinely valuable work.
This question **must be answered before a 1.0.0 (non-beta) release** — carrying
two divergent governance implementations into general availability is not
acceptable long-term. Tracked in `ROADMAP.md`.

**Update (1.0.0-beta.1) — the decision moved toward option 1.** Rather than let
`packages/` sit entirely unused, its most valuable unwired subsystem
(`telemetry`) was wired into the dashboard. This:
* gave the shipping product real observability it previously lacked entirely;
* proved the seam works — the dashboard's live traces are consumed by the
  core's own `scripts/engagement_telemetry.py` analytics unmodified;
* **retired option 2 (delete).** The core is now load-bearing for production
  observability; deleting it would regress the product.

The remaining choice is therefore between **(1) full unification** and a
long-lived hybrid. The telemetry closure problem (above) is the main obstacle
and should be the first thing addressed if (1) is pursued: the core needs real
package boundaries before it can be adopted piecemeal.
