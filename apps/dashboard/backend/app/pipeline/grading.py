"""Golden-case grading — the honest version of "training with case answers".

The model's weights never change (API calls are stateless inference). What DOES
compound is this loop:

    user supplies {case, official model answer}   →  stored as a golden case
    agent runs the case                            →  full engagement pipeline
    a grader compares report vs the gold answer    →  score 0-100 + missed items
    missed items are distilled into process rules  →  anti-leakage lessons store
    lessons are injected into every future run     →  same class of error avoided

Scores per case over time are the proof the loop works.
"""

from __future__ import annotations

import re

from app import db
from app.pipeline.claude import call_agent, friendly_error
from app.pipeline.engine import (
    REFLECTION_SYSTEM,
    CallAgent,
    _parse_lessons,
    run_engagement,
)

# Cheap model for grading and lesson distillation — quality of judgement matters
# less than the engagement itself, and this keeps a full eval ~the cost of a run.
GRADER_MODEL = "claude-haiku-4-5"

GRADER_SYSTEM = """You are an MBB (McKinsey/Bain/BCG) partner grading an
AI-generated consulting report against the OFFICIAL MODEL ANSWER for the same
case. Be strict — this grade drives an improvement loop, and inflated scores
hide errors.

Output EXACTLY this format and nothing else:

SCORE: <integer 0-100>
GOT: <one rubric element the report covered well>          (zero or more lines)
MISSED: <one rubric element the report missed, got materially wrong, or left
underdeveloped — be specific about WHAT is missing>        (zero or more lines)

Scoring guide:
- 60 pts — rubric coverage: does the report hit the elements of the model
  answer (the factors "a good answer would include")?
- 20 pts — structure: answer-first (Pyramid Principle), MECE analysis, clear
  recommendation with next steps and rejected alternatives.
- 20 pts — evidence discipline: numbers traceable to labeled assumptions,
  no invented facts, calibrated confidence.
A report missing a load-bearing element of the model answer cannot score
above 75. A report that contradicts itself cannot score above 60."""


def _parse_grade(text: str) -> tuple[int | None, list[str]]:
    """Extract (score, missed items) from the grader's output."""
    score: int | None = None
    m = re.search(r"SCORE:\s*(\d{1,3})", text, re.IGNORECASE)
    if m:
        score = max(0, min(100, int(m.group(1))))
    missed = [
        line.split(":", 1)[1].strip()[:500]
        for line in text.splitlines()
        if line.strip().upper().startswith("MISSED:") and line.split(":", 1)[1].strip()
    ]
    return score, missed


async def run_case_eval(
    eval_id: str,
    engagement_id: str,
    case_prompt: str,
    rubric: str,
    *,
    call: CallAgent = call_agent,
    api_key: str | None = None,
    model: str | None = None,
) -> None:
    """Run one golden-case eval end to end. Never raises — outcome lands on the
    eval row (and the engagement row, via run_engagement's own handling)."""
    try:
        await run_engagement(
            engagement_id, case_prompt, call=call, api_key=api_key, model=model
        )
        engagement = db.get_engagement(engagement_id) or {}
        report = engagement.get("report_md") or ""
        if engagement.get("status") != "completed" or not report:
            db.complete_eval(
                eval_id,
                status="failed",
                detail=engagement.get("error") or "The engagement did not complete.",
            )
            return

        graded = await call(
            "grader",
            GRADER_SYSTEM,
            f"# Official model answer / grading rubric\n\n{rubric.strip()}"
            f"\n\n# The agent's report to grade\n\n{report.strip()}"
            "\n\nGrade the report against the model answer. SCORE/GOT/MISSED only.",
            api_key=api_key,
            model=GRADER_MODEL,
        )
        score, missed = _parse_grade(graded)
        db.complete_eval(eval_id, status="completed", score=score, detail=graded)
        await _emit_eval_event(engagement_id, score, missed)

        # The learning half: distil what the grader caught into durable process
        # rules. Same anti-leakage guard as the reflection loop — method only,
        # never case facts, so lessons transfer to unrelated engagements.
        if missed:
            reflection = await call(
                "reflector",
                REFLECTION_SYSTEM,
                "# Gaps a grader found comparing the report to the official"
                " model answer\n\n"
                + "\n".join(f"- {item}" for item in missed)
                + "\n\nExtract the durable process lessons (method only, no case "
                "facts). Output `LESSON: ...` lines, or NONE.",
                api_key=api_key,
                model=GRADER_MODEL,
            )
            for lesson in _parse_lessons(reflection):
                db.add_lesson(lesson, engagement_id)
    except Exception as exc:  # noqa: BLE001 — surface any failure on the eval row
        db.complete_eval(eval_id, status="failed", detail=friendly_error(exc))


async def _emit_eval_event(
    engagement_id: str, score: int | None, missed: list[str]
) -> None:
    """Best-effort: append the grade to the engagement's event stream."""
    try:
        from app.pipeline.engine import _emit

        await _emit(
            engagement_id,
            "eval_graded",
            {"score": score, "missed_count": len(missed)},
        )
    except Exception:  # noqa: BLE001 — grading outcome is already persisted
        pass
