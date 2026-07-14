"""Tests for the multi-provider failover chain."""

from __future__ import annotations

import asyncio

import pytest

from app.pipeline import providers

_ALL_KEY_VARS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)


def _clear_keys(monkeypatch):
    for var in _ALL_KEY_VARS:
        monkeypatch.delenv(var, raising=False)


def _provider(name: str) -> providers.Provider:
    return providers.Provider(
        name=name,
        base_url="http://test.invalid",
        api_key="test-key",
        model="test-model",
        min_gap=0.0,
        cooldown_429=1.0,
    )


def test_chain_order_all_keys(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    monkeypatch.setenv("GROQ_API_KEY", "q")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["gemini", "openrouter", "groq"]


def test_chain_skips_missing_keys(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "q")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["groq"]


def test_chain_empty_without_keys(monkeypatch):
    _clear_keys(monkeypatch)
    assert providers.build_chain() == []


def test_no_providers_raises(monkeypatch):
    monkeypatch.setattr(providers, "_chain", [])
    with pytest.raises(RuntimeError, match="No LLM provider configured"):
        asyncio.run(
            providers.call_with_failover("agent", "s", "u", max_tokens=100)
        )


def test_failover_to_next_provider(monkeypatch):
    p1, p2 = _provider("first"), _provider("second")

    async def fail(system, user, max_tokens):
        raise RuntimeError("boom")

    async def ok(system, user, max_tokens):
        return "answer from second"

    monkeypatch.setattr(p1, "call", fail)
    monkeypatch.setattr(p2, "call", ok)
    monkeypatch.setattr(providers, "_chain", [p1, p2])

    result = asyncio.run(
        providers.call_with_failover("agent", "s", "u", max_tokens=100)
    )
    assert result == "answer from second"
    assert not p1.available()  # failed provider is on cooldown
    assert p2.available()


def test_cooling_provider_is_skipped(monkeypatch):
    p1, p2 = _provider("first"), _provider("second")
    p1.set_cooldown(60.0)
    calls: list[str] = []

    async def ok(system, user, max_tokens):
        calls.append("second")
        return "answer"

    monkeypatch.setattr(p2, "call", ok)
    monkeypatch.setattr(providers, "_chain", [p1, p2])

    result = asyncio.run(
        providers.call_with_failover("agent", "s", "u", max_tokens=100)
    )
    assert result == "answer"
    assert calls == ["second"]


def test_byok_key_uses_anthropic_only(monkeypatch):
    """A user key runs on the premium Anthropic provider, not the free chain."""
    free = _provider("free-provider")
    called: list[str] = []

    async def free_ok(system, user, max_tokens):
        called.append("free")
        return "free answer"

    monkeypatch.setattr(free, "call", free_ok)
    monkeypatch.setattr(providers, "_chain", [free])

    captured: dict[str, providers.Provider] = {}
    real_byok = providers.byok_provider

    def spy_byok(api_key: str) -> providers.Provider:
        p = real_byok(api_key)

        async def byok_ok(system, user, max_tokens):
            called.append("byok")
            return "premium answer"

        object.__setattr__(p, "call", byok_ok)
        captured["p"] = p
        return p

    monkeypatch.setattr(providers, "byok_provider", spy_byok)
    result = asyncio.run(
        providers.call_with_failover(
            "agent", "s", "u", max_tokens=100, byok_key="sk-ant-user-key"
        )
    )
    assert result == "premium answer"
    assert called == ["byok"]  # free chain untouched
    assert captured["p"].name == "anthropic-byok"
    assert captured["p"].api_key == "sk-ant-user-key"


def test_byok_detects_provider_from_key_prefix(monkeypatch):
    """Any supported provider's key works — detected by prefix, routed to
    that provider's top model."""
    for var in (
        "STRATAGENT_BYOK_MODEL",
        "STRATAGENT_BYOK_MODEL_OPENAI",
        "STRATAGENT_BYOK_MODEL_OPENROUTER",
        "STRATAGENT_BYOK_MODEL_GROQ",
        "STRATAGENT_BYOK_MODEL_GEMINI",
    ):
        monkeypatch.delenv(var, raising=False)
    cases = [
        ("sk-ant-abc123", "anthropic-byok", providers.ANTHROPIC_BASE_URL),
        ("sk-or-v1-abc123", "openrouter-byok", providers.OPENROUTER_BASE_URL),
        ("sk-proj-abc123", "openai-byok", providers.OPENAI_BASE_URL),
        ("gsk_abc123", "groq-byok", providers.GROQ_BASE_URL),
        ("AIzaSyAbc123", "gemini-byok", providers.GEMINI_BASE_URL),
    ]
    for key, expected_name, expected_url in cases:
        p = providers.byok_provider(key)
        assert p.name == expected_name
        assert p.base_url == expected_url
        assert p.api_key == key


def test_byok_rejects_unknown_key_format():
    with pytest.raises(providers.UnsupportedKeyError, match="Unrecognized"):
        providers.detect_byok("not-a-real-key-shape")


def test_all_hard_down_fails_fast(monkeypatch):
    """When every provider is unusable (bad key), don't sleep out the passes."""
    import time as time_mod

    p1 = _provider("only")

    async def bad_key(system, user, max_tokens):
        raise RuntimeError("invalid key")

    monkeypatch.setattr(p1, "call", bad_key)
    monkeypatch.setattr(p1, "cooldown_429", 1.0)
    monkeypatch.setattr(providers, "_chain", [p1])
    monkeypatch.setattr(providers, "_TRANSIENT_COOLDOWN", 9999.0)

    start = time_mod.monotonic()
    with pytest.raises(RuntimeError, match="invalid key"):
        asyncio.run(
            providers.call_with_failover("agent", "s", "u", max_tokens=100)
        )
    assert time_mod.monotonic() - start < 5.0  # no 180s between-pass sleeps


def test_all_fail_raises_last_error(monkeypatch):
    p1 = _provider("only")

    async def fail(system, user, max_tokens):
        raise RuntimeError("provider down")

    monkeypatch.setattr(p1, "call", fail)
    monkeypatch.setattr(providers, "_chain", [p1])
    monkeypatch.setattr(providers, "_MAX_PASSES", 1)  # avoid cooldown sleeps

    with pytest.raises(RuntimeError, match="provider down"):
        asyncio.run(
            providers.call_with_failover("agent", "s", "u", max_tokens=100)
        )
