"""AI Evaluation (requester's "AI Evaluation" section): multiple evaluation
providers, each returning scores/comments/strengths/weaknesses/improvement
suggestions/confidence. **Structurally separate from consulting output** —
this module never imports a mutator from ``app.consulting``/
``app.knowledge``/``app.organization``/``app.synthesis``/``app.deliverables``;
an ``AIEvaluation`` is a read-only judgment ABOUT a replay, never fed back
into any of those five layers' state.

**One real evaluator, no new dependency.** Wired to the EXISTING
``app.pipeline.providers.call_with_failover`` — the same real, already-
available infra ``app.agents.builtin.ClaudeAgent`` already uses (ADR-012) —
rather than adding a new LLM client. A caller who wants a fully
deterministic evaluation (tests, replay-only environments) injects a
different ``AIEvaluationProvider`` instead; this module does not care which
one runs, the same "honest placeholder + injectable client" pattern already
established for Graphify/AgentDB/PowerPoint-Word-PDF in earlier phases.
"""

from __future__ import annotations

import json
from typing import Protocol

from .errors import EvaluationError
from .models import AIEvaluation, BenchmarkCase, CaseReplayResult, new_ai_evaluation_id


class AIEvaluationProvider(Protocol):
    """One evaluation provider's contract — any async callable matching
    this signature (a live LLM call, a fixture, a mock) can serve as a
    provider; there is no class hierarchy to subclass."""

    async def __call__(self, case: BenchmarkCase, replay: CaseReplayResult) -> dict: ...


def _prompt_for(case: BenchmarkCase, replay: CaseReplayResult) -> tuple[str, str]:
    system = (
        "You are a management-consulting quality evaluator. Score the "
        "replayed engagement below against the case's ground truth. "
        'Respond with ONLY a JSON object: {"scores": {"<metric>": <0-1 '
        'float>, ...}, "comments": [...], "strengths": [...], '
        '"weaknesses": [...], "improvement_suggestions": [...], '
        '"confidence": <0-1 float>}.'
    )
    user = (
        f"Case: {case.title}\n"
        f"Ground truth: {case.ground_truth}\n"
        f"Expected recommendations: {list(case.expected_recommendations)}\n"
        f"Replayed recommendations: {list(replay.recommendations)}\n"
        f"Replayed quality metrics: {replay.quality_metrics}\n"
    )
    return system, user


async def claude_ai_evaluator(case: BenchmarkCase, replay: CaseReplayResult) -> dict:
    """The one REAL provider — calls the existing Provider Router
    (``app.pipeline.providers.call_with_failover``), lazily imported the
    same way ``app.agents.builtin.ClaudeAgent`` already does, so this
    module stays importable standalone."""
    from app.pipeline import providers

    system, user = _prompt_for(case, replay)
    text = await providers.call_with_failover(
        agent_name=f"evaluation:{case.case_id}:ai-evaluator",
        system=system,
        user=user,
        max_tokens=512,
    )
    return json.loads(text)


def _validated_ai_evaluation(raw: dict, provider_name: str) -> AIEvaluation:
    scores = dict(raw.get("scores", {}))
    for name, value in scores.items():
        if not (0.0 <= value <= 1.0):
            raise EvaluationError(
                f"AI evaluator returned out-of-range score for {name!r}: {value}"
            )
    confidence = float(raw.get("confidence", 0.0))
    if not (0.0 <= confidence <= 1.0):
        raise EvaluationError(
            f"AI evaluator returned out-of-range confidence: {confidence}"
        )
    return AIEvaluation(
        id=new_ai_evaluation_id(),
        provider=provider_name,
        scores=scores,
        comments=tuple(raw.get("comments", ())),
        strengths=tuple(raw.get("strengths", ())),
        weaknesses=tuple(raw.get("weaknesses", ())),
        improvement_suggestions=tuple(raw.get("improvement_suggestions", ())),
        confidence=confidence,
    )


async def run_ai_evaluation(
    case: BenchmarkCase,
    replay: CaseReplayResult,
    *,
    provider: AIEvaluationProvider = claude_ai_evaluator,
    provider_name: str = "claude",
) -> AIEvaluation:
    """Never raises: a provider failure (unreachable, malformed JSON,
    out-of-range score) produces an ``AIEvaluation`` with confidence 0.0 and
    the error in ``comments`` — the same "a poor outcome is normal, not
    exceptional" discipline every evaluation check in this platform uses,
    applied to provider availability instead of consulting content."""
    try:
        raw = await provider(case, replay)
        return _validated_ai_evaluation(raw, provider_name)
    except Exception as exc:  # noqa: BLE001 — provider failure is a reportable outcome
        return AIEvaluation(
            id=new_ai_evaluation_id(),
            provider=provider_name,
            scores={},
            comments=(f"AI evaluation failed: {type(exc).__name__}: {exc}",),
            strengths=(),
            weaknesses=(),
            improvement_suggestions=(),
            confidence=0.0,
        )
