---
title: Ruflo Installation Review
date: 2026-07-02
ruflo-version: 3.16.3 (pinned)
baseline: repo clean at c2a5527 before installation
verdict: SAFE TO CONTINUE
---

# Ruflo Installation Review

Ruflo was installed into the StratAgent repository as the orchestration
foundation. The installation was **reconnaissance-first and curated**: `ruflo init`
was never executed inside the repository. It was first run three times in isolated
scratch directories to observe its exact behavior; that evidence drove a
staging-copy install that is **purely additive** — zero protected files were
modified, and the full Python quality gate passes unchanged afterward
(`make check`: ruff/black/mypy --strict clean, 110 tests passed).

**Why init was not run in-repo (recon evidence):**
1. `.claude/agents` and `.claude/skills` in this repo are **symlinks into
   `plugins/ruflo-stratagent/`** (the plugin source of truth). A controlled test
   with the same symlink layout proved `ruflo init` writes its stock files
   **through the symlinks** into the target directory (18 agent files + 30 skills
   landed inside the simulated plugin). Running init in-repo would have polluted
   the plugin.
2. A test with a pre-existing `CLAUDE.md` proved init **skips** it without
   `--force` (file byte-identical after init) — so `CLAUDE.md` was never at risk,
   but the agents/skills hazard alone ruled out in-repo init.
3. The `--skip-claude` flag was tested and found **ineffective** in 3.16.3 (the
   `.claude/` tree was created anyway) — it could not be relied on for safety.

---

# Installation Summary

- **Ruflo version:** `3.16.3` (npm `dist-tags`: latest = alpha = v3alpha = 3.16.3),
  **pinned exactly** via `package.json` `devDependencies` + `package-lock.json`
  (per ADR-001's risk mitigation: "pin versions; isolate Ruflo behind the
  Tool/Memory contracts").
- **Installation method:** staging-copy.
  1. `npm install --save-exact --save-dev ruflo@3.16.3` (new `package.json`).
  2. `npx ruflo@3.16.3 init --no-global` executed in an isolated scratch
     directory to produce canonical artifacts.
  3. Curated artifacts copied into the repo: `.mcp.json`, `.claude/settings.json`,
     `.claude/helpers/`, `.claude-flow/`.
  4. One curated edit to the generated `.mcp.json` (see Files modified).
  5. Runtime validated in-repo: `ruflo init check` → "RuFlo is initialized";
     `ruflo memory init` + `memory stats` → semantic memory operational
     (all-MiniLM-L6-v2, 384-dim, HNSW available); MCP stdio handshake →
     `initialize` OK, **317 tools listed**.
- **Installed components:**
  - **MCP server registration** — `.mcp.json`, server name `claude-flow` running
    the *pinned local* `ruflo mcp start` (tools surface as `mcp__claude-flow__*`,
    which is exactly the prefix the `/solve-case` orchestrator already detects).
  - **Hooks** — `.claude/settings.json`: 10 hook types (PreToolUse, PostToolUse,
    UserPromptSubmit, SessionStart, SessionEnd, Stop, PreCompact, SubagentStart,
    SubagentStop, Notification) routed through `.claude/helpers/hook-handler.cjs`
    / `auto-memory-hook.mjs`, plus statusline, scoped permissions
    (`mcp__claude-flow__*`, `npx claude-flow*`, `node .claude/*`) and `.env` read
    denials.
  - **Helpers** — `.claude/helpers/` (42 files: hook handler, auto-memory,
    statusline, learning/metrics/checkpoint utilities the hooks invoke).
  - **V3 runtime** — `.claude-flow/` (config.yaml: hierarchical-mesh topology,
    max 15 agents, hybrid memory backend + HNSW, learning bridge; CAPABILITIES.md;
    metrics/security seeds; upstream `.gitignore` for data/logs/sessions).
  - **Node toolchain** — `package.json`, `package-lock.json`; `node_modules/`
    (437 top-level packages, gitignored).
- **Deliberately NOT installed** (curated exclusions, each reversible later):
  - Ruflo's generated `CLAUDE.md` (repo has its own project guide).
  - 17 stock dev agents (`coder`, `sparc`, `consensus`…) — StratAgent's agent
    roster is defined by ADR-005; stock dev agents would pollute the consulting
    roster. The MCP tools do **not** depend on these files.
  - 30 stock skills and 148 command docs — generic dev-swarm workflow docs;
    omitted to keep the skill/command palette focused on `/solve-case`.
  - The `~/.claude/CLAUDE.md` global pointer block (`--no-global`) — installation
    was scoped strictly to this repository.
- **Files added:** see Repository Diff.
- **Files modified:** `.gitignore` **only** (see Repository Diff for the exact
  change and why); plus one edit to the *newly generated* `.mcp.json` before
  first commit (pinning, documented below).
- **Files removed:** **none.**

---

# Repository Diff

Baseline: clean tree at `c2a5527`. Verified with `git status`/`git diff`.

**New (committed):**

| Path | What it is |
|---|---|
| `.mcp.json` | MCP server registration (server `claude-flow` → pinned local ruflo) |
| `.claude/settings.json` | Ruflo hooks (10 types), statusline, permissions, env, `claudeFlow` config block |
| `.claude/helpers/` | 42 helper scripts invoked by the hooks |
| `.claude-flow/.gitignore`, `CAPABILITIES.md`, `config.yaml`, `metrics/*.json` (3), `security/audit-status.json` | V3 runtime config + seeds (upstream’s own gitignore excludes its volatile dirs) |
| `package.json` | Pins `ruflo@3.16.3` (exact) as the only dependency; `private: true` |
| `package-lock.json` | Full dependency lock |
| `docs/reviews/Ruflo-Installation-Review.md` | This review |

**New (runtime, gitignored — created by install verification, regenerable):**
`node_modules/`, `.claude/memory.db`, `.swarm/` (memory.db + WAL + schema),
`ruvector.db`, `.claude-flow/data|logs|sessions`.

**Modified:**

| Path | Change | Why |
|---|---|---|
| `.gitignore` | +10 appended lines: `node_modules/`, `.claude/memory.db`, `.claude-flow/data/`, `.claude-flow/logs/`, `.claude-flow/sessions/`, `.swarm/`, `ruvector.db` (+2 comment/blank) | Ruflo's runtime creates machine-local databases and caches that must never be committed. Smallest possible change: pure append, no existing line touched. |
| `.mcp.json` *(pre-commit curation of a new file)* | Generated args `["-y","ruflo@latest","mcp","start"]` → `["-y","ruflo","mcp","start"]` | The generated config floats on `@latest`, violating the pin-versions policy; bare `ruflo` resolves to the locked local install. Single array-element change. |

**Deleted:** none (`git ls-files --deleted` = 0).

**Protected-asset proof:** `git diff --stat -- docs/ packages/ tests/
pyproject.toml CLAUDE.md plugins/` → **empty**. ADRs, implementation docs, the
state package, tests, `pyproject.toml`, `CLAUDE.md`, and the plugin are
byte-identical to `c2a5527`. Both `.claude/agents` and `.claude/skills` remain
symlinks into the plugin.

---

# Configuration Review

- **MCP configuration — verified working.** `.mcp.json` registers one stdio
  server, `claude-flow` (name kept as generated: it yields the
  `mcp__claude-flow__*` tool prefix the orchestrator skill and the generated
  permission allowlist both expect). Live handshake test: `initialize` returned
  `serverInfo {name: ruflo, version: 3.0.0}`; `tools/list` returned **317 tools**
  (agent_spawn/execute/…, swarm_init, memory_*, etc.). `autoStart: false` — the
  server starts when Claude Code loads it; the user must approve the project MCP
  server on first use.
- **Hooks — installed, not yet exercised.** 10 hook types wired to
  `hook-handler.cjs`/`auto-memory-hook.mjs` with a `$HOME` fallback if the
  project copy is missing (both are present in-project). `CLAUDE_FLOW_HOOKS_ENABLED=true`.
  Note: these hooks will run Node on every tool call in *future* Claude Code
  sessions in this repo — this is the intended harness integration, flagged
  under Risks.
- **Memory — verified working.** `ruflo memory init` succeeded; semantic search
  ready (Xenova/all-MiniLM-L6-v2, 384-dim, SIMD on; HNSW available). Backends
  created: `.swarm/memory.db`, `.claude/memory.db`, `ruvector.db` — all
  gitignored. Consistent with ADR-002/ADR-003: the **event log remains the
  source of truth; Ruflo memory is a mirror/index** (wired to engagements at
  M7–M8, not now).
- **Agents — intentionally none from Ruflo.** `.claude/agents` still symlinks to
  the plugin's 7 consulting agents. Stock dev agents excluded (rationale above).
  `mcp__claude-flow__agent_spawn` and swarm tools are fully available regardless.
- **Skills — intentionally none from Ruflo.** `.claude/skills` still symlinks to
  the plugin (`solve-case` intact). The 30 stock skills can be added later via
  `ruflo init skills` after temporarily detaching the symlink, if ever wanted.
- **Commands — intentionally none from Ruflo** (148 generic docs excluded;
  `/solve-case` remains the single entry point per ADR-001).
- **Plugins — untouched.** `plugins/ruflo-stratagent/` byte-identical;
  marketplace manifest untouched; plugin ↔ harness composition unchanged.
- **Settings — reviewed.** `.claude/settings.json` `claudeFlow` block: swarm
  (hierarchical-mesh, 15 agents), memory (hybrid + HNSW), learning, daemon
  (disabled by default — no daemon was started), security defaults;
  `modelPreferences` (default `claude-opus-4-8`, routing `claude-haiku-4-5`);
  `permissions.deny` blocks reading `.env*`. No secrets present. The statusline
  override and experimental `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` env are
  upstream defaults, noted under Risks.

---

# Architecture Compatibility (vs ADR-001…ADR-005)

| ADR-001 layer | Verdict | Why |
|---|---|---|
| 1 · Presentation (Claude Code) | **Compatible** | Ruflo integrates via standard Claude Code surfaces (MCP + hooks + settings); `/solve-case` remains the entry point. |
| 2 · Orchestration (Ruflo) | **Compatible** | This layer *is* Ruflo in ADR-001; the installed MCP server provides the coordination tools (swarm_init, agent_spawn, task orchestration) the ADR assigns here. ADR-001's core constraint is preserved: **Ruflo orchestrates, the host executes** — nothing installed executes agents by itself (`autoStart: false`, no daemon started). |
| 3 · Consulting Intelligence (agents/skills) | **Requires Extension** | Deliberately empty on the Ruflo side: ADR-005's 16 consulting agents are StratAgent's to build (M4–M6) on top of Ruflo's spawn/coordination tools. Stock dev agents were excluded *because* this layer belongs to ADR-005. |
| 4 · Knowledge | **Requires Extension** | Ruflo's vector memory (384-dim semantic search, HNSW) is now available as the retrieval substrate, but ADR-003's vault, Graphify graph, and curation flows are unbuilt (M2–M3). No conflict — ADR-003 already designates Ruflo memory as one of its three stores. |
| 5 · Memory | **Compatible** | Hybrid AgentDB backend installed and verified. Critically, it does **not** displace the Engagement State: ADR-002's event log stays the single source of truth; Ruflo memory is the mirror (M7–M8 wiring). The `packages/state` implementation is untouched. |
| 6 · Tool layer | **Compatible** | 317 MCP tools registered under the expected `mcp__claude-flow__*` prefix; the orchestrator's existing detection logic needs no change. |
| 7 · Infrastructure (Ruflo runtime) | **Compatible** | `.claude-flow/` runtime + pinned package is precisely the "Ruflo as infrastructure, pinned and swappable" posture ADR-001 mandates. |

**ADR-002 (Engagement State):** no interaction — no state-package file changed;
the append/persistence design (M1.7-Design.md) is unaffected. **Compatible.**
**ADR-004 (Knowledge Library):** no interaction. **Compatible (Not Started).**
**ADR-005 (Agent Specs):** the spawn/coordination substrate its agents will run
on is now present; contracts unchanged. **Compatible / Requires Extension.**

No layer is in **Conflict**.

---

# Risks

- **Overwritten files: none.** Proven by empty tracked-file diff (only
  `.gitignore` modified, by append). The *avoided* risk is documented above:
  in-repo `ruflo init` would have written 48+ files into the plugin through the
  `.claude` symlinks — this is now a standing operational caution: **never run
  `ruflo init`/`init --force` in this repo without first detaching
  `.claude/agents` and `.claude/skills`.**
- **Conflicting configuration: low.** No pre-existing `.mcp.json`/settings to
  collide with. Two upstream defaults worth awareness: the settings statusline
  override, and `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (experimental feature
  flag). Both are trivially removable from `.claude/settings.json` if unwanted.
- **Dependency conflicts: none with Python.** The Node tree (437 packages) is
  fully disjoint from the uv-managed Python environment; `make check` passes
  identically post-install. Within Node: npm reported deprecated transitive
  packages (uuid@9, glob@10, koa-router@14) and **blocked two postinstall
  scripts pending approval** (`agentdb`, `tldjs` — npm allow-scripts policy).
  Memory verification succeeded regardless (JS fallback); if native AgentDB
  acceleration is wanted later, run `npm approve-scripts` and re-verify.
- **Duplicated functionality: two known, both already governed.**
  (1) Ruflo memory/persistence vs the M1.8 file-backed event log — resolved by
  ADR-002/ADR-003: log is truth, memory is mirror; nothing installed changes
  that. (2) Ruflo hooks' auto-memory/learning vs StratAgent's evidence ledger —
  independent planes (session telemetry vs engagement facts); watch at M7–M8
  when they are wired together.
- **Future maintenance risks:**
  - **Alpha-velocity upstream.** ruflo 3.x moves fast; the exact pin plus
    `package-lock.json` freezes it. Upgrades must be deliberate
    (`npm install -E ruflo@<new>` + re-run this review's verification steps),
    and `ruflo init upgrade` must be treated with the same symlink caution.
  - **Curated install drift.** Because stock agents/skills/commands were
    excluded, a future `init`-based upgrade may try to (re)create them; the
    curation decision is recorded here and should be re-applied on upgrade.
  - **Hook latency/supply chain.** Every tool call in future sessions runs
    `hook-handler.cjs`. It is local, pinned code, but it is upstream code in the
    hot path; disable by removing hook blocks from `.claude/settings.json` if it
    misbehaves.
  - **Metrics churn.** `.claude-flow/metrics/*.json` are committed (upstream's
    own gitignore excludes only data/logs/sessions); if the runtime updates them
    noisily, move them into `.gitignore` in a follow-up.

---

# Recommendation

## **SAFE TO CONTINUE**

The installation is additive, pinned, verified end-to-end (MCP handshake with
317 tools, memory subsystem live, `init check` passing), and provably
non-destructive: every protected asset — docs, ADRs, implementation docs,
`packages/state`, tests, `pyproject.toml`, `CLAUDE.md`, the plugin — is
byte-identical to the pre-install commit, and the full Python quality gate is
green. The frozen v1.0 architecture is unmodified; Ruflo now sits exactly where
ADR-001 places it: the pinned, swappable infrastructure layer underneath a
consulting vertical that has not changed.

Operational notes for the next session: approve the `claude-flow` MCP server
when Claude Code prompts; do not run `ruflo init` variants in-repo without
detaching the `.claude` symlinks; M1.7 remains gated on approval of
`docs/implementation/M1.7-Design.md` and is unaffected by this installation.
