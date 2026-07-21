# Ollama Local AI Runtime

**Status:** Installed & verified 2026-07-18 on this machine (Apple M3, 8 GB).
Developer-tooling / cost-optimization layer. Like the Codex plugin, this is
orthogonal to the StratAgent *product* — the shipped consulting pipeline does
not depend on Ollama existing. See "Integration" for how it *may* be wired in.

---

## 1. Installation Report (what was actually done)

| Step | Command | Result (verified) |
|---|---|---|
| Install | `brew install ollama` | v0.32.1, deps `mlx` + `mlx-c` pulled |
| Start as login service | `brew services start ollama` | Running, PID managed by launchd, auto-restart at login |
| API | `curl localhost:11434/api/version` | `{"version":"0.32.1"}`, bound to `127.0.0.1` only |
| Model pulled | `ollama pull qwen3:4b` | 2.5 GB on disk, Q4_K_M, 262K context, tools+thinking |
| Memory tuning | (baked into plist by the formula) | `--flash-attn on --cache-type-k q8_0 --cache-type-v q8_0` confirmed in daemon log |

**Live inference benchmark (real numbers, M3 / 8 GB, machine under normal
load):**
- Runs **100% on GPU** (Metal), loaded footprint **~2.9 GB**.
- Throughput **~26–30 tokens/sec**.
- Cold load from disk **~10 s**; warm generations start immediately.
- KV cache at q8_0: **306 MiB** for a 4096-token context (half the f16 cost).

## 2. Compatibility Report

| Component | Value | Note |
|---|---|---|
| Chip | Apple M3 (arm64) | Native Metal acceleration ✅ |
| macOS | 26.5.2 | Supported ✅ |
| **RAM** | **8 GB unified** | **The binding constraint.** Shared by OS + apps + model. |
| Disk free | 81 GB | Room for ~20 small models ✅ |
| Homebrew | 6.0.11 | Install/upgrade path ✅ |
| Node / Python / uv | v26.5 / 3.14.5 / 0.11.29 | Not required by Ollama; present for app integration ✅ |

**The 8 GB reality:** a model does not get 8 GB — it gets what's left after
macOS compresses/evicts everything else (measured: ~160 MB unused, ~3.2 GB
already compressed at baseline with a dev session open). Practical ceiling for
a *daily-driver* model is **4B params at Q4 (~3 GB)**. 7–8B runs but under
memory pressure; 9B+ swaps and degrades the whole machine — excluded.

## 3. Recommended Model Comparison (only what runs on 8 GB)

| Model | Params | ~Load RAM | Ctx | Reasoning | Coding | Consulting prose | Fit |
|---|---|---|---|---|---|---|---|
| **Qwen3 4B** ⭐ installed | 4B | ~2.9 GB | 262K | Very strong (thinking mode) | Very strong | Strong | ✅ Default |
| Gemma 3 4B | 4B | ~3.3 GB | 128K | Strong | Good | **Best writing** | ✅ Add for drafting |
| Qwen3 1.7B | 1.7B | ~2.5 GB | 32K | Good/size | Good | Fair | ✅ Low-memory fallback |
| Qwen2.5-Coder 3B | 3B | ~3 GB | 32K | Fair | **Best coding/size** | Fair | ✅ Coding specialist |
| DeepSeek-R1 7B distill | 7B | ~5.5 GB | 32K | Excellent | Good | Good | ⚠️ Occasional only |
| GLM-4 9B / R1 32B+ | 9B+ | 7 GB+ | — | — | — | — | ❌ Too big for 8 GB |

**Why Qwen3 4B is the default:** best all-round reasoning + code + structured
(JSON/tool) output in the largest class that still loads without choking the
machine. Toggleable thinking mode. Native tool-calling (matters for agent use).

## 4. Final Architecture — where Ollama fits

```
                         Claude Code  (primary reasoning, orchestration, governance)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                      │
     Codex               Claude Flow             Graphify
 (independent review,   (MCP orchestration)   (code-graph MCP)
  mechanical tasks)          │
        │                    │
        └──────────┬─────────┘
                   ▼
              Ollama  (localhost:11434, OpenAI-compatible /v1)
                   │
             Qwen3 4B  (+ optional Gemma 3 4B, Qwen3 1.7B)
             local, $0/token, offline-capable
```

**When Claude should use Ollama:** high-volume, low-stakes, well-scoped work
where a wrong answer is cheap and caught downstream — bulk summarization,
first-draft generation, classification/tagging, local embeddings, quick
reformatting, offline work. **Not** for final board-ready reasoning or
anything on StratAgent's deterministic-verification path (that's code, not any
LLM).

**When Codex should use Ollama:** as a cheap local pre-pass for mechanical
scaffolding before spending Codex/Claude tokens — e.g. draft a boilerplate
test file locally, then have Codex/Claude review and finalize.

**Concrete product integration option (not yet wired):** the dashboard already
runs a multi-provider fallback chain (`apps/dashboard/backend/app/pipeline/
providers.py`). Ollama exposes an OpenAI-compatible endpoint at
`http://localhost:11434/v1`, so it can be added as a **local, zero-cost tail
provider** in that chain for dev/offline runs — subject to the same governance
gates every other provider passes through. A 4B model is a weak analyst, so it
belongs at the *end* of the chain (last-resort/offline), not the head.

**Why local models are bounded here, honestly:** at 4B on 8 GB, Ollama is a
cost-saver for cheap tasks, not a Claude/Codex replacement for hard reasoning.
Treat it as the free tier of a tiered stack.

## 5. Ollama Command Cheat Sheet

```bash
# Service (via Homebrew — auto-restarts at login)
brew services start ollama       # start now + at login
brew services stop ollama        # stop + disable autostart
brew services restart ollama     # restart (after upgrades/config)
brew services info ollama        # status (Running: true/false)

# One-off foreground server (no autostart) — flags already in the service:
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve

# Models
ollama list                      # installed models
ollama pull qwen3:4b             # download / update a model
ollama show qwen3:4b             # metadata (ctx, quant, capabilities)
ollama rm <model>                # remove
ollama ps                        # currently loaded + memory + GPU%

# Run
ollama run qwen3:4b              # interactive chat
ollama run qwen3:4b "prompt"     # one-shot
echo "prompt /no_think" | ollama run qwen3:4b   # suppress Qwen3 reasoning

# REST API (localhost only)
curl localhost:11434/api/version
curl localhost:11434/api/generate -d '{"model":"qwen3:4b","prompt":"hi","stream":false}'
curl localhost:11434/api/chat -d '{"model":"qwen3:4b","messages":[{"role":"user","content":"hi"}],"stream":false}'
# OpenAI-compatible:
curl localhost:11434/v1/chat/completions -d '{"model":"qwen3:4b","messages":[{"role":"user","content":"hi"}]}'
```

## 6. Best Practices (this hardware)

- **Default local model:** Qwen3 4B.
- **Best coding:** Qwen3 4B (or Qwen2.5-Coder 3B if you want a lighter, code-only specialist).
- **Best consulting prose:** Gemma 3 4B (add it when you want better tone than Qwen).
- **Best reasoning:** Qwen3 4B with thinking mode ON (drop `/no_think`); accept higher latency.
- **Best low-memory fallback:** Qwen3 1.7B when other apps are open.
- **Memory optimization:** flash-attention + q8_0 KV cache are already on. Keep
  context modest (`OLLAMA_CONTEXT_LENGTH` / per-request `num_ctx`) — a 262K
  context would blow the RAM budget; the daemon defaults to 4096, which is right.
- **Apple Silicon tuning:** models auto-run on Metal (verified 100% GPU). Keep
  **one model loaded at a time** on 8 GB (`ollama ps` to check); set
  `OLLAMA_MAX_LOADED_MODELS=1` if you ever pull several.
- **Model management:** keep 2–3 models max; `ollama rm` anything unused (disk
  is fine, but fewer models = less confusion). Prefer Q4_K_M quant (the default).
- **Qwen3 gotcha:** the API `"think":false` param does **not** reliably suppress
  reasoning — append `/no_think` to the prompt for direct deliverables, or the
  model spends its whole token budget thinking out loud.

## 7. Troubleshooting Guide

| Symptom | Cause | Fix |
|---|---|---|
| `could not connect to a running Ollama instance` | daemon not started | `brew services start ollama`; confirm `brew services info ollama` shows Running: true |
| Model reply is all "Okay, the user wants…" monologue | Qwen3 thinking mode; token budget consumed by reasoning | append `/no_think` to the prompt |
| Whole Mac becomes sluggish during inference | model too big for 8 GB, swapping | use a smaller model (Qwen3 1.7B); close browser/other apps; check `ollama ps` |
| Slow first response (~10 s) | cold load from disk into GPU | expected once per model; warm calls are instant. Model unloads after ~5 min idle |
| Port 11434 in use / API unreachable | stale process or another Ollama app (cask) | `pgrep -lf ollama`; `lsof -iTCP:11434`; stop the duplicate |
| Out-of-memory / model won't load | not enough free unified memory | `OLLAMA_MAX_LOADED_MODELS=1`, smaller model, or free RAM first |
| Logs | — | `/opt/homebrew/var/log/ollama.log` (service), `~/.ollama/logs/` (client) |

## 8. Future Upgrade Roadmap

1. **Add Gemma 3 4B** for report-drafting tone; A/B it against Qwen3 on real
   consulting prompts. (`ollama pull gemma3:4b`)
2. **Wire Ollama as the offline/tail provider** in the dashboard's
   `providers.py` chain (OpenAI-compatible `/v1`), gated behind an env flag —
   dev/offline runs at $0, product governance unchanged.
3. **Local embeddings** (`ollama pull nomic-embed-text`) to replace the
   knowledge-vault's keyword retrieval with local semantic search at zero API
   cost (ties to ADR-011 item H1).
4. **Hardware headroom:** the single biggest unlock is RAM. On a 16 GB machine,
   7–8B models (Qwen3 8B, DeepSeek-R1 8B) become daily-drivers; on 32 GB+,
   14B–32B reasoning models (incl. GLM-4, DeepSeek-R1 32B) come into range.
   Nothing about this setup changes except which models you pull.
5. **Keep current:** `brew upgrade ollama` periodically; re-pull model tags to
   get updated weights (`ollama pull qwen3:4b`).

## 9. Provider Integration (dashboard runtime — implemented 2026-07-18)

Ollama is wired into the dashboard's LLM pipeline as a **first-class provider in
the existing failover chain** (`apps/dashboard/backend/app/pipeline/providers.py`).
No architecture was redesigned — Ollama's OpenAI-compatible `/v1` endpoint reuses
the exact `Provider` dataclass every cloud provider already uses, so there is no
new call path.

### Two planes — don't conflate them

The Claude/Codex/Gemini "which model does what" split (Engineering-Workflow.md,
ADR-010 §6c/§6d) is a **developer-workflow** concern. This section is the
**product runtime** provider chain the consulting pipeline calls. Codex is a dev
plugin, not a runtime provider — it is *not* in this chain and never will be.

### Provider & routing diagram

```
call_agent()  →  call_with_failover()  →  ordered chain:

  OLLAMA_PLACEMENT=last  (default, cloud-first)     OLLAMA_PLACEMENT=first (local-first)
     gemini → cerebras → … → cloudflare → ollama       ollama → gemini → cerebras → …
                                          └ $0 offline      └ $0 for every call it serves;
                                            fallback           cloud is automatic fallback
```

Placement *is* the routing lever. There is no per-task router today (all 16
agents share one chain, by design) — see "Migration notes" for why finer routing
is a separate, approval-gated change rather than something slipped in here.

### Configuration guide (env vars)

Add to `apps/dashboard/.env` (all optional; absent = today's cloud-only behaviour):

| Var | Default | Meaning |
|---|---|---|
| `OLLAMA_ENABLED` | *(off)* | `1` joins the local model to the chain |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `qwen3:4b` | which pulled model to serve |
| `OLLAMA_PLACEMENT` | `last` | `first` = local-first cost saver; `last` = offline fallback |

Cost-saver setup: `OLLAMA_ENABLED=1`, `OLLAMA_PLACEMENT=first`. Every call the
local model handles is free; when it's down or the prompt is oversized the chain
fails over to cloud automatically. Nothing else changes.

### Adding a new provider (the pattern)

1. If it's OpenAI-compatible: add one `_add_family(...)` (cloud) or a builder like
   `_ollama_provider()` (local) in `build_chain()`, gated on its own env key.
2. Register its model + capabilities in `pipeline/registry.py` (`ModelSpec`).
3. If it has an explicit thinking/reasoning mode, give it `reasoning_effort` or
   `token_headroom` so thinking can't starve output (see the Qwen3 lesson below).
4. Add it to `config.SERVER_HAS_KEY` if it can be the *only* provider.
5. Add a chain-membership test to `tests/test_providers.py`.

### Troubleshooting (integration-specific)

| Symptom | Cause | Fix |
|---|---|---|
| Ollama cooled with `returned no text (finish_reason=length)` | reasoning model spent the whole token budget thinking | already handled — reasoning models get `token_headroom=2048`; ensure the model is registered with `supports_reasoning=True` in `registry.py` |
| Chain has no `ollama` entry | `OLLAMA_ENABLED` not `1` | set it; call `providers.reset_chain()` (or restart) |
| Local calls but cloud never used as fallback | placement `first` and Ollama always succeeds | expected — that's the cost saver working; set `last` to prefer cloud quality |
| Hosted deploy tries localhost | `OLLAMA_ENABLED=1` set in prod | leave it unset in the cloud deployment; it's a local-dev/offline knob |

### Migration notes

- **Fully backward-compatible.** Default off; all 205 pre-existing tests plus 5
  new ones pass (210 total). The cloud chain construction is byte-for-byte
  unchanged when `OLLAMA_ENABLED` is unset.
- **Verified live**, not assumed: a real `market-analyst` call ran end-to-end
  through `call_with_failover` against the local qwen3:4b (local-only chain, no
  cloud key) and returned a correct answer.
- **No per-task routing was added.** Threading a task-class through
  `engine.py`'s 16 phase calls to route (e.g.) classification→local,
  reasoning→cloud is a real feature but a moderate migration touching the live
  pipeline — it belongs in its own approved change (cf. ADR-010's phased style),
  not smuggled into a provider-plumbing PR. The seam is ready: `registry.py`
  capability flags are exactly what such a router would consume.
- **The registry does not yet own the cloud providers' defaults.** Those remain
  hand-tuned in `build_chain()` (the proven live path). Retrofitting them onto
  `registry.py` is a clean, additive follow-up.

## 10. Uninstall (for completeness)

```bash
brew services stop ollama
brew uninstall ollama
rm -rf ~/.ollama                 # removes models + keys (frees ~2.5 GB+)
# optionally: brew uninstall mlx-c mlx   # if nothing else needs them
```
