"""Golden-case benchmark endpoints.

A golden case = {title, case prompt, official model answer}. Running it
executes a full engagement, grades the report against the model answer, and
feeds the gaps into the lessons store — so the agent measurably improves and
the score history proves it.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import config, db
from app.pipeline.grading import run_case_eval
from app.routers.engagements import client_id

router = APIRouter(prefix="/api/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    prompt: str = Field(min_length=40, max_length=20_000)
    # The official model answer / grading rubric the report is scored against.
    rubric: str = Field(min_length=40, max_length=20_000)


class RunEvalRequest(BaseModel):
    # Same BYOK semantics as engagements: used for this run only, never stored.
    api_key: str | None = Field(default=None, min_length=20, max_length=300)
    model: str | None = Field(default=None, max_length=64)


@router.post("", status_code=201)
def create_case(body: CreateCaseRequest, cid: str = Depends(client_id)) -> dict[str, Any]:
    case_id = db.create_case(cid, body.title.strip(), body.prompt, body.rubric)
    return {"id": case_id, "title": body.title.strip()}


@router.get("")
def list_cases(cid: str = Depends(client_id)) -> list[dict[str, Any]]:
    return db.list_cases(cid)


def _owned_case(case_id: str, cid: str) -> dict[str, Any]:
    case = db.get_case(case_id)
    if case is None or case["client_id"] != cid:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/{case_id}")
def get_case(case_id: str, cid: str = Depends(client_id)) -> dict[str, Any]:
    case = _owned_case(case_id, cid)
    case.pop("client_id")
    return case


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: str, cid: str = Depends(client_id)) -> None:
    _owned_case(case_id, cid)
    db.delete_case(case_id, cid)


@router.get("/{case_id}/evals")
def list_evals(case_id: str, cid: str = Depends(client_id)) -> list[dict[str, Any]]:
    _owned_case(case_id, cid)
    return db.list_evals(case_id)


@router.post("/{case_id}/run", status_code=202)
async def run_eval(
    case_id: str, body: RunEvalRequest, cid: str = Depends(client_id)
) -> dict[str, Any]:
    case = _owned_case(case_id, cid)

    api_key = body.api_key.strip() if body.api_key else None
    if api_key and not api_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=422,
            detail="That doesn't look like an Anthropic API key (should start with sk-ant-)",
        )
    model = body.model
    if model is not None and not config.is_allowed_model(model):
        raise HTTPException(status_code=422, detail=f"Unsupported model: {model}")

    if api_key is None:
        # Same free-tier gating as engagements: server credentials + quota.
        if not (config.SERVER_HAS_KEY or config.MOCK_MODE):
            raise HTTPException(
                status_code=402,
                detail="Add your Anthropic API key to run a benchmark — it stays in "
                "your browser and is used only for your runs.",
            )
        if db.engagements_today(cid) >= config.DAILY_ENGAGEMENT_QUOTA:
            raise HTTPException(
                status_code=429,
                detail=f"Free-tier limit reached ({config.DAILY_ENGAGEMENT_QUOTA} engagements/24h). "
                "Add your own API key for unlimited runs.",
            )

    try:
        engagement_id = db.create_engagement(cid, case["prompt"])
        eval_id = db.create_eval(case_id, engagement_id)
    except Exception as exc:  # noqa: BLE001 — clean, CORS-safe error
        raise HTTPException(
            status_code=503,
            detail="The server could not start the benchmark run (storage error). "
            "Please try again in a moment.",
        ) from exc

    asyncio.create_task(
        run_case_eval(
            eval_id,
            engagement_id,
            case["prompt"],
            case["rubric"],
            api_key=api_key,
            model=model,
        )
    )
    return {"eval_id": eval_id, "engagement_id": engagement_id, "status": "queued"}
