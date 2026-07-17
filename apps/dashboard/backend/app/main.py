"""StratAgent Dashboard API.

Run locally:
    cd apps/dashboard/backend
    uv run uvicorn app.main:app --reload --port 8000

No accounts: users bring their own Anthropic API key (kept in their browser,
sent per-request, never stored). A server-side ANTHROPIC_API_KEY, if set,
powers a small quota-limited free tier. STRATAGENT_MOCK=1 needs no key at all.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import config, db, persistence_check, retention
from app.pipeline.engine import recover_interrupted
from app.routers import admin, engagements

# Coarse hard ceiling on any request body, enforced at the ASGI layer BEFORE the
# body is buffered. The per-field/total Pydantic caps (CreateEngagementRequest)
# only run after Starlette has read the whole body into memory, so on their own
# they don't stop an attacker from streaming a multi-GB body to exhaust RAM.
# This is deliberately set WELL ABOVE the 20 MB application-level total cap: the
# Pydantic validators remain the precise limit (and keep returning an accurate
# 422 for a "slightly too large" request), while this backstop only catches the
# genuinely abusive bodies that would otherwise buffer unbounded. Worst case per
# request is bounded here, and overall by MAX_CONCURRENT_ENGAGEMENTS.
_MAX_BODY_BYTES = 32 * 1024 * 1024


class MaxBodySizeMiddleware:
    """Reject an over-large request body without buffering it.

    Works for both Content-Length and chunked/streamed bodies: it fast-rejects
    on a too-large Content-Length header, then counts bytes as they arrive and
    aborts the moment the running total crosses the ceiling — so a body with no
    (or a lying) Content-Length can't slip past. Returns 413 and never calls the
    downstream app for a rejected request.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = _MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self.max_bytes:
            await _reject_413(send)
            return

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Signal end-of-stream to the app is unsafe mid-parse; instead
                    # we raise, which Starlette turns into a clean error response.
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, counting_receive, send)
        except _BodyTooLarge:
            await _reject_413(send)


class _BodyTooLarge(Exception):
    """Internal signal: streamed body crossed the ceiling."""


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _reject_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"detail":"Request body too large."}',
        }
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.connect()
    # Loudly flag the worst silent failure this product has: a DB on ephemeral
    # storage that vanishes on the next redeploy (a real production incident).
    persistence_check.check_persistence()
    # Adopt runs a previous process left paused/running, so a redeploy doesn't
    # strand them on a countdown that will never fire.
    await recover_interrupted()
    # Enforce data retention for the process lifetime (no external cron needed).
    purge_task = asyncio.create_task(retention.purge_loop())
    try:
        yield
    finally:
        purge_task.cancel()


app = FastAPI(
    title="StratAgent Dashboard API",
    # Single source of truth: the repo-root VERSION file. Keep in sync.
    version="1.0.0-beta.1",
    description="Run governed AI consulting engagements from the browser.",
    lifespan=lifespan,
)

# Body-size guard added first so it sits INSIDE CORS: CORS stays outermost and
# decorates every response — including a 413 — with the right headers.
app.add_middleware(MaxBodySizeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # Identity is header-based (X-Client-Id / X-Admin-Token) — no cookies, so
    # credentialed CORS is not needed. Leaving it off keeps a misconfigured
    # origin list (e.g. "*") from being paired with credentials, and avoids
    # echoing Access-Control-Allow-Credentials to every caller.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(engagements.router)
# The public Benchmark and Lessons surfaces were removed: every engagement now
# feeds the learning loop automatically (reflection runs after EVERY run), so
# there was nothing for a user to do there. Lessons are visible to the operator
# via /api/admin/lessons. The `cases`/`evals` tables remain for the golden-case
# harness; they are simply not exposed to end users any more.
app.include_router(admin.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "model": config.MODEL,
        "models": config.MODEL_CHOICES,
        "mock": config.MOCK_MODE,
        "free_tier": config.SERVER_HAS_KEY or config.MOCK_MODE,
        "free_tier_quota": config.DAILY_ENGAGEMENT_QUOTA,
        # So the privacy note on the landing page states the true window rather
        # than a hardcoded number that could drift from the actual purge.
        "retention_days": config.RETENTION_DAYS,
        # True/False/None — an operator (or a monitor) can see at a glance
        # whether the database is on durable storage. None = couldn't determine.
        "persistent_storage": persistence_check.persistence_ok,
    }
