"""Tests for the multi-provider failover chain."""

from __future__ import annotations

import asyncio

import openai
import pytest

from app.pipeline import providers

_ALL_KEY_VARS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_MODELS_TOKEN",
    "GITHUB_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "GROQ_API_KEY",
)


_OLLAMA_VARS = (
    "OLLAMA_ENABLED",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_PLACEMENT",
    "OLLAMA_API_KEY",
)


def _clear_keys(monkeypatch):
    for var in _ALL_KEY_VARS + _OLLAMA_VARS:
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
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    monkeypatch.setenv("GITHUB_MODELS_TOKEN", "gh")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf")
    chain = providers.build_chain()
    assert [p.name for p in chain] == [
        "gemini",
        "cerebras",
        "openrouter",
        "github",
        "cloudflare",
    ]


def test_groq_is_not_in_the_free_chain(monkeypatch):
    """Groq's 6k TPM can't fit a reconcile prompt (413 'request too large'), so
    it was removed from the free chain — a key alone must not resurrect it."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "q")
    assert providers.build_chain() == []


def test_cloudflare_needs_account_id_and_token(monkeypatch):
    """Its account id is part of the URL, so a token alone is unusable."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf")
    assert providers.build_chain() == []  # no account id → skipped

    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["cloudflare"]
    assert "acct123" in chain[0].base_url


def test_reasoning_models_have_a_thinking_guard(monkeypatch):
    """Reasoning models bill their thinking against max_tokens, so without a
    guard a tight budget is spent thinking and the reply is EMPTY — which
    call() reports as "returned no text" and cools a healthy provider.

    Every chain model that thinks (gemini flash, cerebras gpt-oss, openrouter
    nemotron) must either cap the thinking, disable it, or add headroom.
    """
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    for provider in providers.build_chain():
        guarded = (
            provider.reasoning_effort is not None
            or provider.token_headroom > 0
            or (provider.extra_body or {}).get("reasoning", {}).get("enabled") is False
        )
        assert guarded, (
            f"{provider.name} runs a thinking model with no guard — its output "
            f"can be starved by its own reasoning tokens"
        )


def test_pacing_never_exceeds_documented_rpm(monkeypatch):
    """min_gap must not issue faster than the provider's real requests/min, or
    we manufacture our own 429s.

    Gemini's true free-tier limit is 5 RPM per project (measured on a live AI
    Studio dashboard — the docs' "10" is wrong). A 6.5s gap sends ~9.2 req/min
    into that ceiling, which is exactly the self-inflicted rate limiting this
    guards against.
    """
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    limits_rpm = {"gemini": 5, "cerebras": 5, "openrouter": 20}
    for provider in providers.build_chain():
        allowed = limits_rpm[provider.family]
        issued_rpm = 60.0 / provider.min_gap
        assert issued_rpm <= allowed, (
            f"{provider.name} paces {issued_rpm:.1f} req/min into a "
            f"{allowed} req/min limit — it will 429 itself"
        )


def test_multiple_keys_per_provider_comma_separated(monkeypatch):
    """Free-tier quota is per account/project, so several keys = more capacity.
    Each key becomes its own chain entry with its own pacing and cooldown."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k1,k2,k3")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["gemini", "gemini#2", "gemini#3"]
    assert [p.api_key for p in chain] == ["k1", "k2", "k3"]
    assert {p.family for p in chain} == {"gemini"}


def test_multiple_keys_per_provider_numbered(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "c1")
    monkeypatch.setenv("CEREBRAS_API_KEY_2", "c2")
    monkeypatch.setenv("CEREBRAS_API_KEY_3", "c3")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["cerebras", "cerebras#2", "cerebras#3"]
    assert [p.api_key for p in chain] == ["c1", "c2", "c3"]


def test_duplicate_keys_are_collapsed(monkeypatch):
    """The same key pasted twice is one quota bucket, not two — listing it
    twice must not fool the chain into thinking it has more capacity."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "same,same")
    monkeypatch.setenv("GEMINI_API_KEY_2", "same")
    assert [p.name for p in providers.build_chain()] == ["gemini"]


def test_busy_key_hands_off_to_idle_sibling(monkeypatch):
    """The point of extra keys: when key #1 owes a pacing wait, the call goes
    to a sibling that is free NOW rather than sleeping out key #1's min_gap."""
    p1, p2 = _provider("gemini"), _provider("gemini#2")
    object.__setattr__(p1, "min_gap", 30.0)
    p1._last_call = __import__("time").monotonic()  # just used → owes ~30s
    object.__setattr__(p2, "min_gap", 30.0)  # never used → ready now

    assert p1.wait_time() > 25.0
    assert p2.wait_time() == 0.0
    # _ordered puts the ready sibling first, so no 30s sleep is incurred.
    assert [p.name for p in providers._ordered([p1, p2])] == ["gemini#2", "gemini"]


def test_family_order_is_never_reordered_across_providers(monkeypatch):
    """Ordering across families is a quality ranking — a busy Gemini must not
    demote it below Cloudflare just because Cloudflare is idle."""
    gem, cf = _provider("gemini"), _provider("cloudflare")
    object.__setattr__(gem, "min_gap", 30.0)
    gem._last_call = __import__("time").monotonic()  # busy
    assert [p.name for p in providers._ordered([gem, cf])] == ["gemini", "cloudflare"]


def test_blank_model_env_falls_back_to_default(monkeypatch):
    """docker-compose's `MODEL: ${MODEL:-}` exports an EMPTY string, and
    os.environ.get(name, default) returns "" for it — which would send a blank
    model id to the provider. Empty must mean 'unset'."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    monkeypatch.setenv("CEREBRAS_MODEL", "")  # exactly what compose exports
    chain = providers.build_chain()
    assert chain[0].model == "gpt-oss-120b"

    monkeypatch.setenv("CEREBRAS_MODEL", "zai-glm-4.7")  # a real override wins
    assert providers.build_chain()[0].model == "zai-glm-4.7"


def test_chain_skips_missing_keys(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("CEREBRAS_API_KEY", "c")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["cerebras"]


def test_chain_empty_without_keys(monkeypatch):
    _clear_keys(monkeypatch)
    assert providers.build_chain() == []


def test_no_providers_raises(monkeypatch):
    monkeypatch.setattr(providers, "_chain", [])
    with pytest.raises(RuntimeError, match="No LLM provider configured"):
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))


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
        "STRATAGENT_BYOK_MODEL_CEREBRAS",
        "STRATAGENT_BYOK_MODEL_GEMINI",
    ):
        monkeypatch.delenv(var, raising=False)
    cases = [
        ("sk-ant-abc123", "anthropic-byok", providers.ANTHROPIC_BASE_URL),
        ("sk-or-v1-abc123", "openrouter-byok", providers.OPENROUTER_BASE_URL),
        ("sk-proj-abc123", "openai-byok", providers.OPENAI_BASE_URL),
        # Groq stays BYOK-supported after leaving the free chain: a paid key
        # has none of the 6k-TPM limits that made the free tier unusable.
        ("gsk_abc123", "groq-byok", providers.GROQ_BASE_URL),
        ("csk-abc123", "cerebras-byok", providers.CEREBRAS_BASE_URL),
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
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))
    assert time_mod.monotonic() - start < 5.0  # no 180s between-pass sleeps


def test_all_fail_raises_last_error(monkeypatch):
    p1 = _provider("only")

    async def fail(system, user, max_tokens):
        raise RuntimeError("provider down")

    monkeypatch.setattr(p1, "call", fail)
    monkeypatch.setattr(providers, "_chain", [p1])
    monkeypatch.setattr(providers, "_MAX_PASSES", 1)  # avoid cooldown sleeps

    with pytest.raises(RuntimeError, match="provider down"):
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))


async def _no_sleep(_seconds: float) -> None:
    """Stand-in for asyncio.sleep so cooldown waits don't slow the tests."""
    return None


def _rate_limit_error(retry_after: str | None = None) -> openai.RateLimitError:
    import httpx

    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(
        429, headers=headers, request=httpx.Request("POST", "http://test.invalid")
    )
    return openai.RateLimitError("rate limited", response=response, body=None)


def test_all_rate_limited_raises_resumable(monkeypatch):
    """When every provider is 429 at once, surface a distinct resumable error
    carrying the retry-after — so the engine can pause and resume, not fail."""
    p1 = _provider("only")

    async def limited(system, user, max_tokens):
        raise _rate_limit_error("120")

    monkeypatch.setattr(p1, "call", limited)
    monkeypatch.setattr(providers, "_chain", [p1])
    monkeypatch.setattr(providers, "_MAX_PASSES", 1)

    with pytest.raises(providers.AllProvidersRateLimitedError) as caught:
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))
    # retry-after (120) + a small buffer, above the resume threshold
    assert caught.value.retry_after >= 120.0


def test_recurring_short_rate_limit_pauses_rather_than_failing(monkeypatch):
    """Regression: short retry-afters that recur on every pass must still end
    in a resumable pause, not a raw 429 that fails the whole engagement.

    Caught in live verification — the loop exhausted its passes and re-raised
    the bare RateLimitError, so a rate-limited run died with its finished
    analyst work discarded.
    """
    p1 = _provider("only")

    async def limited(system, user, max_tokens):
        raise _rate_limit_error("5")  # short wait, under the resume threshold

    monkeypatch.setattr(p1, "call", limited)
    monkeypatch.setattr(providers, "_chain", [p1])
    monkeypatch.setattr(providers, "_MAX_PASSES", 2)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)  # don't burn the pass waits

    with pytest.raises(providers.AllProvidersRateLimitedError):
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))


def _oversized_error() -> Exception:
    """Groq's real shape for 'this prompt exceeds my whole TPM budget'."""
    import httpx

    response = httpx.Response(413, request=httpx.Request("POST", "http://test.invalid"))
    return openai.APIStatusError(
        "Error code: 413 - Request too large for model `llama-3.1-8b-instant` on "
        "tokens per minute (TPM): Limit 6000, Requested 8000."
        " code: rate_limit_exceeded",
        response=response,
        body=None,
    )


def test_last_provider_413_does_not_mask_throttled_chain(monkeypatch):
    """Regression: a trailing non-429 failure must not veto the pause.

    Caught live — gemini and openrouter both returned 429 (they refill), but
    groq answered 413 "request too large". Because groq is last in the chain
    its error became last_exc, the isinstance(RateLimitError) check missed it,
    and the raw error failed the engagement instead of pausing it.
    """
    p1, p2, p3 = _provider("gemini"), _provider("openrouter"), _provider("groq")

    async def limited(system, user, max_tokens):
        raise _rate_limit_error("60")

    async def oversized(system, user, max_tokens):
        raise _oversized_error()

    monkeypatch.setattr(p1, "call", limited)
    monkeypatch.setattr(p2, "call", limited)
    monkeypatch.setattr(p3, "call", oversized)  # last in the chain
    monkeypatch.setattr(providers, "_chain", [p1, p2, p3])
    monkeypatch.setattr(providers, "_MAX_PASSES", 1)

    with pytest.raises(providers.AllProvidersRateLimitedError):
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))

    # The oversized provider is parked, not merely cooled: waiting cannot make
    # the prompt fit, so it must not be retried for this engagement.
    assert p3.cooldown_remaining() > providers._MAX_429_COOLDOWN


def test_oversized_only_chain_is_not_a_resumable_pause(monkeypatch):
    """If the ONLY failure is 'prompt too large', pausing is pointless — time
    doesn't shrink the request. That must still surface as a real error."""
    p1 = _provider("groq")

    async def oversized(system, user, max_tokens):
        raise _oversized_error()

    monkeypatch.setattr(p1, "call", oversized)
    monkeypatch.setattr(providers, "_chain", [p1])
    monkeypatch.setattr(providers, "_MAX_PASSES", 1)

    with pytest.raises(openai.APIStatusError):
        asyncio.run(providers.call_with_failover("agent", "s", "u", max_tokens=100))


def test_rate_limit_falls_over_before_pausing(monkeypatch):
    """A single rate-limited provider is not a wall — the chain fails over to a
    healthy provider and never raises the resumable error."""
    p1, p2 = _provider("first"), _provider("second")

    async def limited(system, user, max_tokens):
        raise _rate_limit_error("300")

    async def ok(system, user, max_tokens):
        return "healthy answer"

    monkeypatch.setattr(p1, "call", limited)
    monkeypatch.setattr(p2, "call", ok)
    monkeypatch.setattr(providers, "_chain", [p1, p2])

    result = asyncio.run(
        providers.call_with_failover("agent", "s", "u", max_tokens=100)
    )
    assert result == "healthy answer"


def test_vision_provider_attaches_images(monkeypatch):
    """A vision provider forwards pasted images as image_url parts; a text-only
    provider drops them (so failover to a non-vision fallback still works)."""

    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)

        class _Msg:
            content = "ok"

        class _Choice:
            message = _Msg()
            finish_reason = "stop"

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    class _FakeClient:
        def __init__(self, **_):
            self.chat = self

        @property
        def completions(self):
            return self

        create = staticmethod(fake_create)

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeClient)

    img = "data:image/png;base64,AAAA"
    vision = _provider("v")
    object.__setattr__(vision, "supports_vision", True)
    asyncio.run(vision.call("sys", "user text", 100, [img]))
    content = captured["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "user text"}
    assert content[1]["image_url"]["url"] == img

    captured.clear()
    text_only = _provider("t")  # supports_vision defaults False
    asyncio.run(text_only.call("sys", "user text", 100, [img]))
    assert captured["messages"][1]["content"] == "user text"  # image dropped


# ---- Ollama local provider (additive; opt-in) ---------------------------


def test_ollama_absent_by_default(monkeypatch):
    """A cloud-only setup must not gain a local provider unless opted in."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    names = [p.name for p in providers.build_chain()]
    assert "ollama" not in names


def test_ollama_appends_as_fallback_by_default_placement(monkeypatch):
    """OLLAMA_ENABLED with no placement puts the local model LAST (fallback)."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    names = [p.name for p in providers.build_chain()]
    assert names[0] == "gemini" and names[-1] == "ollama"


def test_ollama_first_placement_is_local_first(monkeypatch):
    """OLLAMA_PLACEMENT=first puts the local model at the head (cost saver)."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setenv("OLLAMA_PLACEMENT", "first")
    names = [p.name for p in providers.build_chain()]
    assert names[0] == "ollama"


def test_ollama_only_chain_when_no_cloud_keys(monkeypatch):
    """Local-only: Ollama enabled with no cloud keys still yields a usable chain."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    chain = providers.build_chain()
    assert [p.name for p in chain] == ["ollama"]


def test_ollama_provider_config(monkeypatch):
    """Local provider: no pacing, honours env overrides, reasoning headroom."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("OLLAMA_ENABLED", "1")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    (ollama,) = providers.build_chain()
    assert ollama.min_gap == 0.0  # local — no free-tier rate limit
    assert ollama.base_url == "http://localhost:11434/v1"
    # qwen3 is a reasoning model in the registry → gets thinking headroom so a
    # tight budget isn't consumed by (invisible) thinking (finish_reason=length).
    assert ollama.token_headroom == 2048
