"""Claude API call helper for the engagement pipeline.

One function, `call_agent`, wraps the AsyncAnthropic streaming call with the
skill-recommended defaults: adaptive thinking, streaming with
get_final_message(), no sampling parameters. Mock mode returns canned output
so the full pipeline can run without an API key.
"""

from __future__ import annotations

import anthropic

from app import config


def friendly_error(exc: Exception) -> str:
    """Turn a raw SDK/API exception into a plain, actionable sentence.

    The Anthropic SDK's ``str(exc)`` is a raw JSON dump; users shouldn't see
    that. Map the common cases to guidance, especially the billing and auth
    errors a bring-your-own-key user is most likely to hit.
    """
    status = getattr(exc, "status_code", None)
    message = str(getattr(exc, "message", "") or exc)
    low = message.lower()

    if "credit balance is too low" in low or "plans & billing" in low:
        return (
            "Your Anthropic account has no API credits. Add credits at "
            "console.anthropic.com → Plans & Billing, then run the engagement "
            "again. (API usage is pay-as-you-go and separate from any Claude "
            "subscription.)"
        )
    if isinstance(exc, anthropic.AuthenticationError) or status == 401:
        return (
            "That API key was rejected. Check it at console.anthropic.com → "
            "API Keys and paste a valid key (it should start with sk-ant-)."
        )
    if isinstance(exc, anthropic.PermissionDeniedError) or status == 403:
        return "This API key doesn't have permission to use the requested model."
    if isinstance(exc, anthropic.RateLimitError) or status == 429:
        return "Anthropic rate-limited this key. Wait a moment and run the engagement again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach the Anthropic API — check the network and try again."
    if status is not None and status >= 500:
        return "The Anthropic API had a temporary error. Please run the engagement again."
    # Fall back to the SDK's message, but never the whole JSON blob.
    return message.split("\n")[0][:300] or "The engagement failed unexpectedly."

# One client per credential: index 0 = server credentials (env/profile),
# otherwise keyed by the user's own API key (BYOK).
_clients: dict[str | None, anthropic.AsyncAnthropic] = {}


def _get_client(api_key: str | None) -> anthropic.AsyncAnthropic:
    if api_key not in _clients:
        # api_key=None → SDK resolves server credentials from the environment
        # (ANTHROPIC_API_KEY or an `ant auth login` profile) — never hardcoded.
        _clients[api_key] = (
            anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()
        )
    return _clients[api_key]


async def call_agent(
    agent_name: str,
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """Run one specialist agent as a single Claude API call; return markdown."""
    # Mock mode only covers keyless demo runs — a user-supplied key always
    # gets the real pipeline, even on a server started with STRATAGENT_MOCK=1.
    if config.MOCK_MODE and api_key is None:
        return _mock_output(agent_name)

    client = _get_client(api_key)
    async with client.messages.stream(
        model=model or config.MODEL,
        max_tokens=max_tokens or config.MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        message = await stream.get_final_message()

    text = "".join(block.text for block in message.content if block.type == "text")
    if not text.strip():
        raise RuntimeError(
            f"{agent_name} returned no text (stop_reason={message.stop_reason})"
        )
    return text


def _mock_output(agent_name: str) -> str:
    if agent_name == "grader":
        # A parseable demo grade so the benchmark loop is visible in mock mode.
        return (
            "SCORE: 62\n"
            "GOT: demo run — canned output, not a real grade\n"
            "MISSED: this was a mock-mode run; add an API key for a real graded benchmark"
        )
    return (
        f"## {agent_name} (demo output)\n\n"
        "**This was a demo run** — the server is in mock mode and no Claude API "
        f"call was made, so this is canned output from {agent_name}.\n\n"
        "**Add your Anthropic API key and run again to get a real engagement** "
        "with genuine analysis on your case.\n\n"
        "- Finding 1: placeholder\n- Finding 2: placeholder\n"
    )
