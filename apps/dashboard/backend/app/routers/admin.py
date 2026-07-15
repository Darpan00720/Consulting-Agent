"""Operator console — private, token-gated, read-only.

This is the one place that crosses the per-client boundary the rest of the API
enforces: it shows every engagement, every comment, and every failure trace so
one operator can answer "is it working, for whom, and where does it break?"

Security posture
----------------
* Gated on ``STRATAGENT_ADMIN_TOKEN``. Unset ⇒ every route **404s**, so an
  unconfigured deployment does not advertise an admin surface at all.
* A wrong token also gets 404, not 403 — a probe learns nothing either way.
* Compared with ``secrets.compare_digest`` (constant time), so the token can't
  be recovered a character at a time.
* Read-only by construction: no route here mutates state.
* It reports `used_byok` (a boolean flag) — never key material, which is never
  stored in the first place.
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app import config, db

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(
    x_admin_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> None:
    """Gate every admin route. 404 on any failure — never reveal the surface.

    Accepts the token via header (normal use) or query string, because the
    browser page loads it from a URL the operator pastes once.
    """
    if not config.ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")
    supplied = x_admin_token or token or ""
    if not secrets.compare_digest(supplied, config.ADMIN_TOKEN):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/overview", dependencies=[Depends(require_admin)])
def overview() -> dict[str, Any]:
    """Fleet counters: volume, users, success/failure, free vs BYOK."""
    return db.admin_overview()


@router.get("/engagements", dependencies=[Depends(require_admin)])
def engagements(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict[str, Any]]:
    """Every engagement, newest first, with feedback and failure step attached."""
    return db.admin_engagements(limit=limit)


@router.get("/lessons", dependencies=[Depends(require_admin)])
def lessons() -> list[dict[str, Any]]:
    """What the platform has learned. Reflection runs after EVERY engagement, so
    this grows on its own; it moved here when the public Lessons page was cut."""
    return db.list_lessons(limit=200)
