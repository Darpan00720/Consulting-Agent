# Platform Operations (ADR-013 W6)

**Status:** Operational reference for the composed platform. Not an ADR —
per W6's own constraint ("no new ADR"), this is the document a contributor or
operator actually reads day to day, the same split ADR-010 §6c established
for `Codex-Workflow.md` and `Engineering-Workflow.md`. The architectural
record for the routing/agent/memory/tool platform decisions lives in
ADR-013 and this repo's session history; this document is how you run it.

This file replaces ten separately-requested documents (platform architecture
summary, startup sequence, dependency graph, extension guide, plugin guide,
operational runbook, configuration reference, failure recovery guide,
deployment checklist, architecture decision summary) with one consolidated,
cross-referenced reference — the same judgment call `Engineering-Workflow.md`
already made for a comparably broad brief.

---

## 1. Platform architecture summary

```
User
  │
  ▼
Workflow Router (W1, app.workflow.router)      — classification only
  │
  ▼
Dispatcher (W2, app.workflow.dispatcher)        — execution only
  │
  ▼
Agent Runtime (W3, app.agents.runtime)          — agent orchestration
  │
  ▼
Agent (app.agents.builtin)                      — business logic only
  │
  ├──▶ Memory Platform (W4, app.memory)          — memory orchestration
  ├──▶ Tool Platform (W5, app.tools)              — external integrations
  └──▶ Provider Router (ADR-012, app.pipeline.providers) — provider selection
         │
         ▼
       Provider ──▶ LLM
```

`app.platform` (W6) is the **composition root** sitting beside this stack,
not inside it — it constructs every layer above via that layer's own public
factory and wires the results into one `Platform` object. It owns no
business logic and moves no responsibility; see §9 for the compliance audit.

## 2. Startup sequence

```
PlatformConfig.from_env()
        │  (env vars + defaults + app.config composition; §7 Configuration)
        ▼
targets.default_registry()          ─┐
builtin.default_agent_registry()     │  each built independently — none
memory_adapters.default_memory_registry()  depends on another's OUTPUT to
tool_adapters.default_tool_registry() │  construct (a real, verified fact:
providers.build_chain()             ─┘  every factory takes no arguments)
        │
        ▼
AgentRuntime() / MemoryService(registry) / ToolRuntime()
        │  (explicit construction — never a layer's own singleton accessor)
        ▼
validate_platform(...)              (§5 Validation — runs BEFORE returning)
        │
   blocking issues? ──yes──▶ PlatformBootstrapError (strict=True, default)
        │no
        ▼
Platform(...)  returned — startup complete
```

**Entry point:** `app.platform.bootstrap.bootstrap(config=None, strict=True)`.
One call, one `Platform` object. No global mutable state — two calls to
`bootstrap()` produce two fully independent object graphs (proven by
`tests/test_platform_bootstrap.py::test_bootstrap_returns_independent_platforms_each_call`).

```python
from app.platform.bootstrap import bootstrap

platform = bootstrap()  # raises PlatformBootstrapError on blocking issues
# platform.workflow_registry, .agent_registry, .agent_runtime,
# .memory_registry, .memory_service, .tool_registry, .tool_runtime,
# .provider_chain, .validation_report
```

## 3. Dependency graph

```
app.platform  ──depends on──▶  app.workflow, app.agents, app.memory,
                                 app.tools, app.pipeline.providers

app.workflow  ──depends on──▶  app.agents, app.memory   (Target.invoke()
                                 delegates to AgentRuntime/MemoryService, W3/W4)

app.agents    ──depends on──▶  app.memory (optional, opt-in — memory_service
                                 param on AgentRuntime.execute(), W4 §6)

app.memory, app.tools ──depend on──▶  NOTHING above them (verified: no
                                 runtime import of app.agents/app.workflow
                                 in either package — only TYPE_CHECKING)

app.pipeline.providers ──depends on──▶  NOTHING above it (ADR-012, unchanged)
```

This is the real import graph, not an aspiration — every package boundary
above was verified when each layer was built (W1–W5) and re-verified for W6
(`tests/test_platform_integration.py::test_provider_router_untouched_by_platform_package`
confirms `app.platform` doesn't reimplement `app.pipeline.providers`).

**Honest scope note:** "dependency graph validation" (§5) is a structural
check — did each layer construct successfully in this order — not a static
import-graph analyzer. A full graph-theoretic cycle check would be
over-engineering for a composition-only phase; the graph above was verified
by hand against the actual `import` statements in each package.

## 4. Extension guide (adding a new layer-level capability)

| To add... | Do this — NO other file changes |
|---|---|
| a new Agent | Implement the `Agent` Protocol (`app.agents.agent`); register via `AgentRegistry.register()`. Proven zero-Runtime-change via `PluginAgent` tests (W3). |
| a new Memory provider | Implement `MemoryProvider` (`app.memory.provider`); register via `MemoryRegistry.register()`. Proven via `PluginMemoryProvider` tests (W4). |
| a new Tool adapter | Implement `Tool` (`app.tools.tool`); register via `ToolRegistry.register()`. Proven via `PluginTool` tests (W5). |
| a new Provider | Add to `providers.build_chain()` (ADR-012's own extensibility contract) or supply a BYOK-shaped key — unchanged by W6. |
| a new Workflow category | Add a `_INTENT_KEYWORDS`/`_CATEGORY_PRIORITY` entry (`app.workflow.router`) — unchanged by W6 (ADR-013 §8/§9). |

None of these require touching `app.platform` — `bootstrap()` picks up
whatever each `default_*_registry()`/`build_chain()` factory returns.

## 5. Plugin guide

The concrete, tested proof pattern (not just a claim) for every extensible
layer is: construct a plugin instance satisfying the layer's Protocol,
`register()` it into the REAL production registry (`default_agent_registry()`,
`default_memory_registry()`, `default_tool_registry()`), and execute it
through the UNMODIFIED Runtime/Service. See:

- `tests/test_agent_builtin.py::PluginAgent` (W3)
- `tests/test_memory_adapters.py::PluginMemoryProvider` (W4)
- `tests/test_tool_adapters.py::PluginTool` (W5)

A future integration (CrewAI, Gemini CLI, Kimi CLI, OpenAI Responses, Neo4j,
Pinecone, Weaviate — named in W5's brief, not implemented) follows the same
three-step pattern at whichever layer it belongs to.

## 6. Operational runbook

**Start the platform:**
```python
from app.platform.bootstrap import bootstrap
from app.platform.lifecycle import PlatformLifecycle

platform = bootstrap()
lifecycle = PlatformLifecycle(platform)
state = await lifecycle.start()  # READY | DEGRADED | FAILED
```

**Check health:**
```python
report = await lifecycle.health()
report.overall_state    # ComponentState
report.degraded         # bool
report.component("memory_platform")  # per-layer detail
```

**Shut down:**
```python
await lifecycle.shutdown()  # clears the memory cache; see §8 for the honest
                              # limit on what "resource cleanup" means here
```

**Restart:**
```python
new_platform = await lifecycle.restart()  # shutdown + fresh bootstrap()
```

**Trace one request end-to-end:**
```python
from app.platform.observability import attach_trace_collector, detach_trace_collector

collector = attach_trace_collector()
# ... run a request with a known trace_id ...
collector.layers_touched(trace_id)      # which layers it passed through
collector.latency_breakdown(trace_id)   # per-layer duration_ms
detach_trace_collector(collector)       # restores each logger's prior level
```

## 7. Configuration reference

`app.platform.config.PlatformConfig` (immutable — a frozen dataclass).

| Field | Source | Default |
|---|---|---|
| `environment` | `STRATAGENT_ENV` | `"development"` |
| `ollama_enabled` | **composed from `app.config.OLLAMA_ENABLED`** (not re-parsed — avoids a second, drifting source of truth) | — |
| `ollama_placement` | composed from `app.config.OLLAMA_PLACEMENT` | — |
| `local_shell_allowed_commands` | `STRATAGENT_SHELL_ALLOWLIST` (comma-separated) | `()` — nothing allowed by default (W5's local-shell two-gate design) |
| `obsidian_vault_dir` | `STRATAGENT_VAULT_DIR` | `knowledge-vault` |
| `memory_cache_ttl_s` | `STRATAGENT_MEMORY_CACHE_TTL_S` | `60.0` |
| `feature_flags` | `overrides=` at construction (no env parsing yet — declarative, extend `from_env` when a real flag is needed) | `{}` |

Every existing provider/tool/memory setting NOT listed above (API keys,
`OLLAMA_MODEL`, etc.) is unchanged and lives exactly where it already did
(`app.config`, `app.pipeline.providers`) — W6 does not introduce a second
configuration surface for settings that already have one.

## 8. Failure recovery guide

| Symptom | Likely cause | Recovery |
|---|---|---|
| `PlatformBootstrapError` at startup | A blocking validation issue (empty registry, no default memory provider, version incompatibility) | Read `exc.report.errors` — one line per issue, all reported at once (§5) |
| `lifecycle.start()` returns `DEGRADED` | One optional layer is down (typically: no LLM provider configured) | Check `lifecycle.health()`'s per-component detail; the platform still serves routing/memory/tool traffic in this state |
| `lifecycle.start()` returns `FAILED` | A structural core layer (Router/Dispatcher/Runtime) itself errored, or `aggregate_health()` crashed | This should not happen in normal operation (those layers are pure/stateless) — treat as a real bug, not an operational condition |
| An error surfaces from deep inside the stack | Normalize it through `app.platform.errors.normalize_error(exc, trace_id=...)` | Never inspect a raw exception at the platform boundary — the normalized `PlatformError` carries `category` + `recovery_guidance` |
| A raised message contains what looks like a secret | `normalize_error`/`safe_log` already redact common key shapes (Anthropic/OpenAI/Gemini/GitHub/Bearer) before logging | If a NEW key format appears, add its pattern to `_REDACT_PATTERNS` (`app.platform.errors`) |
| Resource cleanup — "did shutdown really free everything?" | **Honest limit:** no layer holds a persistent external connection (verified — Provider.call() builds its HTTP client per-call; every adapter is stateless or in-memory). `shutdown()` clears the memory cache; it cannot force-cancel work it was never given a handle to | Cancel in-flight work via that call's own `CancellationToken` (W2/W3/W5) BEFORE calling `shutdown()` |

## 9. Architecture compliance report (requirement 9's audit)

| Layer | Responsibility | W6 changes | Verified by |
|---|---|---|---|
| Workflow Router | classification only | **zero lines** | `test_workflow_router_only_classifies_never_dispatches` |
| Dispatcher | execution only | **zero lines** | `test_dispatcher_only_executes_never_classifies` |
| Agent Runtime | agent orchestration | +1 optional param (`memory_service`, W4, pre-existing) | full pre-existing suite green, unmodified |
| Memory Platform | memory orchestration | **zero lines** | `test_all_prior_layer_registries_are_reachable_unmodified` |
| Tool Platform | external integrations | **zero lines** | same |
| Provider Router | provider selection | **zero lines** | `test_provider_router_untouched_by_platform_package` |
| Agents | business logic only | **zero lines** | same |

No responsibility moved. `app.platform` is purely additive composition —
proven, not asserted, by running the entire pre-W6 test suite (609 tests)
unmodified after every W6 change (§13).

## 10. Deployment checklist (requirement 12's release readiness)

- [ ] `bootstrap(strict=True)` succeeds in the target environment (raises loudly on any blocking issue — never deploy past a swallowed error)
- [ ] `lifecycle.start()` returns `READY` or an accepted `DEGRADED` (document which degraded components are expected in this environment — e.g. no LLM key in a validation-only deploy)
- [ ] `platform.validation_report.warnings` reviewed — each one is either accepted or resolved before deploy
- [ ] At least one real end-to-end trace captured via `attach_trace_collector()` and confirmed to touch every expected layer
- [ ] `docs/operations/Ollama-Local-Runtime.md` / provider API keys configured per the target environment's actual needs (unchanged by W6)
- [ ] `lifecycle.shutdown()` exercised at least once in a staging run (confirms cache cleanup path is reachable)
- [ ] Full test suite green: `uv run pytest` (682 passing as of this phase)
- [ ] `uv run ruff check app/ tests/` clean for every file this phase touched

## Architecture decision summary (requirement 11 — not a new ADR)

W6 made exactly four load-bearing design calls, all composition, none
requiring a new ADR (per the phase's own constraint):

1. **`bootstrap()` constructs explicitly, never via each layer's own
   singleton accessor** (`default_runtime()`, `default_service()`) —
   preserves those accessors, unchanged, as each layer's own backward-
   compatible fallback for pre-W6 callers, while giving `Platform` its own
   independent, DI'd object graph.
2. **Fail-closed startup by default** (`strict=True`) — a blocking
   validation issue raises `PlatformBootstrapError` rather than returning a
   broken platform; `strict=False` exists for diagnostics tooling that wants
   to inspect what's broken.
3. **Health degrades, doesn't fail, on an optional layer being down** — the
   platform is usable (routing/memory/tools) without a configured LLM
   provider; only a genuinely broken structural core layer is `FAILED`.
4. **Trace correlation via a `logging.Handler`, not a redesign of any
   layer's logging** — and the one real bug this surfaced (a `Handler`'s own
   DEBUG level doesn't help if the `Logger` itself is still at WARNING) is
   documented at the fix site (`app.platform.observability`) as the concrete
   lesson, not just fixed silently.
