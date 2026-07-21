"""Tests for the model capability registry (ADR-012 P0).

The registry is the single declarative source of "what can model X do?" that the
Provider Router consumes instead of hardcoding provider-family names. These
tests pin that every production provider is represented with the capabilities
routing depends on, and that the capability-lookup helpers behave.
"""

from __future__ import annotations

from app.pipeline import registry


def test_every_production_provider_is_registered():
    """Each family build_chain() constructs has a registered default model, so a
    capability-driven router can reason about all of them, not just Ollama."""
    providers = {spec.provider for spec in registry._REGISTRY.values()}
    for family in ("gemini", "cerebras", "openrouter", "github", "cloudflare"):
        assert family in providers, family


def test_vision_capabilities_are_recorded():
    assert registry.model_supports("gemini-flash-latest", "supports_vision") is True
    assert registry.model_supports("openai/gpt-4.1-mini", "supports_vision") is True
    assert registry.model_supports("gpt-oss-120b", "supports_vision") is False
    assert registry.model_supports("gemma3:4b", "supports_vision") is True  # local
    assert registry.model_supports("qwen3:4b", "supports_vision") is False  # local


def test_json_capabilities_are_recorded():
    assert registry.model_supports("gpt-oss-120b", "supports_json") is True
    assert registry.model_supports("gemini-flash-latest", "supports_json") is True
    # Cloudflare's fallback model is conservatively marked not json-reliable.
    assert (
        registry.model_supports(
            "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "supports_json"
        )
        is False
    )


def test_model_supports_returns_none_for_unregistered_model():
    assert registry.model_supports("some-env-override-model", "supports_vision") is None


def test_effective_context_uses_tier_cap_when_lower():
    """GitHub Models' free tier caps a request at 8k even though gpt-4.1-mini's
    nominal window is ~1M — long-context routing must see the usable 8k."""
    assert registry.effective_context("openai/gpt-4.1-mini") == 8192


def test_effective_context_is_the_nominal_window_without_a_cap():
    assert registry.effective_context("gemini-flash-latest") == 1048576


def test_effective_context_is_none_for_unregistered_model():
    assert registry.effective_context("some-env-override-model") is None


def test_reasoning_and_local_flags_are_recorded():
    assert registry.model_supports("gpt-oss-120b", "supports_reasoning") is True
    assert registry.get_spec("qwen3:4b").local is True
    assert registry.get_spec("gemini-flash-latest").local is False
