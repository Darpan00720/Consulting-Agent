"""Agent call entry point for the engagement pipeline.

Delegates to the multi-provider failover chain in ``providers.py``
(Gemini 2.5 Flash → OpenRouter free → Groq). Mock mode returns canned
output so the full pipeline runs without any API key.
"""

from __future__ import annotations

import logging

import openai

from app import config
from app.pipeline import providers

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)


def friendly_error(exc: Exception) -> str:
    """Turn a raw SDK/API exception into a plain, actionable sentence."""
    status = getattr(exc, "status_code", None)
    message = str(getattr(exc, "message", "") or exc)
    low = message.lower()

    if isinstance(exc, openai.AuthenticationError) or status == 401:
        return (
            "An API key was rejected by its provider. If you supplied your own "
            "API key, please check it; otherwise the server's provider keys "
            "(GEMINI_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY) need attention."
        )
    if isinstance(exc, openai.NotFoundError) or status == 404:
        return "The configured model was not found on its provider."
    if isinstance(exc, openai.PermissionDeniedError) or status == 403:
        return "An AI provider API key doesn't have permission for the requested model."
    if isinstance(exc, openai.RateLimitError) or status == 429 or "rate limit" in low or "rate_limit" in low:
        return (
            "All configured AI providers are rate-limited right now. "
            "Wait a minute and run the engagement again."
        )
    if isinstance(exc, openai.APIConnectionError):
        return "Could not reach any AI provider — check the network and try again."
    if status is not None and status >= 500:
        return "The AI provider had a temporary error. Please run the engagement again."
    if "no llm provider configured" in low:
        return message
    return message.split("\n")[0][:300] or "The engagement failed unexpectedly."


async def call_agent(
    agent_name: str,
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int | None = None,
    api_key: str | None = None,  # user's own Anthropic key (BYOK premium path)
    model: str | None = None,    # kept for interface compatibility; chain picks models
) -> str:
    """Run one specialist agent as a single LLM call; return markdown.

    With ``api_key`` the call runs on the user's own Anthropic key (premium
    Claude model, no free-tier limits). Otherwise the provider failover chain
    decides which free provider serves the call, paces requests to each
    provider's rate limits, and fails over automatically on outages.
    """
    if config.MOCK_MODE:
        return _mock_output(agent_name)

    return await providers.call_with_failover(
        agent_name,
        system_prompt,
        user_message,
        max_tokens=max_tokens or config.MAX_TOKENS,
        byok_key=api_key,
    )


def _mock_output(agent_name: str) -> str:
    if agent_name == "grader":
        return (
            "SCORE: 62\n"
            "GOT: demo run — canned output, not a real grade\n"
            "MISSED: this was a mock-mode run; set a provider API key for a real graded benchmark"
        )
    return (
        f"## {agent_name} (demo output)\n\n"
        "**This was a demo run** — the server is in mock mode and no LLM API "
        f"call was made, so this is canned output from {agent_name}.\n\n"
        "Set `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, or `GROQ_API_KEY` in the "
        "server environment to get real engagement analysis — all three have "
        "free tiers.\n\n"
        "- Finding 1: placeholder\n- Finding 2: placeholder\n"
    )
