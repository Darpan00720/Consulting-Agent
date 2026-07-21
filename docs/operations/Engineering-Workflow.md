# Multi-Model Engineering Workflow

**Status:** Designed 2026-07-17 (Phase 3.6). Codex's role here is live — see
[Codex-Workflow.md](Codex-Workflow.md) for its installation/security detail.
Gemini's role is **designed, deliberately not integrated**. This document
states the governance rules Gemini must satisfy *if* it is ever wired in.

> **Correction (2026-07-18):** this file originally said "no Gemini CLI or
> Claude Code plugin is installed on this machine today." That is no longer
> accurate — the Gemini CLI is now installed and operational (`gemini
> --version` succeeds). It remains **deliberately out of the active
> engineering toolchain** (Claude + Codex + Ollama), so every rule below that
> names Gemini is still a standing design, not a live gate — now by choice,
> not because it is uninstalled. The local model runtime that *was* installed,
> verified, and integrated is **Ollama** (see
> [Ollama-Local-Runtime.md](Ollama-Local-Runtime.md)); Kimi CLI is installed
> but excluded because it requires paid API credits.

This is a developer-tooling document. Nothing here touches StratAgent the
product; the consulting pipeline (`apps/dashboard/backend/app/pipeline`)
never calls any of these tools. It governs how the *engineering team* builds
StratAgent, using three model families as complementary collaborators rather
than interchangeable assistants.

## Why three models, and why not just the best one

A single model reviewing its own work has one blind spot: itself. The one
real data point this project has (§6c of ADR-010) is concrete: an independent
Codex review of code that had already passed 205 tests and a Claude
self-review still found three real, previously-invisible bugs — including
one that silently undermined this ADR's core "no LLM invents the ledger"
guarantee. That is the entire argument for this document: **no critical or
deterministic change should depend on a single model's judgment being
correct.** Adding a third model (Gemini) exists for the same reason, scoped
to the cases a second model can't settle alone — see Conflict Resolution
below. This is not about running every model on everything; that triples
review cost for most changes without a matching gain.

## Model roster

| Model | Status in this repo | What it actually brings |
|---|---|---|
| **Claude** (this session) | Primary, always available | The only participant with continuity across this repo's ADRs, agent prompts, memory system, and engagement history. Owns anything that requires integrated judgment across files/sessions. |
| **OpenAI Codex** | Installed, live, validated (`codex@openai-codex` v1.0.6; see [Codex-Workflow.md](Codex-Workflow.md)) | A genuinely different model family for independent review; proven to catch what Claude's self-review misses. Cheap/fast for mechanical, well-scoped delegation. |
| **Gemini CLI** | **Installed and available, but deliberately not part of the active dev toolchain.** The Gemini CLI is present on the machine (`gemini --version` succeeds); it is intentionally excluded from the live Claude + Codex + Ollama toolchain. (Gemini *is* also in production as one of the dashboard's free-tier LLM providers — an unrelated, product-side use; see `apps/dashboard/README.md`.) | Designed role: a third, architecturally distinct model family, and typically the largest context window of the three — useful for whole-repo consistency sweeps and as a tie-breaker, not for routine work. |

**The Gemini CLI is installed but not adopted into this workflow.** Its
installation is verified (`gemini --version` succeeds); its *adoption* into
the governance model below is a separate, deliberately-not-taken step. Until
Gemini is explicitly wired in as a reviewer here, every rule below that names
it has no live enforcement mechanism and is a standing design, not an active
gate. The local model runtime that *is* integrated is Ollama —
see [Ollama-Local-Runtime.md](Ollama-Local-Runtime.md).

## Responsibility matrix

Read each row as "highest marginal value," not "exclusive owner" — Claude
remains capable of doing any of these; the matrix says where delegating
elsewhere is worth the coordination cost.

| Category | Claude | Codex | Gemini | Neither |
|---|---|---|---|---|
| **Architecture** | Authors the proposal/ADR text — owns continuity with prior decisions | Adversarial-reviews major changes for internal consistency | Independent second read before a major ADR is finalized, or tie-breaker if Claude/Codex disagree | — |
| **Refactoring** | Anything touching P1–P3 deterministic modules or agent-prompt domain logic | Primary for large mechanical refactors, boilerplate, renames | Whole-repo consistency sweeps where context-window size, not judgment, is the bottleneck | — |
| **Code generation** | Agent prompts, consulting-domain code, deterministic modules (Ledger Builder, Quant Gate, Evidence Store) | Boilerplate, scaffolding, test fixtures, migrations | Rarely generates directly — reserved for review, not authorship | — |
| **Code review** | First-pass self-review (never sufficient alone for the tiers below) | Default independent reviewer — proven, real findings | Required third opinion only for deterministic-module or major-architecture PRs | — |
| **Test generation** | Verifies test correctness/coverage for deterministic modules | Primary generator for mechanical, well-scoped test scaffolding | Not typically used | — |
| **Performance analysis** | Decides what's worth optimizing; signs off on any change to a live path | Micro-optimizations backed by a benchmark number | Whole-codebase hotspot/consistency analysis where large context helps | — |
| **Security review** | Leads remediation; never auto-enters or handles credentials (standing rule, all models) | Adversarial-review required for anything touching secrets/auth/credential handling | Second opinion required for the same tier, once installed | — |
| **Consulting methodology** | **Owns exclusively** | — | — | Codex/Gemini — neither has this repo's accumulated domain context (ADR-005/006/009/010, the knowledge vault); delegating consulting judgment is exactly the risk P1–P3 exist to prevent |
| **ADR updates** | **Authors exclusively** | May comment/review a draft | May comment/review a draft | — |
| **Documentation** | Architecture- and ADR-linked docs | Mechanical doc sync acceptable (e.g., regenerating a table from code) | Rarely used | — |
| **Bug investigation** | Anything needing cross-file/domain context | First pass on isolated bugs with a reproducible failing test (`/codex:rescue`) | Tie-breaker when Claude and Codex disagree on root cause | — |
| **Production incidents** | Leads — owns full state/context, makes the call | Assists with isolated diagnosis, under supervision only | Not used live (too slow to bring in mid-incident); postmortem review only | Unsupervised autonomous action by any model on a live incident |

The **consulting methodology** row is the one hard boundary carried forward
unchanged from §6c: it is not a preference, it is the same rule that makes
the Quant Gate mean anything. A second (or third) LLM reviewing code is
additive safety. A second LLM making the business call is not — that is the
product's job, done by StratAgent's own governed agents, never a dev tool.

## Review protocol by change tier

| Tier | Examples | Required gate |
|---|---|---|
| **Small** | Typo, config tweak, single-function bugfix with an accompanying test | Author (Claude or Codex-delegated) merges after tests pass. No mandatory second review. |
| **Medium feature** | New module, multi-file change, non-deterministic-path feature | Author + one independent review from a *different* model before merge. Claude-authored → Codex reviews (or vice versa). |
| **Major architectural change** | New package, schema change, cross-cutting refactor, anything that would warrant its own ADR section | Claude authors a design note/ADR update first (design-first, per this repo's standing rule) → Codex adversarial-review → human sign-off. Gemini independent read required only if Claude and Codex disagree, or if the change is large enough that a second reviewer would need to chunk it (Gemini's context-size case). |
| **Deterministic modules** (Ledger Builder, Quant Gate, Evidence Store/Normalizer, consulting-intelligence validators/ranker — P1–P3 core) | Any edit to `ledger_builder.py`, `quantcheck.py`, `evidence_normalizer.py`, `evidence_store.py`, `consulting_validators.py`, `recommendation_ranker.py` | **Mandatory**, not "encouraged": Claude authorship + Codex adversarial-review + a passing regression test before the change is considered complete. This upgrades §6c's "strongly encouraged" to a hard gate — the one real data point (three real bugs in this exact code) is the justification. |
| **Executive reporting modules** | `report-writer`, `render_report`, tie-out/consistency-check logic — anything that shapes what a client reads | Same gate as deterministic modules. The report is the actual deliverable; a silent bug here is a bug in front of a client, not just in a test suite. |

## Conflict resolution rules

1. **A factual/mechanical disagreement ("is this actually a bug?") is never
   settled by argument — it is settled by reproduction.** Write a standalone
   script or failing test that demonstrates the claim before trusting it,
   regardless of which model made the claim. This is not new: every Codex
   finding accepted into this codebase (§6c) was independently reproduced
   first. The rule generalizes to any model, including Claude's own claims.
2. **A judgment/architecture disagreement that no test can settle** (e.g.,
   "should this be one package or two") escalates to a third independent
   read — Gemini, once verified installed — specifically because it is a
   different model family than either party to the disagreement. If the
   three still disagree, or Gemini is unavailable, escalate to the human
   (project owner), who makes the final call. No model's opinion
   unilaterally overrides another's without either evidence or a human
   decision.
3. **A claim of "fixed" or "verified" is not accepted on narrative alone.**
   The same standard applies whether the claim comes from Claude, Codex, or
   Gemini: show the before/after (failing test → passing test, or a repro
   script's output changing), then lock it in as a regression test.
4. **Silence is not agreement.** If a review pass produces zero findings,
   that is a data point ("this reviewer, at this depth, found nothing"), not
   proof of correctness — it does not substitute for the gate a tier
   actually requires.

## Evidence requirements before accepting any recommendation

- **Correctness claims** ("this is a bug," "this is fixed") require a
  reproducible artifact — a failing test before and a passing test after, or
  a standalone repro script — never the model's description of what it
  believes happened.
- **Performance claims** require a benchmark number (before/after), not an
  assertion that something "should be faster."
- **Security claims** require either a concrete exploit/repro path or a
  specific named vulnerability class and location — not a general "this
  looks risky."
- **Architecture recommendations** must name the specific existing
  code/tests/ADRs the recommending model actually read before proposing a
  change — consistent with this ADR's own evidence discipline (§1's "already
  exists in `packages/`" table was built the same way: verified against real
  code, not assumed from the spec).

## Failure modes & fallback

- **Codex absent/unauthenticated/rate-limited:** fall back to Claude for the
  task (unchanged from §6c). Nothing in this repo depends on Codex existing.
- **Gemini not adopted into this workflow (the current state — installed but
  deliberately not wired in):** every rule above that names Gemini simply does
  not fire; the Medium/Major/Deterministic tiers still function on Claude +
  Codex alone. Gemini is additive, never load-bearing.
- **All delegated models absent:** every task in the responsibility matrix
  can be done by Claude directly, at higher review risk for the
  Major/Deterministic/Executive tiers — in that case, flag explicitly that
  the change shipped with single-model review, don't silently treat it as
  equivalent to a dual-reviewed change.
- **A delegated result is bad:** treat it like a bad PR from a contractor —
  reviewed, revised, or discarded, never auto-merged. Unchanged from §6c.

## Relationship to other documents

- [Codex-Workflow.md](Codex-Workflow.md) — Codex's installation, security
  posture, and command reference. This document assumes that one and adds
  the cross-model governance layer on top.
- [ADR-010 §6c](../architecture/ADR-010-Consulting-Operating-System.md) —
  the original two-model (Claude/Codex) architectural record for the P1–P3.5
  Codex integration.
- [ADR-010 §6d](../architecture/ADR-010-Consulting-Operating-System.md) —
  the architectural record for this three-model governance model (Phase
  3.6). This file is the operational detail; §6d is the decision record.
