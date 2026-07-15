"""Operator status report — "is it being used, is it any good, is it broken?"

Run it against a live deployment:

    docker exec dashboard-backend-1 /app/.venv/bin/python -m app.ops
    docker exec dashboard-backend-1 /app/.venv/bin/python -m app.ops --hours 24
    docker exec dashboard-backend-1 /app/.venv/bin/python -m app.ops --json

It reads two sources that are already there and correlates them by
``engagement_id``:

* the **domain database** — what happened to each engagement (status, gate
  verdicts, whether a recommendation actually shipped);
* the **telemetry traces** — how long each phase took, what retried, what failed.

This is a **pull** tool, not alerting. Nothing pushes to you. For a real
deployment, run it on a schedule and alert on the WATCH lines below; the
thresholds encode what actually matters:

* a blocked engagement is NOT a failure — it is the platform refusing to ship
  analysis that did not survive its own governance. Some blocking is healthy;
  *zero* blocking over many runs is suspicious (a gate that never fails is a
  gate that is not working).
* pauses are NOT failures either — a rate-limited run resumes from its
  checkpoint. Alert on the pause *rate*, not on pauses.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from app import config


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def collect(hours: float | None = None) -> dict[str, Any]:
    """Gather the operator picture. ``hours`` limits to a recent window."""
    conn = _db()
    where, params = "", ()
    if hours is not None:
        where = " WHERE created_at > ?"
        params = (time.time() - hours * 3600,)

    rows = conn.execute(
        f"SELECT id, client_id, status, error, review_verdict, challenge_verdict,"
        f" review_ready, created_at, completed_at FROM engagements{where}",
        params,
    ).fetchall()

    status = Counter(r["status"] for r in rows)
    completed = [r for r in rows if r["status"] == "completed"]
    shipped = [r for r in completed if r["review_ready"] == 1]
    blocked = [r for r in completed if r["review_ready"] == 0]
    failed = [r for r in rows if r["status"] == "failed"]

    durations = [
        r["completed_at"] - r["created_at"]
        for r in completed
        if r["completed_at"] and r["created_at"]
    ]

    # Pauses live in the event log, not on the engagement row.
    ids = {r["id"] for r in rows}
    pauses = 0
    if ids:
        marks = ",".join("?" * len(ids))
        pauses = conn.execute(
            f"SELECT COUNT(*) FROM events WHERE type='engagement_paused'"
            f" AND engagement_id IN ({marks})",
            tuple(ids),
        ).fetchone()[0]

    return {
        "window_hours": hours,
        "engagements": len(rows),
        "distinct_users": len({r["client_id"] for r in rows}),
        "status": dict(status),
        "shipped_recommendation": len(shipped),
        "blocked_by_governance": len(blocked),
        "failed": len(failed),
        "paused_events": pauses,
        "median_minutes": (
            round(sorted(durations)[len(durations) // 2] / 60, 1) if durations else None
        ),
        "review_verdicts": dict(Counter(r["review_verdict"] for r in completed)),
        "challenge_verdicts": dict(Counter(r["challenge_verdict"] for r in completed)),
        "errors": dict(Counter((r["error"] or "")[:90] for r in failed)),
        "slowest_phases_ms": _slowest_phases(ids),
    }


def _slowest_phases(ids: set[str]) -> dict[str, float]:
    """Median duration per phase, from telemetry traces. {} if unavailable."""
    root = Path(config.TELEMETRY_DIR or "")
    if not root.is_dir():
        return {}
    by_phase: dict[str, list[float]] = {}
    for eid in ids:
        trace = root / f"{eid}.jsonl"
        if not trace.exists():
            continue
        for line in trace.read_text().splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("status") == "finished" and e.get("duration_ms"):
                by_phase.setdefault(e["phase"], []).append(e["duration_ms"])
    medians = {p: round(sorted(v)[len(v) // 2]) for p, v in by_phase.items() if v}
    return dict(sorted(medians.items(), key=lambda kv: -kv[1])[:5])


def _watch(s: dict[str, Any]) -> list[str]:
    """Interpretation — the lines an operator should act on."""
    out: list[str] = []
    n = s["engagements"]
    if n == 0:
        return ["no engagements in this window — nothing to judge"]

    if s["failed"]:
        out.append(
            f"🔴 {s['failed']}/{n} FAILED — these are real bugs or outages. "
            f"See errors below; rate limits should never appear here (they pause)."
        )
    if s["status"].get("paused"):
        out.append(
            f"🟠 {s['status']['paused']} stuck in 'paused' — if this does not "
            f"clear, auto-resume is not firing (check STRATAGENT_AUTO_RESUME)."
        )
    if s["status"].get("running"):
        out.append(f"⏳ {s['status']['running']} still running")

    blocked, shipped = s["blocked_by_governance"], s["shipped_recommendation"]
    done = blocked + shipped
    if done:
        rate = blocked / done
        if rate > 0.5:
            out.append(
                f"🟠 {blocked}/{done} blocked by governance — the analysis is "
                f"failing its own gates more often than it passes. Prompt/model "
                f"quality problem, not a crash."
            )
        elif blocked == 0 and done >= 10:
            out.append(
                f"🟡 0/{done} blocked — a gate that NEVER fails may not be "
                f"working. Verify the challenger is actually adversarial."
            )
        else:
            out.append(
                f"🟢 {shipped}/{done} shipped a recommendation, {blocked} "
                f"correctly withheld — governance is doing its job."
            )
    if s["paused_events"]:
        out.append(
            f"ℹ️  {s['paused_events']} rate-limit pauses (runs resumed; not "
            f"failures). Sustained growth here = add provider keys."
        )
    return out


def render(s: dict[str, Any]) -> str:
    w = f"last {s['window_hours']:g}h" if s["window_hours"] else "all time"
    L = [f"StratAgent — operator report ({w})", "=" * 46, ""]
    L.append(f"  {s['engagements']} engagements from {s['distinct_users']} users")
    if s["median_minutes"]:
        L.append(f"  median completion: {s['median_minutes']} min")
    L.append(f"  status: {s['status'] or '—'}")
    L.append("")
    L.append("WATCH")
    for line in _watch(s):
        L.append(f"  {line}")
    if s["errors"]:
        L.append("")
        L.append("ERRORS")
        for msg, n in s["errors"].items():
            L.append(f"  {n}x {msg}")
    if s["review_verdicts"]:
        L.append("")
        L.append("GOVERNANCE")
        L.append(f"  reviewer:   {s['review_verdicts']}")
        L.append(f"  challenger: {s['challenge_verdicts']}")
    if s["slowest_phases_ms"]:
        L.append("")
        L.append("SLOWEST PHASES (median ms, from telemetry)")
        for p, ms in s["slowest_phases_ms"].items():
            L.append(f"  {p:<16} {ms / 1000:>7.1f}s")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="StratAgent operator status report.")
    ap.add_argument("--hours", type=float, default=None, help="limit to a window")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    summary = collect(args.hours)
    print(json.dumps(summary, indent=2) if args.json else render(summary))
    # Non-zero exit when something genuinely needs a human — usable in cron.
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
