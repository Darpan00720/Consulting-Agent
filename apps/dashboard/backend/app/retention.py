"""Data-retention purge — delete engagements older than the retention window.

The product stores real, confidential business briefs and has no signup, so no
user can ever ask us to delete their data. An automatic hard-delete is the
honest substitute (see config.RETENTION_DAYS).

Purging spans two stores that must stay in sync:
  * the SQLite rows (engagement + its events + its feedback), via db.purge_expired;
  * the per-engagement telemetry JSONL file, which lives on disk outside the DB.

The DB delete is the source of truth for WHICH ids die; the telemetry file for
each is removed to match. A missing telemetry file is fine (telemetry may be
disabled) and never blocks the DB purge.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app import config, db

log = logging.getLogger(__name__)


def purge_once() -> int:
    """Run one purge sweep. Returns the number of engagements deleted.

    Never raises: retention is a background hygiene task, and a purge failure
    must not take the server down. Errors are logged for the operator.
    """
    if config.RETENTION_DAYS <= 0:
        return 0
    try:
        deleted_ids = db.purge_expired(config.RETENTION_DAYS)
    except Exception:  # noqa: BLE001 - a purge failure must not crash the server
        log.exception("retention purge (db) failed")
        return 0

    # Remove each deleted engagement's telemetry file to match the DB delete.
    tel_dir = Path(config.TELEMETRY_DIR) if config.TELEMETRY_DIR else None
    if tel_dir and tel_dir.is_dir():
        for eid in deleted_ids:
            trace = tel_dir / f"{eid}.jsonl"
            try:
                trace.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - fs race; DB row is already gone
                log.warning("could not delete telemetry file for %s", eid)

    if deleted_ids:
        log.info(
            "retention purge: deleted %d engagement(s) older than %.1f days",
            len(deleted_ids),
            config.RETENTION_DAYS,
        )
    return len(deleted_ids)


async def purge_loop() -> None:
    """Sweep on startup, then every PURGE_INTERVAL_SECONDS, for the process life.

    In-process rather than an external cron so a plain `docker run` of the image
    enforces retention with no extra moving parts. One indexed DELETE per sweep,
    so hourly is cheap.
    """
    if config.RETENTION_DAYS <= 0:
        log.info("data retention disabled (RETENTION_DAYS=0); purge loop not started")
        return
    log.info(
        "data retention: purging engagements older than %.1f days every %.0fs",
        config.RETENTION_DAYS,
        config.PURGE_INTERVAL_SECONDS,
    )
    while True:
        purge_once()
        await asyncio.sleep(config.PURGE_INTERVAL_SECONDS)
