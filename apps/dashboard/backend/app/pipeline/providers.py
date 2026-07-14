"""Multi-provider LLM failover chain — never rely on a single free tier.

Order: Gemini 2.5 Flash → OpenRouter (free model) → Groq.

Only providers whose API key is present in the environment join the chain.
Each provider paces its own calls to its free-tier rate limit, and goes on
cooldown when it errors so subsequent calls skip straight to the next
provider until it recovers. A call only fails when every configured
provider is down at the same time.

Free-tier pacing per provider (July 2026):
- Gemini 2.5 Flash:   10 requests/min, 250k tokens/min  → 6.5 s gap
- OpenRouter (:free): 20 requests/min                   → 4.0 s gap
- Groq:               6 000 tokens/min                  → 65 s gap
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import openai

log = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"  # OpenAI-compat endpoint
OPENAI_BASE_URL = "https://api.openai.com/v1"

# Cooldown caps: a rate-limited provider is skipped, not waited on, so a long
# cooldown is cheap — the chain simply uses the next provider meanwhile.
_MAX_429_COOLDOWN = 900.0     # 15 min (e.g. daily-quota exhaustion)
_UNUSABLE_COOLDOWN = 3600.0   # bad key / missing model — don't hammer
_TRANSIENT_COOLDOWN = 30.0    # 5xx, timeout, empty response
_MAX_PASSES = 3               # full sweeps over the chain before giving up


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str
    min_gap: float                    # seconds between calls (free-tier pacing)
    cooldown_429: float               # fallback cooldown when 429 has no header
    extra_body: dict[str, Any] | None = None
    reasoning_effort: str | None = None  # for thinking models ("low"/"medium"/"high")
    token_headroom: int = 0           # extra max_tokens so thinking can't starve output
    _last_call: float = field(default=0.0, repr=False)
    _cooldown_until: float = field(default=0.0, repr=False)
    _lock: asyncio.Lock | None = field(default=None, repr=False)

    def available(self) -> bool:
        return time.monotonic() >= self._cooldown_until

    def cooldown_remaining(self) -> float:
        return max(0.0, self._cooldown_until - time.monotonic())

    def set_cooldown(self, seconds: float) -> None:
        self._cooldown_until = max(
            self._cooldown_until, time.monotonic() + seconds
        )

    async def throttle(self) -> None:
        """Enforce min_gap between consecutive calls to this provider."""
        if self._lock is None:  # created lazily, after the event loop exists
            self._lock = asyncio.Lock()
        async with self._lock:
            wait = self.min_gap - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    async def call(self, system: str, user: str, max_tokens: int) -> str:
        client = openai.AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=120.0,
            max_retries=0,  # failover handles retries, not the SDK
        )
        kwargs: dict[str, Any] = {}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens + self.token_headroom,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **kwargs,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError(
                f"{self.name} returned no text "
                f"(finish_reason={response.choices[0].finish_reason})"
            )
        return text


def build_chain() -> list[Provider]:
    """Assemble the failover chain from whichever API keys are configured."""
    chain: list[Provider] = []

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        chain.append(
            Provider(
                name="gemini",
                base_url=GEMINI_BASE_URL,
                api_key=gemini_key,
                model=os.environ.get("GEMINI_MODEL", "gemini-flash-latest"),
                min_gap=6.5,
                cooldown_429=60.0,
                # Gemini flash models think by default; thought tokens count
                # against max_tokens. Keep thinking modest and give the output
                # budget headroom so the visible answer is never starved.
                reasoning_effort="low",
                token_headroom=2048,
            )
        )

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        chain.append(
            Provider(
                name="openrouter",
                base_url=OPENROUTER_BASE_URL,
                api_key=openrouter_key,
                # Nemotron runs on NVIDIA's own infra — far less congested than
                # the shared upstreams serving most other :free models.
                model=os.environ.get(
                    "OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"
                ),
                min_gap=4.0,
                cooldown_429=75.0,
                # It's a reasoning model; disable thinking so chain-of-thought
                # doesn't leak into analyst outputs (no-op for other models).
                extra_body={"reasoning": {"enabled": False}},
            )
        )

    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        chain.append(
            Provider(
                name="groq",
                base_url=GROQ_BASE_URL,
                api_key=groq_key,
                model=os.environ.get(
                    "GROQ_MODEL",
                    os.environ.get("STRATAGENT_MODEL", "llama-3.1-8b-instant"),
                ),
                min_gap=65.0,
                cooldown_429=70.0,
            )
        )

    return chain


_chain: list[Provider] | None = None


def get_chain() -> list[Provider]:
    global _chain
    if _chain is None:
        _chain = build_chain()
    return _chain


def reset_chain() -> None:
    """Rebuild the chain on next use (tests / env changes)."""
    global _chain
    _chain = None


def chain_names() -> list[str]:
    return [p.name for p in get_chain()]


class UnsupportedKeyError(ValueError):
    """The BYOK key's format doesn't match any supported provider."""


# BYOK key detection: (prefix, provider name, base_url, model env override,
# default premium model). Order matters — the specific `sk-ant-`/`sk-or-`
# prefixes must match before the generic OpenAI `sk-`.
_BYOK_PROVIDERS: list[tuple[str, str, str, str, str]] = [
    ("sk-ant-", "anthropic-byok", ANTHROPIC_BASE_URL,
     "STRATAGENT_BYOK_MODEL", "claude-opus-4-8"),
    ("sk-or-", "openrouter-byok", OPENROUTER_BASE_URL,
     "STRATAGENT_BYOK_MODEL_OPENROUTER", "openrouter/auto"),
    ("gsk_", "groq-byok", GROQ_BASE_URL,
     "STRATAGENT_BYOK_MODEL_GROQ", "llama-3.3-70b-versatile"),
    ("AIza", "gemini-byok", GEMINI_BASE_URL,
     "STRATAGENT_BYOK_MODEL_GEMINI", "gemini-2.5-pro"),
    ("sk-", "openai-byok", OPENAI_BASE_URL,
     "STRATAGENT_BYOK_MODEL_OPENAI", "gpt-5.1"),
]

SUPPORTED_BYOK = "Anthropic (sk-ant-…), OpenAI (sk-…), OpenRouter (sk-or-…), Groq (gsk_…), or Google Gemini (AIza…)"


def detect_byok(api_key: str) -> tuple[str, str, str]:
    """Map a user key to (provider name, base_url, premium model) by prefix.

    Raises UnsupportedKeyError for a key that matches no known provider, so
    the router can reject it up front instead of failing mid-engagement.
    """
    for prefix, name, base_url, model_env, default_model in _BYOK_PROVIDERS:
        if api_key.startswith(prefix):
            return name, base_url, os.environ.get(model_env, default_model)
    raise UnsupportedKeyError(
        f"Unrecognized API key format. Supported keys: {SUPPORTED_BYOK}."
    )


def byok_provider(api_key: str) -> Provider:
    """Ephemeral provider for a user-supplied key (best-results path).

    Works with any supported provider's key — detected by prefix — and runs
    the whole engagement on that provider's top model. Built fresh per call
    and never cached: the key must not outlive the request that carried it.
    Paid-tier limits are generous, so pacing is minimal; the failover loop's
    cooldown passes still absorb transient 429/5xx errors.
    """
    name, base_url, model = detect_byok(api_key)
    return Provider(
        name=name,
        base_url=base_url,
        api_key=api_key,
        model=model,
        min_gap=1.5,
        cooldown_429=30.0,
        # Thinking models (Gemini 2.5 Pro etc.) spend tokens on reasoning
        # before output; headroom keeps max_tokens from starving the answer.
        token_headroom=4096 if name == "gemini-byok" else 0,
    )


def _parse_reset_seconds(exc: openai.RateLimitError) -> float | None:
    """Extract 'seconds until the limit resets' from a 429's headers."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", {}) or {}
    for key in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        raw = headers.get(key)
        if raw:
            try:
                cleaned = "".join(c for c in str(raw) if c.isdigit() or c == ".")
                return float(cleaned) + 3.0  # small buffer
            except (ValueError, TypeError):
                continue
    return None


async def call_with_failover(
    agent_name: str,
    system: str,
    user: str,
    *,
    max_tokens: int,
    byok_key: str | None = None,
) -> str:
    """Call the first available provider; fail over down the chain on errors.

    When ``byok_key`` is set the user brought their own Anthropic key: the
    call runs ONLY on that key's premium model — never silently degraded to
    the free chain, so premium results stay premium and key errors surface.
    """
    if byok_key:
        chain: list[Provider] = [byok_provider(byok_key)]
    else:
        chain = get_chain()
    if not chain:
        raise RuntimeError(
            "No LLM provider configured — set GEMINI_API_KEY, "
            "OPENROUTER_API_KEY, or GROQ_API_KEY in the server environment."
        )

    last_exc: Exception | None = None
    for pass_no in range(_MAX_PASSES):
        for provider in chain:
            if not provider.available():
                continue
            await provider.throttle()
            try:
                return await provider.call(system, user, max_tokens)
            except openai.RateLimitError as exc:
                wait = _parse_reset_seconds(exc) or provider.cooldown_429
                provider.set_cooldown(min(wait, _MAX_429_COOLDOWN))
                log.warning(
                    "%s rate-limited on %s — cooling %.0fs, failing over",
                    provider.name, agent_name, min(wait, _MAX_429_COOLDOWN),
                )
                last_exc = exc
            except (
                openai.AuthenticationError,
                openai.PermissionDeniedError,
                openai.NotFoundError,
            ) as exc:
                provider.set_cooldown(_UNUSABLE_COOLDOWN)
                log.warning(
                    "%s unusable on %s (%s) — cooling 1h, failing over",
                    provider.name, agent_name, type(exc).__name__,
                )
                last_exc = exc
            except Exception as exc:  # noqa: BLE001 — 5xx, timeout, empty text
                provider.set_cooldown(_TRANSIENT_COOLDOWN)
                log.warning(
                    "%s failed on %s (%s: %s) — cooling %.0fs, failing over",
                    provider.name, agent_name, type(exc).__name__,
                    str(exc)[:200], _TRANSIENT_COOLDOWN,
                )
                last_exc = exc

        # Every provider is hard-down (bad key / missing model) — waiting
        # won't fix it, so fail fast instead of sleeping out the passes.
        if all(p.cooldown_remaining() > _MAX_429_COOLDOWN for p in chain):
            break

        # Every provider is cooling down — sleep until the soonest recovers.
        if pass_no < _MAX_PASSES - 1:
            wait = min(p.cooldown_remaining() for p in chain)
            await asyncio.sleep(min(wait, 180.0) + 1.0)

    assert last_exc is not None
    raise last_exc
