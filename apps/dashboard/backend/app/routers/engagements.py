"""Engagement endpoints — no accounts, no signup, keys never stored.

Identity is an anonymous, browser-generated client ID sent as the
``X-Client-Id`` header (or ``?client=`` for SSE, since EventSource cannot set
headers). Two ways to run a case:

- **Free tier**: no key at all — the server's own provider chain serves the
  run, rate-limited per client id by the daily quota.
- **Best results (BYOK)**: the user sends their own API key — Anthropic,
  OpenAI, OpenRouter, Cerebras, Groq, or Google — in the request body. The
  provider is detected from the key prefix and the whole run uses that
  provider's top model. The key is handed straight to the pipeline for this
  run only — NEVER persisted, NEVER logged, and it bypasses the free-tier quota.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

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


def _source_ip(request: Request) -> str:
    """The caller's IP, as trustworthy as the deployment allows.

    X-Forwarded-For is caller-supplied, so it is honoured ONLY when
    ``STRATAGENT_TRUST_PROXY=1`` says a reverse proxy really is in front. Then
    the LAST entry is the one our own proxy observed and appended; the earlier
    entries are whatever the client chose to claim, and trusting those would
    reopen the exact bypass this quota exists to close.
    """
    if config.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def source_fingerprint(request: Request) -> str:
    """Salted hash of the caller's IP — a spoof-resistant quota key.

    Hashed, never stored raw: an IP is PII and this product holds nothing about
    its users. The salt makes the digest useless outside this deployment.
    """
    ip = _source_ip(request)
    return hashlib.sha256(f"{config.IP_HASH_SALT}:{ip}".encode()).hexdigest()[:32]


class CreateEngagementRequest(BaseModel):
    # No max_length here by design: a case brief shouldn't be artificially
    # truncated. The `_cap_total_payload` validator below is the real
    # backstop against a pathological request (already existed for images;
    # now the only ceiling on case_prompt too) — memory/DoS protection, not a
    # content-quality judgment about how long a real case is allowed to be.
    case_prompt: str = Field(min_length=40)
    model: str | None = Field(default=None, max_length=64)
    # User's own API key (any supported provider — best-results path).
    # Used for this run only — never persisted, never logged.
    api_key: str | None = Field(default=None, min_length=8, max_length=200)
    # Pasted charts/graphs/screenshots as data:image/* URLs. Passed to
    # vision-capable providers for this run only — never persisted (privacy:
    # a pasted chart may hold client data, so it never touches disk).
    images: list[str] | None = Field(default=None, max_length=6)

    @field_validator("images")
    @classmethod
    def _validate_images(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return value
        for img in value:
            if not img.startswith("data:image/"):
                raise ValueError("images must be data:image/* URLs")
            if len(img) > 7_000_000:  # ~5 MB decoded — the frontend downscales
                raise ValueError("each image must be under ~5 MB")
        return value

    @model_validator(mode="after")
    def _cap_total_payload(self) -> CreateEngagementRequest:
        # Per-field caps still allow ~42 MB in aggregate (6 × 7 MB + prompt),
        # unbounded across concurrent requests. Cap the whole payload so one
        # request can't pin memory or starve others.
        total = len(self.case_prompt) + sum(len(i) for i in (self.images or []))
        if total > 20_000_000:  # ~20 MB request ceiling
            raise ValueError(
                "Total request too large — reduce the number or size of images."
            )
        return self


class EngagementSummary(BaseModel):
    id: str
    case_prompt: str
    status: str
    created_at: float
    completed_at: float | None


@router.post("", status_code=202)
async def create_engagement(
    body: CreateEngagementRequest,
    request: Request,
    cid: str = Depends(client_id),
) -> dict[str, Any]:
    model = body.model
    if model is not None and not config.is_allowed_model(model):
        raise HTTPException(status_code=422, detail=f"Unsupported model: {model}")

    # Hash the source even for BYOK runs, so the column is populated for the
    # operator view — but only free runs are counted against the IP quota.
    ip_hash = source_fingerprint(request)

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
                "GEMINI_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY, or "
                "GITHUB_MODELS_TOKEN in the server environment — or supply "
                "your own API key with the run.",
            )
        if db.engagements_today(cid) >= config.DAILY_ENGAGEMENT_QUOTA:
            raise HTTPException(
                status_code=429,
                detail=f"Free-tier limit reached ({config.DAILY_ENGAGEMENT_QUOTA} "
                "engagements/24h). Try again tomorrow — or add your own API key "
                "for unlimited premium runs.",
            )
        # The client id above is caller-asserted, so that quota alone is a
        # courtesy limit: send a fresh id per request and it never triggers.
        # This one keys off something the caller cannot choose, and is what
        # actually protects the shared provider quota on a public deployment.
        if (
            config.DAILY_IP_QUOTA > 0
            and db.engagements_today_from_ip(ip_hash) >= config.DAILY_IP_QUOTA
        ):
            raise HTTPException(
                status_code=429,
                detail="Daily free-tier limit reached for this network "
                f"({config.DAILY_IP_QUOTA} engagements/24h). Add your own API key "
                "to keep going — your key is used for that run only and is never "
                "stored.",
            )

    try:
        # used_byok records THAT a user key was used, never the key itself —
        # it lets restart recovery skip runs it cannot legitimately resume.
        engagement_id = db.create_engagement(
            cid, body.case_prompt, used_byok=byok, ip_hash=ip_hash
        )
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
            engagement_id,
            body.case_prompt,
            model=model,
            api_key=body.api_key,
            images=body.images,
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


class FeedbackRequest(BaseModel):
    # Long enough for a real explanation of what the analysis got wrong — that
    # detail is the whole point of collecting it.
    comment: str = Field(min_length=1, max_length=4000)
    rating: str | None = None

    @field_validator("rating")
    @classmethod
    def _validate_rating(cls, value: str | None) -> str | None:
        if value not in (None, "helpful", "not_helpful"):
            raise ValueError("rating must be 'helpful' or 'not_helpful'")
        return value


@router.post("/{engagement_id}/feedback", status_code=201)
def add_feedback(
    engagement_id: str, body: FeedbackRequest, cid: str = Depends(client_id)
) -> dict[str, Any]:
    """Record a reader's comment on their own report.

    Ownership is enforced via _owned_engagement: you can only annotate an
    engagement you ran, so this can't be used to write into someone else's.
    """
    _owned_engagement(engagement_id, cid)
    feedback_id = db.add_feedback(engagement_id, cid, body.comment.strip(), body.rating)
    return {"id": feedback_id, "status": "recorded"}


@router.get("/{engagement_id}/feedback")
def list_feedback(
    engagement_id: str, cid: str = Depends(client_id)
) -> list[dict[str, Any]]:
    _owned_engagement(engagement_id, cid)
    return db.list_feedback(engagement_id)


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
                except TimeoutError:
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
