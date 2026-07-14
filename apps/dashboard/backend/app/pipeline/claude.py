"""Groq API call helper for the engagement pipeline.

Uses Groq's OpenAI-compatible endpoint (free tier, no credit card required).
Mock mode returns canned output so the full pipeline runs without any API key.
"""

from __future__ import annotations

import os

import openai

from app import config

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def friendly_error(exc: Exception) -> str:
    """Turn a raw SDK/API exception into a plain, actionable sentence."""
    status = getattr(exc, "status_code", None)
    message = str(getattr(exc, "message", "") or exc)
    low = message.lower()

    if isinstance(exc, openai.AuthenticationError) or status == 401:
        return (
            "The Groq API key was rejected. Check GROQ_API_KEY at "
            "console.groq.com → API Keys and make sure it starts with gsk_."
        )
    if isinstance(exc, openai.PermissionDeniedError) or status == 403:
        return "This Groq API key doesn't have permission to use the requested model."
    if isinstance(exc, openai.RateLimitError) or status == 429:
        return (
            "Groq rate-limited this request. The free tier has a per-minute token "
            "cap — wait a moment and run the engagement again."
        )
    if isinstance(exc, openai.APIConnectionError):
        return "Could not reach the Groq API — check the network and try again."
    if "rate limit" in low or "rate_limit" in low:
        return (
            "Groq rate-limited this request. Wait a moment and run the engagement again."
        )
    if status is not None and status >= 500:
        return "The Groq API had a temporary error. Please run the engagement again."
    return message.split("\n")[0][:300] or "The engagement failed unexpectedly."


def _get_client() -> openai.AsyncOpenAI:
    # api_key=None → openai SDK reads OPENAI_API_KEY; we override with GROQ_API_KEY.
    key = os.environ.get("GROQ_API_KEY")
    return openai.AsyncOpenAI(base_url=GROQ_BASE_URL, api_key=key or "mock-key")


async def call_agent(
    agent_name: str,
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int | None = None,
    api_key: str | None = None,  # kept for interface compatibility; ignored (no BYOK)
    model: str | None = None,
) -> str:
    """Run one specialist agent as a single Groq API call; return markdown."""
    if config.MOCK_MODE:
        return _mock_output(agent_name)

    client = _get_client()
    response = await client.chat.completions.create(
        model=model or config.MODEL,
        max_tokens=max_tokens or config.MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError(
            f"{agent_name} returned no text "
            f"(finish_reason={response.choices[0].finish_reason})"
        )
    return text


def _mock_output(agent_name: str) -> str:
    if agent_name == "grader":
        return (
            "SCORE: 62\n"
            "GOT: demo run — canned output, not a real grade\n"
            "MISSED: this was a mock-mode run; set GROQ_API_KEY for a real graded benchmark"
        )
    return (
        f"## {agent_name} (demo output)\n\n"
        "**This was a demo run** — the server is in mock mode and no Groq API "
        f"call was made, so this is canned output from {agent_name}.\n\n"
        "Set `GROQ_API_KEY` in the server environment to get real engagement "
        "analysis. Groq is free — get a key at console.groq.com.\n\n"
        "- Finding 1: placeholder\n- Finding 2: placeholder\n"
    )
