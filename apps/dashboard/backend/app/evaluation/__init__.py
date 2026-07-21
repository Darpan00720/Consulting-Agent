"""Evaluation Platform — scoring, hallucination detection, and longitudinal
dashboards, approved for integration into ``app.pipeline`` under ADR-014
Phase 3.

The re-exports below are exactly the symbols ADR-014 §7.3 names as the
sanctioned integration surface — a future live-engagement adapter maps
``app.pipeline``'s real completed-engagement output into ``BenchmarkCase``/
``CaseReplayResult``-shaped data and calls ``evaluate_replay``/
``detect_hallucinations``; ``app.pipeline`` may separately read
``build_dashboard_snapshot`` output for longitudinal reporting. Calling
``app.evaluation.replay.replay_case`` (W7–W12's OWN benchmark-case replay,
a different concern from scoring a live engagement) is explicitly out of
scope per ADR-014 §7.3, and reaching into a submodule or a private symbol
is prohibited by ADR-014 §7.4.
"""

from __future__ import annotations

from app.evaluation.dashboard import build_dashboard_snapshot
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.hallucination import detect_hallucinations
from app.evaluation.models import BenchmarkCase, CaseReplayResult, EvaluationResult

__all__ = [
    "BenchmarkCase",
    "CaseReplayResult",
    "EvaluationResult",
    "evaluate_replay",
    "detect_hallucinations",
    "build_dashboard_snapshot",
]
