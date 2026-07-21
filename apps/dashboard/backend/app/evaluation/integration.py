"""The seam into the Memory Platform (requester's "Integration" section)
— this module CALLS INTO the EXISTING ``MemoryService``/``CheckpointAdapter``,
reusing ``MemoryType.CONSULTING`` (no new memory type, no new persistence
path), the same convention every prior layer's own ``integration.py``
already established (W7's engine checkpoint, W10's
``checkpoint_synthesis``, W11's ``checkpoint_deliverable``).

**Every other named integration point is consume-only, by construction, not
by convention here.** The Workflow Engine (W7), Knowledge Library (W8),
Organization Layer (W9), Synthesis Engine (W10), and Deliverables Engine
(W11) are consumed through ``app.evaluation.replay.replay_case`` — the ONE
place in this package that imports their execution functions
(``ConsultingEngine.start_engagement``, ``execute_framework``,
``allocate_team``, ``create_finding``/``create_recommendation``,
``generate_deliverable``) — and every one of those calls is a read/create
against the CALLER's own fresh ``EngagementState``/``SynthesisState``,
never a mutation of a pre-existing engagement the rest of the platform is
still using. The Tool Platform is reached only transitively, through
whatever the five consulting layers themselves already call — this package
adds no direct Tool Platform dependency of its own.
"""

from __future__ import annotations

import dataclasses

from .models import EvaluationMetric, EvaluationResult, MetricScore

_CHECKPOINT_KEY_SUFFIX = "evaluation"


def _checkpoint_key(case_id: str) -> str:
    return f"{case_id}::{_CHECKPOINT_KEY_SUFFIX}::latest"


def serialize_evaluation_result(result: EvaluationResult) -> dict:
    """``dataclasses.asdict()`` handles the easy direction — every field is
    a primitive, a tuple, or a ``StrEnum`` member (which serializes as a
    plain string automatically), the same fact ``app.consulting.serialization``
    already relies on."""
    return dataclasses.asdict(result)


def deserialize_evaluation_result(data: dict) -> EvaluationResult:
    """The hard direction, hand-written: JSON has no way to know a dict
    should become a ``MetricScore`` or that a string should become an
    ``EvaluationMetric`` member."""
    metric_scores = tuple(
        MetricScore(
            metric=EvaluationMetric(m["metric"]),
            score=m["score"],
            confidence=m["confidence"],
            weight=m["weight"],
            reason=m["reason"],
            supporting_artifacts=tuple(m["supporting_artifacts"]),
        )
        for m in data["metric_scores"]
    )
    return EvaluationResult(
        id=data["id"],
        case_id=data["case_id"],
        replay_id=data["replay_id"],
        metric_scores=metric_scores,
        overall_score=data["overall_score"],
        evaluation_version=data["evaluation_version"],
        evaluated_at=data["evaluated_at"],
    )


async def checkpoint_evaluation(result: EvaluationResult, memory_service=None):
    """Persists an ``EvaluationResult`` through the EXISTING Memory
    Platform, via the shared ``app.memory.checkpoint`` helper, under
    ``MemoryType.CONSULTING`` — no new memory type."""
    from app.memory.checkpoint import store_checkpoint

    payload = serialize_evaluation_result(result)
    return await store_checkpoint(
        _checkpoint_key(result.case_id),
        payload,
        trace_id=result.replay_id,
        metadata={"case_id": result.case_id, "replay_id": result.replay_id},
        memory_service=memory_service,
    )


async def resume_evaluation(case_id: str, memory_service=None) -> EvaluationResult:
    from app.memory.checkpoint import load_checkpoint

    from .errors import EvaluationError

    value = await load_checkpoint(_checkpoint_key(case_id), memory_service)
    if value is None:
        raise EvaluationError(f"no evaluation checkpoint found for case {case_id!r}")
    return deserialize_evaluation_result(value)
