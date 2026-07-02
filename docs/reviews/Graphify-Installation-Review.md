---
title: Graphify Installation Review
date: 2026-07-02
graphify-version: 0.9.3 (PyPI `graphifyy`, uv tool, pinned)
baseline: repo clean at 642696f before integration
verdict: SAFE TO CONTINUE
---

# Graphify Installation Review

Graphify was established as the Knowledge Layer indexer defined by ADR-003. The
work was **verification-first**: every capability ADR-003 marks as
`[GRAPHIFY-ASSUMPTION]` was tested against the real tool — in an isolated scratch
vault so the repository vault could remain empty as required — before anything was
wired into the repo. The result is the exact ADR-003 §4 vault structure, an
initial empty knowledge graph, scoped indexing, and MCP exposure — with zero
files deleted and three small, explained modifications.

---

# Installation Summary

- **Graphify version:** `0.9.3` (PyPI package `graphifyy`), installed as a uv
  tool providing the `graphify` and `graphify-mcp` executables. The tool
  environment was re-pinned during this work as
  `uv tool install --force graphifyy==0.9.3 --with watchdog --with mcp` — the two
  extras are required for watch mode (`watchdog`) and the MCP server (`mcp`); a
  plain reinstall without them silently loses both (verified: the MCP server
  failed with `ModuleNotFoundError: mcp` after an extras-free reinstall, and was
  restored by re-adding the extra). This exact command is the canonical
  (re)install for this machine.
- **Installation method (in-repo):** no `graphify … install` variant was
  executed. Integration is three explicit, minimal touch points:
  1. `make vault-index` — deterministic reindex of `knowledge-vault/` only
     (runs from inside the vault so every cache/output lands in
     `knowledge-vault/graphify-out/`).
  2. `.mcp.json` — a second MCP server, `graphify`, serving
     `knowledge-vault/graphify-out/graph.json` over stdio.
  3. `.gitignore` — the regenerable `knowledge-vault/graphify-out/` excluded.
- **Features enabled:**
  - Deterministic (no-LLM) markdown indexing of the vault: document + heading
    nodes, `contains` edges, wikilink → `references` edges.
  - Graph artifacts: `graph.json` (canonical), `graph.html` (interactive
    visualization), `GRAPH_REPORT.md`, incremental `manifest.json`
    (per-file mtime + AST/semantic hashes).
  - Graph CLI: `query` (BFS/DFS traversal), `path`, `explain`, `affected`,
    `tree`, `merge-graphs`, `benchmark`.
  - MCP server (`graphify-mcp`, stdio): 10 tools — `query_graph`, `get_node`,
    `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`,
    `shortest_path`, plus PR-triage tools.
  - Clustering/community detection (deterministic; LLM only for community
    *naming*, which is not used).
- **Features intentionally disabled / not used:**
  - **`graphify claude install`** — would write a Graphify section into
    `CLAUDE.md` and register a global PreToolUse hook. Forbidden by this task's
    constraints (no CLAUDE.md changes, no global hooks). **Not run.**
  - **`graphify hook install`** — git post-commit/post-checkout hooks. Not run
    (no hooks; reindex stays deliberate via `make vault-index`).
  - **LLM semantic extraction / community labeling** (`extract --backend`,
    `label`) — not needed for the empty vault; deterministic pass only. No API
    keys configured or required.
  - **`--global` cross-repo graph merging** — out of scope.
  - **Source-code indexing** — explicitly avoided; see Indexing scope below.

---

# Repository Changes

Baseline: clean tree at `642696f`. Verified via `git status` / `git diff`.

**New:**

| Path | What it is |
|---|---|
| `knowledge-vault/` — `frameworks/ playbooks/ industries/ companies/ kpis/ engagements/ lessons/ templates/ _attachments/ _meta/` (each with `.gitkeep`) | The ADR-003 §4 vault structure, **exactly** as specified, empty as required |
| `knowledge-vault/.obsidian/` — `app.json`, `appearance.json` (both `{}`), `.gitignore` (excludes `workspace.json`, `cache/`) | Minimal Obsidian vault config; volatile UI state ignored |
| `knowledge-vault/graphify-out/` *(gitignored, on disk)* | The generated initial graph: `graph.json` (1 node, 0 edges), `graph.html`, `GRAPH_REPORT.md`, `manifest.json` |
| `docs/reviews/Graphify-Installation-Review.md` | This review |

**Modified:**

| Path | Change | Why |
|---|---|---|
| `Makefile` | `vault-index` target added (+ `.PHONY`) | The single sanctioned way to reindex; `cd knowledge-vault && graphify update . --force` keeps all artifacts inside the vault (a repo-root invocation was observed leaving a stray cwd-relative `manifest.json` cache at the root — running from inside the vault eliminates it) and structurally cannot index source code |
| `.mcp.json` | `graphify` server entry added (stdio, `--graph knowledge-vault/graphify-out/graph.json`, `autoStart: false`) | ADR-003 §6's exposure contract: the graph is exposed to agents "via a query API, an MCP tool, or Ruflo's store" — this is the MCP option, verified live |
| `.gitignore` | +2 appended lines (`knowledge-vault/graphify-out/`) | Index artifacts are regenerable machine outputs (`make vault-index`); committing them would churn every reindex |

**Deleted:** none. Protected-asset proof: `git diff --stat -- docs/ packages/
tests/ pyproject.toml CLAUDE.md plugins/` → **empty**; `make check` green after
integration (ruff/black/mypy --strict, 110 tests).

**Machine-level (not repo) change:** the graphifyy uv-tool environment now pins
`watchdog` + `mcp` extras (command above).

---

# Knowledge Layer Verification

| Item | Result | Evidence |
|---|---|---|
| **Obsidian vault** | ✅ | `knowledge-vault/` is a valid Obsidian vault (`.obsidian/` config present; volatile workspace state gitignored). Note: Graphify has **no "export to Obsidian" subcommand** in 0.9.3 — its Obsidian compatibility is *vault-native reading* (markdown + `[[wikilinks]]` parsed directly), which is what ADR-003 actually requires (Graphify reads the vault; Obsidian is the human plane). |
| **Graphify CLI** | ✅ | `update` (deterministic, "no LLM needed"), `query` (BFS traversal returned correct nodes/edges in the scratch vault), `path`/`explain`/`tree` available. |
| **MCP support** | ✅ | `graphify-mcp` stdio handshake verified twice: scratch graph (`tools/list` → 10 tools) and in-repo empty graph (`tools/call graph_stats` → "Nodes: 1, Edges: 0, Communities: 1"). Registered in `.mcp.json` as server `graphify`. |
| **graph.json** | ✅ | Generated for the empty vault: 1 node, 0 links. Scratch-vault validation of real content: 2 markdown notes → 4 nodes (document + heading), `contains` edges, and wikilink → `references` edges, all with `source_file`/`source_location` provenance. |
| **graph.html** | ✅ | Generated by full `update` (≈15 KB interactive visualization; plus `GRAPH_REPORT.md`). `--no-viz` available for CI. |
| **graph export** | ✅ (with a correction) | Available export surfaces: `graph.json` (canonical, portable), `graph.html`, `GRAPH_TREE.html` (`tree`), Mermaid call-flow HTML, `merge-graphs`. **No Neo4j export subcommand exists in 0.9.3** — a previously recorded capability claim that this verification corrects. ADR-003 §12 (future graph DB) is unaffected: `graph.json` is a portable typed node/edge list. |
| **watch mode** | ⚠️ Exists; **code-scoped** | `graphify watch` runs (after adding `watchdog`) and was proven to rebuild on a `.py` change — but it does **not** trigger on `.md` changes. For the vault, the reindex trigger is therefore **manual/scheduled** (`make vault-index`), which is one of the three trigger options ADR-003 §6 explicitly lists. |
| **Indexing scope** | ✅ Vault only | Indexing is path-scoped by invocation; the only committed entry point is `make vault-index`, which cannot see `packages/`. Verified: no `graphify-out` exists anywhere outside `knowledge-vault/`; the root manifest cache observed during testing referenced **only vault files** (no source code was ever indexed) and the cwd fix eliminates it. Minor scope noise: `.obsidian/app.json` is indexed as 1 node (`.graphifyignore` was tested and is **not honored** in 0.9.3); harmless, disappears into insignificance once real notes exist. |

---

# ADR-003 Compatibility

| ADR-003 section | Verdict | Why |
|---|---|---|
| §1 Overall architecture | **Compatible** | The three planes now physically exist: human (Obsidian vault), machine-index (Graphify graph + MCP), memory (Ruflo hybrid store, installed previously). |
| §2 Component responsibilities | **Compatible** | Graphify occupies exactly the indexer seat; nothing else was given its responsibilities. |
| §3 Knowledge lifecycle | **Requires Extension** | Authoring → indexing → retrieval → curation flows are M2–M3/M9 milestones; only the substrate exists (by design of this task). |
| §4 Vault structure | **Compatible** | Directory-for-directory match with the ADR tree, including `_attachments/`, `_meta/`, `.obsidian/`. |
| §5 Note metadata schema | **Compatible / Requires Extension** | The schema is an authoring convention — nothing to conflict with. Enforcement (validation of `source`, frontmatter shape) is not native to Graphify → the §10 governance hook must be built (M2). |
| §6 Indexing workflow | **Requires Extension** (assumptions now measured) | Verified ✓: manual/scheduled trigger; incremental reindex (manifest with per-file hashes); wikilinks → associative `references` edges with provenance; exposure via MCP. Not native ✗: **frontmatter → typed edges** (the deterministic pass creates document/heading nodes but does not translate `industry:`-style fields into typed edges); **vector index over note chunks** (no embedding in the deterministic pass — Ruflo's 384-dim vector memory, already installed, is the natural provider per §7/§12); **quarantine of governance-failing notes**. Caveat: wikilink targets resolve **note-relative**, so vault-root-style links (`[[kpis/x]]` from inside `frameworks/`) mis-resolve — either an authoring convention (relative links) or M2 normalization is needed. |
| §7 Retrieval workflow | **Requires Extension** | The thin retrieval interface belongs to the Knowledge Agent (M3); both backends it will compose (graph MCP + Ruflo vector memory) are now live. |
| §8 Knowledge Agent | **Requires Extension** | M3 scope; substrate ready. |
| §9 Knowledge Curator | **Requires Extension** | M9 scope; vault write-targets (`companies/`, `engagements/`, `lessons/`) exist. |
| §10 Governance | **Requires Extension** | No native validation/quarantine in Graphify 0.9.3; to be built at M2 (e.g., a pre-index lint over frontmatter). |
| §11 Versioning | **Requires Extension** | `manifest.json` provides per-file hashes/mtimes (a de-facto incremental version record); the ADR's explicit index build-id stamp is a small M2 addition. |
| §12 Future graph DB | **Compatible** | `graph.json` is a portable typed node/edge list; `merge-graphs` exists; the MCP exposure keeps the backend swappable exactly as §12 requires. |

**No section is in Conflict.** Every gap is an extension the roadmap already
assigns to M2–M3/M9, consistent with ADR-003's own `[GRAPHIFY-ASSUMPTION]`
discipline — the assumptions are now replaced by measured facts.

---

# Risks

- **Configuration risks:**
  - The uv-tool environment is **extras-fragile**: any future
    `uv tool install --force graphifyy` without `--with watchdog --with mcp`
    silently breaks the MCP server (observed during this work). The canonical
    reinstall command is recorded above and in project memory.
  - `.mcp.json` invokes bare `graphify-mcp` — requires `~/.local/bin` on PATH
    for the MCP client environment (standard for uv tools on this machine).
  - **Never run `graphify claude install` / `graphify install` in this repo** —
    it writes to `CLAUDE.md` and registers a global PreToolUse hook, both
    standing prohibitions here.
- **Indexing risks:**
  - **Frontmatter is not typed-edge parsed** and **wikilinks resolve
    note-relative** — if M2 authors notes assuming ADR-003 §6's full parse, the
    graph will be structurally poorer than expected. Mitigation is scheduled M2
    work (pre-index normalization or a typed-edge exporter) and a vault
    authoring convention for links.
  - No `.graphifyignore` support: `.obsidian/` config files enter the graph as
    noise nodes (currently 1). Watch for growth; a pre-index filter is a
    one-line M2 mitigation.
  - Reindex is **manual** (`make vault-index`) — stale-graph risk between
    authoring and reindexing; acceptable while the vault is empty, and §6
    explicitly permits scheduled/manual triggers. Revisit at M2 (git
    post-commit hook is the natural upgrade, deliberately not installed today).
- **Future maintenance risks:**
  - graphifyy is a fast-moving 0.x tool; version is pinned at 0.9.3 and
    upgrades should re-run this review's verification checklist (especially:
    md parsing behavior, MCP tool surface, export surfaces).
  - The graph server reads a **static** `graph.json` — after each reindex the
    `graphify` MCP server must be restarted to serve the new graph (session
    lifecycle concern for M3's Knowledge Agent).
  - Two MCP servers (`claude-flow`, `graphify`) now live in `.mcp.json`; both
    are stdio-spawned per session — low but nonzero startup overhead.

---

# Recommendation

## **SAFE TO CONTINUE**

The Knowledge Layer foundation exists exactly as ADR-003 defines it: the vault
structure is a directory-for-directory match of §4, empty as mandated; the
initial knowledge graph is generated, inspectable, and served over MCP; indexing
is structurally scoped to the vault and cannot reach source code; and every
ADR-003 `[GRAPHIFY-ASSUMPTION]` has been converted into a verified fact or a
scheduled M2–M3 extension, with no conflicts. The repository's protected assets
are byte-identical to the baseline, the quality gate is green, and the three
modifications (Makefile, `.mcp.json`, `.gitignore`) are minimal and reversible.

Operational notes: reindex with `make vault-index`; restart the `graphify` MCP
server after reindexing; keep the canonical uv-tool reinstall command; M1.7
remains gated on approval of `docs/implementation/M1.7-Design.md` and is
untouched by this integration.
