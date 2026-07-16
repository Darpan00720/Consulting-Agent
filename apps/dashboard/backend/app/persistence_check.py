"""Startup check: is the database actually on a persistent volume?

The single worst silent failure this product has: SQLite writing to the
container's ephemeral filesystem instead of the mounted volume. Everything works
— engagements run, reports render — until the next redeploy, when the whole
database vanishes. It took a production data-loss incident to notice.

This turns that silent failure loud. It compares the DB directory's mount
against the root filesystem's: if they are the SAME device, the DB is NOT on a
separate mounted volume and will not survive a restart. The result is logged at
WARNING and surfaced on /api/health, so an operator sees it immediately instead
of after losing data.

It is best-effort and read-only: on any platform where the check itself can't
run, it reports "unknown" rather than failing startup.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app import config

log = logging.getLogger(__name__)

# Set once at startup; read by /api/health.
persistence_ok: bool | None = None
persistence_detail: str = "not checked"


def check_persistence() -> tuple[bool | None, str]:
    """Return (is_persistent, human_detail). None = couldn't determine.

    A directory sitting on its OWN mount (a volume) has a different st_dev than
    the root filesystem. Same st_dev ⇒ it's just part of the ephemeral container
    layer ⇒ data is lost on redeploy.
    """
    global persistence_ok, persistence_detail
    db_dir = Path(config.DB_PATH).parent
    try:
        db_dir.mkdir(parents=True, exist_ok=True)
        db_dev = os.stat(db_dir).st_dev
        root_dev = os.stat("/").st_dev
    except OSError as exc:  # pragma: no cover - exotic FS
        persistence_ok, persistence_detail = None, f"could not stat: {exc}"
        return persistence_ok, persistence_detail

    if db_dev != root_dev:
        persistence_ok = True
        persistence_detail = f"DB dir {db_dir} is on a separate mounted volume"
        log.info("persistence check OK: %s", persistence_detail)
    else:
        persistence_ok = False
        persistence_detail = (
            f"DB dir {db_dir} is on the SAME device as / — it is NOT a mounted "
            f"volume. Data will be LOST on redeploy. Set STRATAGENT_DB to a path "
            f"inside your volume's mount, and mount the volume there."
        )
        log.warning("PERSISTENCE CHECK FAILED: %s", persistence_detail)
    return persistence_ok, persistence_detail
