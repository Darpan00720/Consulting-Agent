"""Engagement endpoints — no accounts, no signup, keys never stored.

Identity is an anonymous, browser-generated client ID sent as the
``X-Client-Id`` header (or ``?client=`` for SSE, since EventSource cannot set
headers). Two ways to run a case:

- **Free tier**: no key at all — the server's own provider chain serves the
  run, rate-limited per client id by the daily quota.
- **Best results (BYOK)**: the user sends their own API key — Anthropic,
  OpenAI, OpenRouter, Groq, or Google — in the request body. The provider is
  detected from the key prefix and the whole run uses that provider's top
  model. The key is handed straight to the pipeline for this run only —
  NEVER persisted, NEVER logged, and it bypasses the free-tier quota.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import config, db
from app.events import bus
from app.pipeline.engine import PHASES, run_engagement
from app.pipeline.providers import UnsupportedKeyError, detect_byok

router = APIRouter(prefix="/api/engagements", tags=["engagements"])

TERMINAL_EVENTS = {"engagement_completed", "engagement_failed"}

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def client_id(
    x_client_id: str | None = Header(default=None),
    client: str | None = Query(default=None),
) -> str:
    """Anonymous per-browser identity (header, or ?client= for SSE)."""
    raw = x_client_id or client
    if not raw or not _CLIENT_ID_RE.match(raw):
        raise HTTPException(status_code=400, detail="Missing or invalid client id")
    return raw


class CreateEngagementRequest(BaseModel):
    case_prompt: str = Field(min_length=40, max_length=20_000)
    model: str | None = Field(default=None, max_length=64)
    # User's own API key (any supported provider — best-results path).
    # Used for this run only — never persisted, never logged.
    api_key: str | None = Field(default=None, min_length=8, max_length=200)


class EngagementSummary(BaseModel):
    id: str
    case_prompt: str
    status: str
    created_at: float
    completed_at: float | None


@router.post("", status_code=202)
async def create_engagement(
    body: CreateEngagementRequest, cid: str = Depends(client_id)
) -> dict[str, Any]:
    model = body.model
    if model is not None and not config.is_allowed_model(model):
        raise HTTPException(status_code=422, detail=f"Unsupported model: {model}")

    byok = bool(body.api_key)
    if byok:
        # Reject an unrecognized key format up front (clear 422) rather than
        # letting the engagement start and fail minutes in.
        try:
            detect_byok(body.api_key or "")
        except UnsupportedKeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        if not (config.SERVER_HAS_KEY or config.MOCK_MODE):
            raise HTTPException(
                status_code=503,
                detail="The server has no AI provider key configured. Set "
                "GEMINI_API_KEY, OPENROUTER_API_KEY, or GROQ_API_KEY in the "
                "server environment — or supply your own API key with the run.",
            )
        if db.engagements_today(cid) >= config.DAILY_ENGAGEMENT_QUOTA:
            raise HTTPException(
                status_code=429,
                detail=f"Free-tier limit reached ({config.DAILY_ENGAGEMENT_QUOTA} "
                "engagements/24h). Try again tomorrow — or add your own API key "
                "for unlimited premium runs.",
            )

    try:
        engagement_id = db.create_engagement(cid, body.case_prompt)
    except Exception as exc:  # noqa: BLE001 — return a clean, CORS-safe error
        # An unhandled 500 loses its CORS headers, so the browser only sees
        # "Failed to fetch". Convert storage failures into a proper HTTP error.
        raise HTTPException(
            status_code=503,
            detail="The server could not start the engagement (storage error). "
            "Please try again in a moment.",
        ) from exc

    asyncio.create_task(
        run_engagement(
            engagement_id, body.case_prompt, model=model, api_key=body.api_key
        )
    )
    return {"id": engagement_id, "status": "queued", "phases": [p for p, _ in PHASES]}


@router.get("", response_model=list[EngagementSummary])
def list_engagements(cid: str = Depends(client_id)) -> list[dict[str, Any]]:
    return db.list_engagements(cid)


def _owned_engagement(engagement_id: str, cid: str) -> dict[str, Any]:
    engagement = db.get_engagement(engagement_id)
    if engagement is None or engagement["client_id"] != cid:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return engagement


@router.get("/{engagement_id}")
def get_engagement(engagement_id: str, cid: str = Depends(client_id)) -> dict[str, Any]:
    engagement = _owned_engagement(engagement_id, cid)
    engagement.pop("client_id")
    return engagement


@router.get("/{engagement_id}/events")
async def stream_events(
    engagement_id: str, cid: str = Depends(client_id)
) -> StreamingResponse:
    """SSE stream: replays persisted events, then tails live ones."""
    _owned_engagement(engagement_id, cid)

    async def generator():
        queue = await bus.subscribe(engagement_id)
        try:
            last_seq = 0
            done = False
            for event in db.list_events(engagement_id):
                last_seq = event["seq"]
                done = done or event["type"] in TERMINAL_EVENTS
                yield f"data: {json.dumps(event)}\n\n"
            if done:
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event["seq"] <= last_seq:
                    continue
                last_seq = event["seq"]
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in TERMINAL_EVENTS:
                    return
        finally:
            await bus.unsubscribe(engagement_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
