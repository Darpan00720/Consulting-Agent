"""Model capability registry — a declarative, env-configurable model catalog.

This is the single place that answers "what can model X do?" without scattering
model names through the codebase. The provider chain (``providers.py``) reads
the capability flags it actually acts on (vision, reasoning); the rest are
declarative metadata for routing decisions and documentation.

Design notes / honesty:
- The existing cloud providers in ``build_chain()`` were tuned by hand against
  real free-tier limits and are intentionally left as-is (see ADR-008 — the
  live path is the proven one). This registry is ADDITIVE: it is the source of
  truth for the Ollama provider and the documented pattern for adding models.
  Retrofitting the five cloud providers onto it is a clean follow-up, not done
  here to keep this change non-breaking.
- Capability flags encode what the code (or a future task-router) can branch on.
  A flag that nothing reads yet is declarative, not dead — it is the contract a
  router would consume; kept minimal so it doesn't become decorative metadata.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """One model's identity and capabilities, independent of who serves it."""

    provider: str  # family name: "ollama", "gemini", "anthropic", ...
    model: str  # the provider's own model id
    context_length: int
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_reasoning: bool = False  # has an explicit thinking/reasoning mode
    supports_json: bool = False  # reliable JSON / structured output
    supports_vision: bool = False  # reads pasted images
    supports_embeddings: bool = False  # is an embedding model (not chat)
    local: bool = False  # runs on-device (no API cost, no network)
    # A per-request INPUT cap imposed by the serving tier, when it is lower than
    # the model's nominal ``context_length``. GitHub Models' free tier, for
    # example, caps a request at 8k in / 4k out even though gpt-4.1-mini's
    # nominal window is ~1M — so long-context routing must use the *usable*
    # limit, not the nominal one. ``None`` = no tier cap below context_length.
    max_request_tokens: int | None = None


# Known models. Ollama entries mirror what Phase 3/4 of the Ollama setup
# verified on this machine (see docs/operations/Ollama-Local-Runtime.md). Cloud
# entries are a representative subset — the authoritative cloud defaults still
# live in build_chain(); these exist so a router/UI can query capabilities.
_REGISTRY: dict[str, ModelSpec] = {
    # ---- Local (Ollama) --------------------------------------------------
    "qwen3:4b": ModelSpec(
        provider="ollama",
        model="qwen3:4b",
        context_length=262144,
        supports_tools=True,
        supports_reasoning=True,  # thinking mode; append "/no_think" to disable
        supports_json=True,
        local=True,
    ),
    "qwen3:1.7b": ModelSpec(
        provider="ollama",
        model="qwen3:1.7b",
        context_length=32768,
        supports_tools=True,
        supports_reasoning=True,
        supports_json=True,
        local=True,
    ),
    "gemma3:4b": ModelSpec(
        provider="ollama",
        model="gemma3:4b",
        context_length=131072,
        supports_json=True,
        supports_vision=True,
        local=True,
    ),
    "nomic-embed-text": ModelSpec(
        provider="ollama",
        model="nomic-embed-text",
        context_length=8192,
        supports_streaming=False,
        supports_embeddings=True,
        local=True,
    ),
    # ---- Cloud (every production provider in build_chain, P0/ADR-012) -----
    # These mirror the default model each provider family serves in
    # build_chain(); a router consumes these flags instead of embedding
    # provider knowledge. build_chain() still owns the live wiring — this is the
    # declarative capability catalog it is described against.
    "gemini-flash-latest": ModelSpec(
        provider="gemini",
        model="gemini-flash-latest",
        context_length=1048576,
        supports_tools=True,
        supports_reasoning=True,
        supports_json=True,
        supports_vision=True,
    ),
    "gpt-oss-120b": ModelSpec(  # Cerebras default
        provider="cerebras",
        model="gpt-oss-120b",
        context_length=131072,
        supports_tools=True,
        supports_reasoning=True,  # gpt-oss is a reasoning model (see providers.py)
        supports_json=True,
    ),
    "nvidia/nemotron-3-super-120b-a12b:free": ModelSpec(  # OpenRouter default
        provider="openrouter",
        model="nvidia/nemotron-3-super-120b-a12b:free",
        context_length=131072,
        supports_tools=True,
        supports_reasoning=True,  # reasoning model; build_chain disables its CoT
        supports_json=True,
    ),
    "openai/gpt-4.1-mini": ModelSpec(  # GitHub Models default
        provider="github",
        model="openai/gpt-4.1-mini",
        context_length=1047576,  # nominal gpt-4.1-mini window
        # Free tier caps a request at 8k in / 4k out — the usable long-context
        # limit is far below the nominal window (see providers.py CAUTION note).
        max_request_tokens=8192,
        supports_tools=True,
        supports_json=True,
        supports_vision=True,  # gpt-4.1 family reads images
    ),
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": ModelSpec(  # Cloudflare default
        provider="cloudflare",
        model="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        context_length=131072,
        supports_tools=True,
        # Conservative: CF's endpoint doesn't guarantee reliable structured
        # JSON, and it is the last-resort fallback — so it is not marked
        # json-capable, keeping json-preferring routes off it.
        supports_json=False,
    ),
    "claude-opus-4-8": ModelSpec(  # BYOK premium (Anthropic)
        provider="anthropic",
        model="claude-opus-4-8",
        context_length=200000,
        supports_tools=True,
        supports_reasoning=True,
        supports_json=True,
        supports_vision=True,
    ),
}


def model_supports(model: str, capability: str) -> bool | None:
    """Whether ``model`` has a boolean capability flag (e.g. ``supports_vision``).

    Returns ``None`` when the model isn't registered, so a caller can decide
    whether to fall back to another source (a live provider's own flag) rather
    than assume ``False``. This is the capability lookup a router consumes to
    avoid hardcoding provider-family names.
    """
    spec = get_spec(model)
    if spec is None:
        return None
    return bool(getattr(spec, capability, False))


def effective_context(model: str) -> int | None:
    """Usable single-request input context: ``min(context_length, tier cap)``.

    Uses ``max_request_tokens`` when the serving tier caps a request below the
    model's nominal window (GitHub Models' 8k free tier). ``None`` when the
    model isn't registered.
    """
    spec = get_spec(model)
    if spec is None:
        return None
    if spec.max_request_tokens is not None:
        return min(spec.context_length, spec.max_request_tokens)
    return spec.context_length


def get_spec(model: str) -> ModelSpec | None:
    """Return the ModelSpec for a model id, or None if it isn't registered.

    Unregistered models are not an error — the provider chain still runs them;
    the registry just can't answer capability questions about them.
    """
    return _REGISTRY.get(model)


def register(spec: ModelSpec) -> None:
    """Add or override a model spec at runtime (tests, dynamic discovery)."""
    _REGISTRY[spec.model] = spec


def models_for(provider: str) -> list[ModelSpec]:
    """Every registered model served by one provider family."""
    return [s for s in _REGISTRY.values() if s.provider == provider]


def local_models() -> list[ModelSpec]:
    """Every on-device model — the zero-cost tier a router can prefer."""
    return [s for s in _REGISTRY.values() if s.local]
