"""Integration tests: the Evaluation Platform's Memory Platform checkpoint
seam, wired against the REAL MemoryService (same isolation fixture pattern
as test_synthesis_integration.py / test_deliverables_generator.py)."""

from __future__ import annotations

import asyncio

import pytest

from app import config, db
from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.errors import EvaluationError
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.integration import (
    checkpoint_evaluation,
    deserialize_evaluation_result,
    resume_evaluation,
    serialize_evaluation_result,
)
from app.evaluation.replay import replay_case


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "evaluation-test.db")
    db.reset_for_tests()


def _run(coro):
    return asyncio.run(coro)


def test_serialize_deserialize_roundtrip_preserves_content():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    result = evaluate_replay(case, replay)

    payload = serialize_evaluation_result(result)
    restored = deserialize_evaluation_result(payload)

    assert restored.id == result.id
    assert restored.case_id == result.case_id
    assert restored.overall_score == result.overall_score
    assert len(restored.metric_scores) == len(result.metric_scores)
    assert {m.metric for m in restored.metric_scores} == {
        m.metric for m in result.metric_scores
    }


def test_checkpoint_and_resume_round_trips_through_the_real_memory_platform():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    result = evaluate_replay(case, replay)

    checkpoint_result = _run(checkpoint_evaluation(result))
    assert checkpoint_result.success

    resumed = _run(resume_evaluation(case.case_id))
    assert resumed.case_id == result.case_id
    assert resumed.overall_score == pytest.approx(result.overall_score)
    assert len(resumed.metric_scores) == 16


def test_resume_without_a_prior_checkpoint_raises():
    with pytest.raises(EvaluationError):
        _run(resume_evaluation("never-checkpointed-case"))
