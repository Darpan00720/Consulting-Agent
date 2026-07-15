"""StratAgent Dashboard API.

Run locally:
    cd apps/dashboard/backend
    uv run uvicorn app.main:app --reload --port 8000

No accounts: users bring their own Anthropic API key (kept in their browser,
sent per-request, never stored). A server-side ANTHROPIC_API_KEY, if set,
powers a small quota-limited free tier. STRATAGENT_MOCK=1 needs no key at all.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, db
from app.pipeline.engine import recover_interrupted
from app.routers import admin, engagements


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.connect()
    # Adopt runs a previous process left paused/running, so a redeploy doesn't
    # strand them on a countdown that will never fire.
    await recover_interrupted()
    yield


app = FastAPI(
    title="StratAgent Dashboard API",
    # Single source of truth: the repo-root VERSION file. Keep in sync.
    version="1.0.0-beta.1",
    description="Run governed AI consulting engagements from the browser.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
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
    }
