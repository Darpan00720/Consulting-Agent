"""Lessons endpoints — the standing playbook the reflection loop builds.

Lessons are global, process-only guardrails (never case facts) injected into
every future engagement. Exposed read-only + delete so the operator can audit
and prune what the agent has "learned".
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app import db

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("")
def list_lessons() -> list[dict[str, Any]]:
    return db.list_lessons()


@router.delete("/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: int) -> None:
    db.delete_lesson(lesson_id)
