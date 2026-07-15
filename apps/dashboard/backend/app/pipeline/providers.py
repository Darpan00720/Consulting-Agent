"""Multi-provider LLM failover chain — never rely on a single free tier.

Order: Gemini → Cerebras → OpenRouter → GitHub Models → Cloudflare Workers AI.

Only providers whose API key is present in the environment join the chain, so
adding a key is the whole install step and a missing key is simply skipped.
Each provider paces its own calls to its free-tier rate limit, and goes on
cooldown when it errors so subsequent calls skip straight to the next provider
until it recovers. A call only fails when every configured provider is down at
the same time.

Free-tier limits per provider (July 2026):
- Gemini (flash):    5 req/min PER PROJECT, 250k tokens/min → 12.5 s gap. Vision.
- Cerebras:          5 req/min, 30k TPM, 1M tokens/day      → 12.5 s gap
- OpenRouter(:free):20 req/min                              → 4.0 s gap
- GitHub Models:    15 req/min, 150 req/day, **8k in / 4k out per request**
- Cloudflare WAI:   10,000 neurons/day (a few engagements)  → 3.0 s gap

Gemini's 5 RPM is measured from a real AI Studio rate-limit dashboard. Docs and
third-party guides say 10 — they are WRONG for this account, and pacing at 10
silently manufactures 429s. Requests, not tokens, are the binding limit: peak
observed TPM was 23.37K against the 250K ceiling (<10%). When tuning any
provider here, trust the vendor's live usage dashboard over its documentation.

WHY GROQ WAS REMOVED (2026-07-14): its free tier is 6,000 tokens/min, and a
single reconcile prompt is ~8k tokens — so it answered 413 "Request too large"
on every large-prompt phase, no matter how long we waited. It could never serve
the phases that matter, while its 65 s pacing stretched runs past 14 minutes.
A *paid* Groq key is fine, so `gsk_` stays supported for BYOK.

CAUTION — GitHub Models has the same shape of limit: 8k tokens in / 4k out per
request on the free tier. Reconcile and report prompts sit right at that edge,
so expect it to be parked by `_is_oversized` on those phases and to serve the
smaller early ones. It is placed late in the chain for that reason.
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


def _env(name: str, default: str) -> str:
    """``os.environ.get`` that treats an empty value as absent.

    docker-compose's ``VAR: ${VAR:-}`` sets the variable to an EMPTY STRING
    when it isn't defined on the host — and ``os.environ.get(name, default)``
    then returns "" rather than the default, silently blanking a model id.
    """
    return os.environ.get(name) or default


_MAX_KEYS_PER_PROVIDER = 10


def _keys(*names: str) -> list[str]:
    """Collect every key configured for one provider, in order, deduped.

    Free-tier quota is per account/project, so several independent keys give
    genuinely multiplied capacity — the chain treats each as its own provider
    with its own pacing and cooldown. Two spellings are accepted:

        GEMINI_API_KEY=key1,key2,key3        # comma-separated
        GEMINI_API_KEY=key1                  # or numbered
        GEMINI_API_KEY_2=key2

    CRITICAL: only list keys that bill to DIFFERENT quota buckets. Each entry
    is paced as though it owns its limit (see ``_ordered``), so keys sharing a
    bucket don't merely fail to help — they make things WORSE: the chain
    round-robins them and issues ~N× the request rate into one limit, causing
    429 churn, cooldowns, and pauses that a single key would never hit.

    Check each vendor's quota UNIT before pooling:
    - Gemini    — per Google Cloud PROJECT ("rate limits are applied per
                  project, not per API key"). Separate projects → real N×.
    - Cerebras  — per ORGANIZATION ("rate limits apply at the organization
                  level, not the user level"). Extra keys on one account share
                  one pool: list only ONE.
    """
    found: list[str] = []
    for name in names:
        variants = [name] + [
            f"{name}_{i}" for i in range(2, _MAX_KEYS_PER_PROVIDER + 1)
        ]
        for var in variants:
            raw = os.environ.get(var) or ""
            for key in raw.split(","):
                key = key.strip()
                if key and key not in found:
                    found.append(key)
    return found[:_MAX_KEYS_PER_PROVIDER]


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"  # BYOK only — see module docstring
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/"  # OpenAI-compat endpoint
OPENAI_BASE_URL = "https://api.openai.com/v1"
CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"
GITHUB_MODELS_BASE_URL = "https://models.github.ai/inference"
# Cloudflare's endpoint embeds the account id, so it is built per-account.
CLOUDFLARE_BASE_URL_TEMPLATE = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
)

# Cooldown caps: a rate-limited provider is skipped, not waited on, so a long
# cooldown is cheap — the chain simply uses the next provider meanwhile.
_MAX_429_COOLDOWN = 900.0  # 15 min (e.g. daily-quota exhaustion)
_UNUSABLE_COOLDOWN = 3600.0  # bad key / missing model — don't hammer
_TRANSIENT_COOLDOWN = 30.0  # 5xx, timeout, empty response
_MAX_PASSES = 3  # full sweeps over the chain before giving up
# When every provider is rate-limited and the soonest recovery is longer than
# this, stop sleeping in-call and hand control back to the caller so it can
# checkpoint progress, pause, and auto-resume with a visible countdown instead
# of a silent multi-minute stall.
_RESUME_THRESHOLD = 45.0


class AllProvidersRateLimitedError(RuntimeError):
    """Every configured provider is on rate-limit cooldown at once.

    Distinct from a hard failure (bad key, missing model, provider outage):
    waiting *will* fix it. Carries ``retry_after`` — the seconds until the
    soonest provider refills — so the engine can pause and resume rather than
    failing the whole engagement and losing completed work.
    """

    def __init__(self, retry_after: float) -> None:
        self.retry_after = max(0.0, float(retry_after))
        super().__init__(
            f"All AI providers are rate-limited; soonest refill in "
            f"{self.retry_after:.0f}s"
        )


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str
    min_gap: float  # seconds between calls (free-tier pacing)
    cooldown_429: float  # fallback cooldown when 429 has no header
    extra_body: dict[str, Any] | None = None
    reasoning_effort: str | None = None  # for thinking models ("low"/"medium"/"high")
    token_headroom: int = 0  # extra max_tokens so thinking can't starve output
    supports_vision: bool = False  # can read pasted images/charts (multimodal)
    _last_call: float = field(default=0.0, repr=False)
    _cooldown_until: float = field(default=0.0, repr=False)
    _lock: asyncio.Lock | None = field(default=None, repr=False)

    @property
    def family(self) -> str:
        """Provider identity ignoring the key index: ``gemini#2`` → ``gemini``.

        Keys in the same family are interchangeable, so the chain may serve a
        call from whichever one is ready rather than queueing on the first.
        """
        return self.name.split("#", 1)[0]

    def available(self) -> bool:
        return time.monotonic() >= self._cooldown_until

    def cooldown_remaining(self) -> float:
        return max(0.0, self._cooldown_until - time.monotonic())

    def wait_time(self) -> float:
        """Seconds until this provider could actually serve a call.

        Covers BOTH cooldown and min_gap pacing. Cooldown alone isn't enough:
        a provider that is 'available' may still owe a pacing sleep, and
        picking it would waste that wait when a sibling key is free right now.
        """
        gap_left = self.min_gap - (time.monotonic() - self._last_call)
        return max(0.0, self.cooldown_remaining(), gap_left)

    def set_cooldown(self, seconds: float) -> None:
        self._cooldown_until = max(self._cooldown_until, time.monotonic() + seconds)

    async def throttle(self) -> None:
        """Enforce min_gap between consecutive calls to this provider."""
        if self._lock is None:  # created lazily, after the event loop exists
            self._lock = asyncio.Lock()
        async with self._lock:
            wait = self.min_gap - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    async def call(
        self,
        system: str,
        user: str,
        max_tokens: int,
        images: list[str] | None = None,
    ) -> str:
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
        # Multimodal: attach pasted images (charts, graphs, screenshots) as
        # image_url parts — but only for a vision-capable model. On a text-only
        # provider we silently drop them rather than error, so failover still
        # works when the chain lands on a non-vision fallback.
        if images and self.supports_vision:
            user_content: Any = [{"type": "text", "text": user}]
            user_content += [
                {"type": "image_url", "image_url": {"url": img}} for img in images
            ]
        else:
            user_content = user
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens + self.token_headroom,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
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


def _add_family(chain: list[Provider], family: str, keys: list[str], **kw: Any) -> None:
    """Append one Provider per key: `gemini`, `gemini#2`, `gemini#3`, …

    Each gets independent pacing and cooldown state, so one key hitting its
    quota simply moves traffic to the next instead of stalling the chain.
    """
    for i, key in enumerate(keys):
        chain.append(
            Provider(
                name=family if i == 0 else f"{family}#{i + 1}",
                api_key=key,
                **kw,
            )
        )


def build_chain() -> list[Provider]:
    """Assemble the failover chain from whichever API keys are configured.

    Every provider accepts MULTIPLE keys (see ``_keys``) — each becomes its own
    entry, so N independent accounts/projects give ~N× the free-tier capacity.
    """
    chain: list[Provider] = []

    _add_family(
        chain,
        "gemini",
        _keys("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        base_url=GEMINI_BASE_URL,
        model=_env("GEMINI_MODEL", "gemini-flash-latest"),
        # 5 req/min per PROJECT — confirmed against a real AI Studio rate-limit
        # dashboard (Gemini 3.5 Flash: RPM 2/5, TPM 23.37K/250K), not from docs
        # or blogs, which report 10. At the old 6.5 s gap we issued ~9.2 req/min
        # into a 5/min ceiling and manufactured our own 429s.
        min_gap=12.5,
        cooldown_429=60.0,
        # Gemini flash models think by default; thought tokens count against
        # max_tokens. Keep thinking modest and give the output budget headroom
        # so the visible answer is never starved.
        reasoning_effort="low",
        token_headroom=2048,
        supports_vision=True,  # Gemini reads pasted charts/graphs
    )

    # Cerebras — the provider that replaces Groq. Same "fast inference" niche,
    # but 30k tokens/min instead of 6k, so the ~8k reconcile prompt that Groq
    # could never fit is comfortable here. 5 req/min is the binding limit,
    # which is exactly why extra Cerebras keys pay off.
    _add_family(
        chain,
        "cerebras",
        _keys("CEREBRAS_API_KEY"),
        base_url=CEREBRAS_BASE_URL,
        model=_env("CEREBRAS_MODEL", "gpt-oss-120b"),
        min_gap=12.5,  # 5 req/min free trial
        cooldown_429=65.0,
        # gpt-oss is a REASONING model: its thinking is billed against
        # max_tokens, so a tight budget is spent thinking and the reply comes
        # back empty (finish_reason=length) — which our call() reports as
        # "returned no text" and cools the provider as if it were broken.
        # Measured: "low" cut a simple answer from 58 completion tokens to 20.
        # Same guard Gemini flash and OpenRouter's nemotron already carry.
        reasoning_effort="low",
        token_headroom=2048,
    )

    _add_family(
        chain,
        "openrouter",
        _keys("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
        # Nemotron runs on NVIDIA's own infra — far less congested than the
        # shared upstreams serving most other :free models.
        model=_env("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"),
        min_gap=4.0,
        cooldown_429=75.0,
        # It's a reasoning model; disable thinking so chain-of-thought doesn't
        # leak into analyst outputs (no-op for other models).
        extra_body={"reasoning": {"enabled": False}},
    )

    # GitHub Models — a GitHub PAT with the `models: read` scope. Free tier caps
    # a request at 8k tokens in / 4k out, so big phases get parked as oversized;
    # placed late so it serves the smaller phases without blocking the chain.
    _add_family(
        chain,
        "github",
        _keys("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN"),
        base_url=GITHUB_MODELS_BASE_URL,
        # Model ids are `publisher/model`. Low-tier models get the better
        # allowance (15 req/min, 150/day) than high tier (10/50).
        model=_env("GITHUB_MODELS_MODEL", "openai/gpt-4.1-mini"),
        min_gap=4.5,
        cooldown_429=70.0,
        supports_vision=True,  # gpt-4.1 family reads images
    )

    # Cloudflare Workers AI — the account id is baked into the URL, so ids and
    # tokens are paired positionally; an unmatched one is skipped rather than
    # silently combined with the wrong account's token.
    cf_accounts = _keys("CLOUDFLARE_ACCOUNT_ID")
    cf_tokens = _keys("CLOUDFLARE_API_TOKEN")
    for i, (account, token) in enumerate(zip(cf_accounts, cf_tokens, strict=False)):
        chain.append(
            Provider(
                name="cloudflare" if i == 0 else f"cloudflare#{i + 1}",
                base_url=CLOUDFLARE_BASE_URL_TEMPLATE.format(account_id=account),
                api_key=token,
                model=_env(
                    "CLOUDFLARE_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
                ),
                min_gap=3.0,
                # Free tier is 10k neurons/day — a handful of engagements. When
                # that runs out it stays out until 00:00 UTC, so cool it long
                # rather than retrying into a wall.
                cooldown_429=900.0,
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
#
# Groq stays here even though it was dropped from the free chain: a PAID Groq
# key has far higher limits than the 6k-TPM free tier that made it unusable for
# us, and silently rejecting a user's valid key would break the promise that any
# supported provider's key works.
_BYOK_PROVIDERS: list[tuple[str, str, str, str, str]] = [
    (
        "sk-ant-",
        "anthropic-byok",
        ANTHROPIC_BASE_URL,
        "STRATAGENT_BYOK_MODEL",
        "claude-opus-4-8",
    ),
    (
        "sk-or-",
        "openrouter-byok",
        OPENROUTER_BASE_URL,
        "STRATAGENT_BYOK_MODEL_OPENROUTER",
        "openrouter/auto",
    ),
    (
        "gsk_",
        "groq-byok",
        GROQ_BASE_URL,
        "STRATAGENT_BYOK_MODEL_GROQ",
        "llama-3.3-70b-versatile",
    ),
    (
        "csk-",
        "cerebras-byok",
        CEREBRAS_BASE_URL,
        "STRATAGENT_BYOK_MODEL_CEREBRAS",
        "gpt-oss-120b",
    ),
    (
        "AIza",
        "gemini-byok",
        GEMINI_BASE_URL,
        "STRATAGENT_BYOK_MODEL_GEMINI",
        "gemini-2.5-pro",
    ),
    ("sk-", "openai-byok", OPENAI_BASE_URL, "STRATAGENT_BYOK_MODEL_OPENAI", "gpt-5.1"),
]

SUPPORTED_BYOK = (
    "Anthropic (sk-ant-…), OpenAI (sk-…), OpenRouter (sk-or-…), "
    "Cerebras (csk-…), Groq (gsk_…), or Google Gemini (AIza…)"
)

# Which BYOK providers can read pasted images. Anthropic (Claude), OpenAI
# (GPT), and Gemini are natively multimodal; Groq's llama models and
# OpenRouter's default routing are text-first, so images are dropped there.
_VISION_BYOK = frozenset({"anthropic-byok", "openai-byok", "gemini-byok"})


def detect_byok(api_key: str) -> tuple[str, str, str]:
    """Map a user key to (provider name, base_url, premium model) by prefix.

    Raises UnsupportedKeyError for a key that matches no known provider, so
    the router can reject it up front instead of failing mid-engagement.
    """
    for prefix, name, base_url, model_env, default_model in _BYOK_PROVIDERS:
        if api_key.startswith(prefix):
            return name, base_url, _env(model_env, default_model)
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
        supports_vision=name in _VISION_BYOK,
    )


def _is_rate_limit(exc: Exception) -> bool:
    """True when a failure means 'quota exhausted — capacity returns later'.

    Not every rate limit arrives as openai.RateLimitError. Groq signals a
    per-minute token overrun as a 413 carrying code ``rate_limit_exceeded``,
    so an isinstance check alone lets a rate limit masquerade as a hard
    failure — and the engagement dies instead of pausing.
    """
    if isinstance(exc, openai.RateLimitError):
        return True
    if getattr(exc, "status_code", None) == 429:
        return True
    text = str(exc).lower()
    return "rate_limit" in text or "rate limit" in text or "tokens per minute" in text


def _is_oversized(exc: Exception) -> bool:
    """True when the prompt exceeds what this provider can EVER serve.

    Groq's 413 "Request too large ... TPM Limit 6000, Requested 8000" means the
    single request outgrew the whole per-minute budget. Waiting cannot shrink
    it, so unlike a normal rate limit this provider must be parked rather than
    retried — and it must not be mistaken for the chain being merely throttled.
    """
    return (
        getattr(exc, "status_code", None) == 413
        or "request too large" in str(exc).lower()
    )


def _parse_reset_seconds(exc: openai.RateLimitError) -> float | None:
    """Extract 'seconds until the limit resets' from a 429's headers."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", {}) or {}
    for key in (
        "retry-after",
        "x-ratelimit-reset-tokens",
        "x-ratelimit-reset-requests",
    ):
        raw = headers.get(key)
        if raw:
            try:
                cleaned = "".join(c for c in str(raw) if c.isdigit() or c == ".")
                return float(cleaned) + 3.0  # small buffer
            except (ValueError, TypeError):
                continue
    return None


def _ordered(chain: list[Provider]) -> list[Provider]:
    """Chain order, but within each family try the key that can serve soonest.

    Family order is a preference ranking (quality and limits), so it is never
    reordered — Gemini is still attempted before Cloudflare. Within one family
    the keys are interchangeable, and picking the one with the shortest wait is
    what converts N keys into N× throughput: otherwise the loop always lands on
    key #1 and sleeps out its min_gap while key #2 sits idle.
    """
    out: list[Provider] = []
    seen: set[str] = set()
    for provider in chain:
        if provider.family in seen:
            continue
        seen.add(provider.family)
        siblings = [p for p in chain if p.family == provider.family]
        if len(siblings) > 1:
            siblings.sort(key=lambda p: p.wait_time())
        out.extend(siblings)
    return out


async def call_with_failover(
    agent_name: str,
    system: str,
    user: str,
    *,
    max_tokens: int,
    byok_key: str | None = None,
    images: list[str] | None = None,
) -> str:
    """Call the first available provider; fail over down the chain on errors.

    When ``byok_key`` is set the user brought their own Anthropic key: the
    call runs ONLY on that key's premium model — never silently degraded to
    the free chain, so premium results stay premium and key errors surface.

    ``images`` are pasted charts/graphs forwarded to vision-capable providers.

    Raises ``AllProvidersRateLimitedError`` (not a plain failure) when every
    provider is on rate-limit cooldown at once — the caller can then pause and
    auto-resume instead of losing the engagement.
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
    # Providers whose latest failure was a quota limit — i.e. capacity that
    # comes back. Tracked per provider because the chain's LAST exception is a
    # bad proxy: one provider dying for another reason (a 413 too-large, a bad
    # key) would otherwise hide that the rest are simply waiting to refill.
    throttled: set[str] = set()
    for pass_no in range(_MAX_PASSES):
        for provider in _ordered(chain):
            if not provider.available():
                continue
            await provider.throttle()
            try:
                # Only pass images when present so text-only call paths (and
                # test doubles with a 3-arg signature) are unaffected.
                if images:
                    return await provider.call(system, user, max_tokens, images)
                return await provider.call(system, user, max_tokens)
            except openai.RateLimitError as exc:
                wait = _parse_reset_seconds(exc) or provider.cooldown_429
                provider.set_cooldown(min(wait, _MAX_429_COOLDOWN))
                throttled.add(provider.name)
                log.warning(
                    "%s rate-limited on %s — cooling %.0fs, failing over",
                    provider.name,
                    agent_name,
                    min(wait, _MAX_429_COOLDOWN),
                )
                last_exc = exc
            except (
                openai.AuthenticationError,
                openai.PermissionDeniedError,
                openai.NotFoundError,
            ) as exc:
                provider.set_cooldown(_UNUSABLE_COOLDOWN)
                throttled.discard(provider.name)
                log.warning(
                    "%s unusable on %s (%s) — cooling 1h, failing over",
                    provider.name,
                    agent_name,
                    type(exc).__name__,
                )
                last_exc = exc
            except Exception as exc:  # noqa: BLE001 — 5xx, timeout, empty text
                if _is_oversized(exc):
                    # The prompt is bigger than this provider's whole per-minute
                    # budget; retrying can't help. Park it for this engagement
                    # so it stops shadowing providers that only need to refill.
                    provider.set_cooldown(_UNUSABLE_COOLDOWN)
                    throttled.discard(provider.name)
                    log.warning(
                        "%s cannot fit the %s prompt (%s) — parking, failing over",
                        provider.name,
                        agent_name,
                        str(exc)[:120],
                    )
                elif _is_rate_limit(exc):
                    wait = provider.cooldown_429
                    provider.set_cooldown(min(wait, _MAX_429_COOLDOWN))
                    throttled.add(provider.name)
                    log.warning(
                        "%s rate-limited on %s (non-429 shape) — cooling %.0fs",
                        provider.name,
                        agent_name,
                        min(wait, _MAX_429_COOLDOWN),
                    )
                else:
                    provider.set_cooldown(_TRANSIENT_COOLDOWN)
                    throttled.discard(provider.name)
                    log.warning(
                        "%s failed on %s (%s: %s) — cooling %.0fs, failing over",
                        provider.name,
                        agent_name,
                        type(exc).__name__,
                        str(exc)[:200],
                        _TRANSIENT_COOLDOWN,
                    )
                last_exc = exc

        # Providers that will recover within the 429 cap (i.e. rate-limited,
        # not made unusable by a bad key / missing model). If none can recover,
        # waiting won't help — fail fast instead of sleeping out the passes.
        recoverable = [p for p in chain if p.cooldown_remaining() <= _MAX_429_COOLDOWN]
        if not recoverable:
            break

        soonest = min(p.cooldown_remaining() for p in chain)
        # A rate-limit wall the whole chain hit at once: if the soonest refill
        # is more than a brief blip away, hand control back so the engine can
        # checkpoint, pause, and auto-resume with a visible countdown — rather
        # than blocking here (and eventually failing) with work already done.
        if throttled and soonest > _RESUME_THRESHOLD:
            raise AllProvidersRateLimitedError(soonest) from last_exc

        # Otherwise the wait is short — absorb it in-call and retry the sweep.
        if pass_no < _MAX_PASSES - 1:
            await asyncio.sleep(min(soonest, 180.0) + 1.0)

    assert last_exc is not None
    # Short rate limits that kept recurring across every pass land here. This
    # is still a rate-limit wall, not a hard failure: hand back the resumable
    # error so the engine pauses and auto-resumes from its checkpoint. Raising
    # the raw error instead would fail the engagement and discard finished work.
    #
    # Keyed on ANY provider being throttled, not on last_exc: the final failure
    # in the sweep is often an unrelated shape (a parked 413) while the real
    # story is that the other providers just need time.
    if throttled:
        soonest = min(
            (p.cooldown_remaining() for p in chain if p.name in throttled),
            default=0.0,
        )
        raise AllProvidersRateLimitedError(soonest) from last_exc
    raise last_exc
