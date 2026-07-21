"""Tests for the AI Evaluation model: injectable providers, structural
separation from consulting output, and graceful failure handling."""

from __future__ import annotations

import asyncio
import inspect

from app.evaluation import ai_evaluation
from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.replay import replay_case


def _run(coro):
    return asyncio.run(coro)


def _case_and_replay():
    case = all_benchmark_cases()[0]
    return case, replay_case(case)


def test_injected_provider_produces_a_valid_ai_evaluation():
    case, replay = _case_and_replay()

    async def fake_provider(c, r):
        return {
            "scores": {"traceability": 0.9},
            "comments": ["solid"],
            "strengths": ["clear recommendation"],
            "weaknesses": [],
            "improvement_suggestions": [],
            "confidence": 0.75,
        }

    result = _run(
        ai_evaluation.run_ai_evaluation(
            case, replay, provider=fake_provider, provider_name="fake"
        )
    )
    assert result.provider == "fake"
    assert result.scores == {"traceability": 0.9}
    assert result.confidence == 0.75


def test_provider_returning_out_of_range_score_fails_gracefully():
    case, replay = _case_and_replay()

    async def bad_provider(c, r):
        return {"scores": {"traceability": 5.0}, "confidence": 0.5}

    result = _run(
        ai_evaluation.run_ai_evaluation(
            case, replay, provider=bad_provider, provider_name="bad"
        )
    )
    assert result.confidence == 0.0
    assert "out-of-range" in result.comments[0] or "failed" in result.comments[0]


def test_crashing_provider_fails_gracefully_never_raises():
    case, replay = _case_and_replay()

    async def crashing_provider(c, r):
        raise RuntimeError("provider unreachable")

    result = _run(
        ai_evaluation.run_ai_evaluation(
            case, replay, provider=crashing_provider, provider_name="crash"
        )
    )
    assert result.confidence == 0.0
    assert "provider unreachable" in result.comments[0]


def test_claude_ai_evaluator_lazily_imports_pipeline_providers():
    source = inspect.getsource(ai_evaluation.claude_ai_evaluator)
    assert "from app.pipeline import providers" in source


def test_ai_evaluation_module_never_imports_consulting_mutators():
    source = inspect.getsource(ai_evaluation)
    for forbidden in (
        "app.consulting.tracking",
        "app.knowledge.execution",
        "app.organization.governance",
        "app.synthesis.tracking",
        "app.deliverables.generator",
    ):
        assert forbidden not in source
