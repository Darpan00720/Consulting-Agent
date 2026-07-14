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
    created_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_engagements_client ON engagements(client_id, created_at);
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
        _conn.commit()
    return _conn


def reset_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


# --- engagements ------------------------------------------------------------

def create_engagement(client_id: str, case_prompt: str) -> str:
    engagement_id = f"eng_{uuid.uuid4().hex}"
    with _lock:
        conn = connect()
        conn.execute(
            "INSERT INTO engagements (id, client_id, case_prompt, status, created_at)"
            " VALUES (?,?,?, 'queued', ?)",
            (engagement_id, client_id, case_prompt, time.time()),
        )
        conn.commit()
    return engagement_id


def engagements_today(client_id: str) -> int:
    day_start = time.time() - 86400
    with _lock:
        row = connect().execute(
            "SELECT COUNT(*) AS n FROM engagements WHERE client_id = ? AND created_at > ?",
            (client_id, day_start),
        ).fetchone()
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
            (review_verdict, challenge_verdict, 1 if review_ready else 0, engagement_id),
        )
        conn.commit()


def get_engagement(engagement_id: str) -> dict[str, Any] | None:
    with _lock:
        row = connect().execute(
            "SELECT * FROM engagements WHERE id = ?", (engagement_id,)
        ).fetchone()
    return dict(row) if row else None


def list_engagements(client_id: str) -> list[dict[str, Any]]:
    with _lock:
        rows = connect().execute(
            "SELECT id, case_prompt, status, created_at, completed_at"
            " FROM engagements WHERE client_id = ? ORDER BY created_at DESC",
            (client_id,),
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
        rows = connect().execute(
            "SELECT id, text, created_at FROM lessons ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
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
        row = connect().execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    return dict(row) if row else None


def list_cases(client_id: str) -> list[dict[str, Any]]:
    """Cases with their latest completed score and total eval count."""
    with _lock:
        rows = connect().execute(
            "SELECT c.id, c.title, c.created_at,"
            " (SELECT e.score FROM evals e WHERE e.case_id = c.id AND e.status = 'completed'"
            "  ORDER BY e.created_at DESC LIMIT 1) AS latest_score,"
            " (SELECT COUNT(*) FROM evals e WHERE e.case_id = c.id) AS eval_count"
            " FROM cases c WHERE c.client_id = ? ORDER BY c.created_at DESC",
            (client_id,),
        ).fetchall()
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
        rows = connect().execute(
            "SELECT id, engagement_id, status, score, detail, created_at, completed_at"
            " FROM evals WHERE case_id = ? ORDER BY created_at",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def append_event(engagement_id: str, event_type: str, payload: dict[str, Any]) -> int:
    with _lock:
        conn = connect()
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM events WHERE engagement_id = ?",
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
        rows = connect().execute(
            "SELECT seq, type, payload, created_at FROM events"
            " WHERE engagement_id = ? AND seq > ? ORDER BY seq",
            (engagement_id, after_seq),
        ).fetchall()
    return [
        {
            "seq": r["seq"],
            "type": r["type"],
            "payload": json.loads(r["payload"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
