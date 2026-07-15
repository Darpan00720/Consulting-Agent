"""SQLite storage for engagements and engagement events.

No user accounts: engagements belong to an anonymous, browser-generated
client ID. API keys are never persisted — they travel per-request and go
straight to the Claude client.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from typing import Any

from app import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS engagements (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    case_prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    report_md TEXT,
    error TEXT,
    review_verdict TEXT,
    challenge_verdict TEXT,
    review_ready INTEGER,
    -- Whether the run used a user-supplied key. NOT the key itself (keys are
    -- never persisted) — just a flag, so a restart can tell which paused runs
    -- are safe to resume on the server's own providers.
    used_byok INTEGER NOT NULL DEFAULT 0,
    -- Salted hash of the source IP — never the IP itself. Enough to enforce a
    -- per-source quota the caller cannot spoof (unlike client_id), useless for
    -- identifying anyone. See config.IP_HASH_SALT.
    ip_hash TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_engagements_client ON engagements(client_id, created_at);
-- NOTE: the ip_hash index is created in _migrate(), never here. This script runs
-- BEFORE the migration, and on an existing database CREATE TABLE IF NOT EXISTS
-- is a no-op — so indexing a column added later fails outright ("no such column:
-- ip_hash") and the process dies at startup. Any index on a migrated column
-- belongs in _migrate.
-- Reader feedback on a delivered report. This is the only channel through which
-- a real user tells us the analysis was wrong, so it is stored verbatim and
-- never summarised away. Multiple notes per engagement are allowed (someone may
-- come back after re-reading).
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id TEXT NOT NULL REFERENCES engagements(id),
    client_id TEXT NOT NULL,
    -- 'helpful' | 'not_helpful' | NULL — a one-click signal, optional so a
    -- comment is never gated behind picking a rating.
    rating TEXT,
    comment TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_engagement ON feedback(engagement_id);
CREATE TABLE IF NOT EXISTS events (
    engagement_id TEXT NOT NULL REFERENCES engagements(id),
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (engagement_id, seq)
);
CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL UNIQUE,
    engagement_id TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    title TEXT NOT NULL,
    prompt TEXT NOT NULL,
    rubric TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cases_client ON cases(client_id, created_at);
CREATE TABLE IF NOT EXISTS evals (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    engagement_id TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    score INTEGER,
    detail TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_evals_case ON evals(case_id, created_at);
"""


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA)
        _migrate(_conn)
        _conn.commit()
    return _conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was first created.

    CREATE TABLE IF NOT EXISTS leaves existing tables untouched, so a DB from
    an older build lacks newer columns. Now that the SQLite file survives
    redeploys (docker volume), these have to be applied in place.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(engagements)")}
    if "used_byok" not in existing:
        conn.execute(
            "ALTER TABLE engagements ADD COLUMN used_byok INTEGER NOT NULL DEFAULT 0"
        )
    if "ip_hash" not in existing:
        conn.execute("ALTER TABLE engagements ADD COLUMN ip_hash TEXT")
    # Unconditional: the column exists by now on BOTH paths (fresh DBs get it
    # from CREATE TABLE, older ones from the ALTER above), and a fresh DB would
    # otherwise never get the index at all — the migration branch wouldn't run.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_engagements_ip"
        " ON engagements(ip_hash, created_at)"
    )


def reset_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


# --- engagements ------------------------------------------------------------


def create_engagement(
    client_id: str,
    case_prompt: str,
    *,
    used_byok: bool = False,
    ip_hash: str | None = None,
) -> str:
    engagement_id = f"eng_{uuid.uuid4().hex}"
    with _lock:
        conn = connect()
        conn.execute(
            "INSERT INTO engagements (id, client_id, case_prompt, status, used_byok,"
            " ip_hash, created_at) VALUES (?,?,?, 'queued', ?, ?, ?)",
            (
                engagement_id,
                client_id,
                case_prompt,
                1 if used_byok else 0,
                ip_hash,
                time.time(),
            ),
        )
        conn.commit()
    return engagement_id


def engagements_today_from_ip(ip_hash: str) -> int:
    """Free-tier runs from one source in 24h.

    Counts only free-tier runs: a BYOK visitor spends their own quota, so
    rate-limiting them protects nothing and would punish the users we most want.
    """
    day_start = time.time() - 86400
    with _lock:
        row = (
            connect()
            .execute(
                "SELECT COUNT(*) AS n FROM engagements"
                " WHERE ip_hash = ? AND used_byok = 0 AND created_at > ?",
                (ip_hash, day_start),
            )
            .fetchone()
        )
    return int(row["n"])


def interrupted_engagements() -> list[dict[str, Any]]:
    """Runs left mid-flight by a server stop (status running/paused).

    Their in-process asyncio resume task died with the old process, so nothing
    would ever move them again — startup recovery adopts or closes them.
    """
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT id, case_prompt, used_byok FROM engagements"
                " WHERE status IN ('running', 'paused')"
            )
            .fetchall()
        )
    return [dict(row) for row in rows]


def engagements_today(client_id: str) -> int:
    day_start = time.time() - 86400
    with _lock:
        row = (
            connect()
            .execute(
                "SELECT COUNT(*) AS n FROM engagements"
                " WHERE client_id = ? AND created_at > ?",
                (client_id, day_start),
            )
            .fetchone()
        )
    return int(row["n"])


def set_governance(
    engagement_id: str,
    *,
    review_verdict: str,
    challenge_verdict: str,
    review_ready: bool,
) -> None:
    with _lock:
        conn = connect()
        conn.execute(
            "UPDATE engagements SET review_verdict = ?, challenge_verdict = ?,"
            " review_ready = ? WHERE id = ?",
            (
                review_verdict,
                challenge_verdict,
                1 if review_ready else 0,
                engagement_id,
            ),
        )
        conn.commit()


def get_engagement(engagement_id: str) -> dict[str, Any] | None:
    with _lock:
        row = (
            connect()
            .execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
            .fetchone()
        )
    return dict(row) if row else None


def list_engagements(client_id: str) -> list[dict[str, Any]]:
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT id, case_prompt, status, created_at, completed_at"
                " FROM engagements WHERE client_id = ? ORDER BY created_at DESC",
                (client_id,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


# --- feedback ---------------------------------------------------------------


def add_feedback(
    engagement_id: str, client_id: str, comment: str, rating: str | None = None
) -> int:
    with _lock:
        conn = connect()
        cur = conn.execute(
            "INSERT INTO feedback (engagement_id, client_id, rating, comment,"
            " created_at) VALUES (?,?,?,?,?)",
            (engagement_id, client_id, rating, comment, time.time()),
        )
        conn.commit()
    return int(cur.lastrowid or 0)


def list_feedback(engagement_id: str) -> list[dict[str, Any]]:
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT id, rating, comment, created_at FROM feedback"
                " WHERE engagement_id = ? ORDER BY created_at",
                (engagement_id,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


# --- admin (operator-only; see routers/admin.py) -----------------------------


def admin_overview() -> dict[str, Any]:
    """Fleet-wide counters for the operator view.

    `used_byok` records only THAT a user brought a key, never the key — so free
    vs BYOK is answerable without ever having stored credentials.
    """
    with _lock:
        conn = connect()
        row = conn.execute("""
            SELECT
              COUNT(*)                                            AS total,
              COUNT(DISTINCT client_id)                           AS users,
              SUM(status = 'completed')                           AS completed,
              SUM(status = 'failed')                              AS failed,
              SUM(status IN ('running', 'queued', 'paused'))      AS in_flight,
              SUM(used_byok = 1)                                  AS byok_runs,
              SUM(used_byok = 0)                                  AS free_runs,
              SUM(review_ready = 1)                               AS shipped_final,
              SUM(status = 'completed' AND review_ready = 0)      AS interim_only
            FROM engagements
            """).fetchone()
        feedback_count = conn.execute("SELECT COUNT(*) AS n FROM feedback").fetchone()
        lessons_count = conn.execute("SELECT COUNT(*) AS n FROM lessons").fetchone()
    out = {k: (row[k] or 0) for k in row.keys()}
    out["feedback_count"] = feedback_count["n"]
    out["lessons_learned"] = lessons_count["n"]
    return out


def admin_engagements(limit: int = 200) -> list[dict[str, Any]]:
    """Every engagement across all clients, with feedback attached.

    `failed_at` answers "which step is breaking?" — the last phase that started
    without completing. Derived from the event log rather than stored, so it
    stays correct for runs that failed before this view existed.
    """
    with _lock:
        conn = connect()
        rows = conn.execute(
            """
            SELECT e.id, e.client_id, e.case_prompt, e.status, e.error,
                   e.review_verdict, e.challenge_verdict, e.review_ready,
                   e.used_byok, e.created_at, e.completed_at,
                   (SELECT COUNT(*) FROM feedback f WHERE f.engagement_id = e.id)
                     AS feedback_count
            FROM engagements e ORDER BY e.created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = dict(r)
            started = [
                json.loads(p)["phase"]
                for (p,) in conn.execute(
                    "SELECT payload FROM events WHERE engagement_id = ?"
                    " AND type = 'phase_started' ORDER BY seq",
                    (r["id"],),
                )
            ]
            done = [
                json.loads(p)["phase"]
                for (p,) in conn.execute(
                    "SELECT payload FROM events WHERE engagement_id = ?"
                    " AND type = 'phase_completed' ORDER BY seq",
                    (r["id"],),
                )
            ]
            unfinished = [p for p in started if p not in done]
            item["failed_at"] = unfinished[-1] if unfinished else None
            item["phases_completed"] = len(set(done))
            item["pauses"] = conn.execute(
                "SELECT COUNT(*) AS n FROM events WHERE engagement_id = ?"
                " AND type = 'engagement_paused'",
                (r["id"],),
            ).fetchone()["n"]
            item["feedback"] = list_feedback_unlocked(conn, r["id"])
            out.append(item)
    return out


def list_feedback_unlocked(
    conn: sqlite3.Connection, engagement_id: str
) -> list[dict[str, Any]]:
    """list_feedback for callers already holding _lock (it is not reentrant)."""
    rows = conn.execute(
        "SELECT id, rating, comment, created_at FROM feedback"
        " WHERE engagement_id = ? ORDER BY created_at",
        (engagement_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def set_engagement_status(
    engagement_id: str,
    status: str,
    *,
    report_md: str | None = None,
    error: str | None = None,
) -> None:
    completed_at = time.time() if status in ("completed", "failed") else None
    with _lock:
        conn = connect()
        conn.execute(
            "UPDATE engagements SET status = ?,"
            " report_md = COALESCE(?, report_md),"
            " error = COALESCE(?, error),"
            " completed_at = COALESCE(?, completed_at)"
            " WHERE id = ?",
            (status, report_md, error, completed_at, engagement_id),
        )
        conn.commit()


# --- events -----------------------------------------------------------------

# --- lessons (the reflection / learning loop) -------------------------------


def add_lesson(text: str, engagement_id: str | None = None) -> bool:
    """Store a durable process lesson. Returns False if it already exists."""
    text = text.strip()
    if not text:
        return False
    with _lock:
        conn = connect()
        try:
            conn.execute(
                "INSERT INTO lessons (text, engagement_id, created_at) VALUES (?,?,?)",
                (text, engagement_id, time.time()),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # duplicate — already learned


def list_lessons(limit: int = 40) -> list[dict[str, Any]]:
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT id, text, created_at FROM lessons"
                " ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


def delete_lesson(lesson_id: int) -> None:
    with _lock:
        conn = connect()
        conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        conn.commit()


# --- golden cases + evals (the benchmark / "train with answers" loop) --------


def create_case(client_id: str, title: str, prompt: str, rubric: str) -> str:
    case_id = f"case_{uuid.uuid4().hex}"
    with _lock:
        conn = connect()
        conn.execute(
            "INSERT INTO cases (id, client_id, title, prompt, rubric, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (case_id, client_id, title, prompt, rubric, time.time()),
        )
        conn.commit()
    return case_id


def get_case(case_id: str) -> dict[str, Any] | None:
    with _lock:
        row = (
            connect().execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        )
    return dict(row) if row else None


def list_cases(client_id: str) -> list[dict[str, Any]]:
    """Cases with their latest completed score and total eval count."""
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT c.id, c.title, c.created_at,"
                " (SELECT e.score FROM evals e"
                "  WHERE e.case_id = c.id AND e.status = 'completed'"
                "  ORDER BY e.created_at DESC LIMIT 1) AS latest_score,"
                " (SELECT COUNT(*) FROM evals e WHERE e.case_id = c.id) AS eval_count"
                " FROM cases c WHERE c.client_id = ? ORDER BY c.created_at DESC",
                (client_id,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


def delete_case(case_id: str, client_id: str) -> None:
    with _lock:
        conn = connect()
        conn.execute("DELETE FROM evals WHERE case_id = ?", (case_id,))
        conn.execute(
            "DELETE FROM cases WHERE id = ? AND client_id = ?", (case_id, client_id)
        )
        conn.commit()


def create_eval(case_id: str, engagement_id: str) -> str:
    eval_id = f"eval_{uuid.uuid4().hex}"
    with _lock:
        conn = connect()
        conn.execute(
            "INSERT INTO evals (id, case_id, engagement_id, status, created_at)"
            " VALUES (?,?,?, 'running', ?)",
            (eval_id, case_id, engagement_id, time.time()),
        )
        conn.commit()
    return eval_id


def complete_eval(
    eval_id: str,
    *,
    status: str,
    score: int | None = None,
    detail: str | None = None,
) -> None:
    with _lock:
        conn = connect()
        conn.execute(
            "UPDATE evals SET status = ?, score = ?, detail = ?, completed_at = ?"
            " WHERE id = ?",
            (status, score, detail, time.time(), eval_id),
        )
        conn.commit()


def list_evals(case_id: str) -> list[dict[str, Any]]:
    """Eval history for one case, oldest first — so the score trend reads
    left-to-right as the agent learns."""
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT id, engagement_id, status, score, detail,"
                " created_at, completed_at"
                " FROM evals WHERE case_id = ? ORDER BY created_at",
                (case_id,),
            )
            .fetchall()
        )
    return [dict(r) for r in rows]


def append_event(engagement_id: str, event_type: str, payload: dict[str, Any]) -> int:
    with _lock:
        conn = connect()
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM events"
            " WHERE engagement_id = ?",
            (engagement_id,),
        ).fetchone()
        seq = int(row["next"])
        conn.execute(
            "INSERT INTO events (engagement_id, seq, type, payload, created_at)"
            " VALUES (?,?,?,?,?)",
            (engagement_id, seq, event_type, json.dumps(payload), time.time()),
        )
        conn.commit()
    return seq


def list_events(engagement_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
    with _lock:
        rows = (
            connect()
            .execute(
                "SELECT seq, type, payload, created_at FROM events"
                " WHERE engagement_id = ? AND seq > ? ORDER BY seq",
                (engagement_id, after_seq),
            )
            .fetchall()
        )
    return [
        {
            "seq": r["seq"],
            "type": r["type"],
            "payload": json.loads(r["payload"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
