"""``ConsultingEngine`` — the orchestrator that runs one engagement through
the 10-stage methodology, gated by quality gates, on top of the EXISTING
platform.

**This is the integration point (deliverable 11), not a new infrastructure
layer.** Two platform capabilities are reused, never reimplemented:

- **Analysis execution** goes through the REAL Workflow Router + Dispatcher
  (``app.workflow.router.route`` / ``app.workflow.dispatcher.dispatch``),
  exactly the way any other caller reaches the governed ``consulting`` target
  — this engine does not call an agent directly, and does not duplicate the
  guardrail/fallback/timeout logic the Dispatcher already owns.
- **Checkpointing** goes through the REAL Memory Platform
  (``app.memory.service.MemoryService`` -> the real ``CheckpointAdapter``,
  which wraps ``app.db``'s existing event log) — no new persistence layer,
  no new database table.

Both are late (lazy, inside methods) imports, matching the existing
discipline every platform layer already uses to avoid a top-level dependency
on a layer it only calls into at request time (see ``app.workflow.targets``'
module docstring for the precedent).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.consulting.artifacts import generate_artifact
from app.consulting.errors import UnknownEngagementError
from app.consulting.models import (
    ArtifactType,
    ConsultingStage,
    EngagementCategory,
    QualityGateResult,
)
from app.consulting.quality_gates import evaluate_stage_gates, stage_gates_pass
from app.consulting.registry import WorkflowRegistry, default_workflow_registry
from app.consulting.serialization import deserialize_state, serialize_state
from app.consulting.state import (
    EngagementState,
    EngagementStatus,
    StageHistoryEntry,
    StageOutcome,
)
from app.consulting.workflow import WorkflowDefinition

_CHECKPOINT_LATEST = "latest"


def _checkpoint_key(engagement_id: str, name: str) -> str:
    return f"{engagement_id}::checkpoint::{name}"


@dataclass
class ConsultingEngine:
    workflow_registry: WorkflowRegistry = field(
        default_factory=default_workflow_registry
    )
    memory_service: object | None = None  # app.memory.service.MemoryService, lazy-typed
    target_registry: dict | None = None  # dict[str, app.workflow.targets.Target]
    _states: dict[str, EngagementState] = field(default_factory=dict, repr=False)

    def _memory(self):
        if self.memory_service is not None:
            return self.memory_service
        from app.memory.service import default_service

        return default_service()

    def _targets(self) -> dict:
        if self.target_registry is not None:
            return self.target_registry
        from app.workflow.targets import default_registry

        return default_registry()

    # ---- Engagement lifecycle -------------------------------------------

    def resolve_workflow(
        self,
        category: EngagementCategory,
        workflow_id: str | None = None,
        version: str | None = None,
    ) -> WorkflowDefinition:
        wid = workflow_id or f"workflow.{category.value}"
        return self.workflow_registry.get(wid, version)

    def start_engagement(
        self,
        engagement_id: str,
        category: EngagementCategory,
        *,
        workflow_id: str | None = None,
        workflow_version: str | None = None,
        trace_id: str = "",
    ) -> EngagementState:
        workflow = self.resolve_workflow(category, workflow_id, workflow_version)
        first_stage = workflow.required_stages[0]
        state = EngagementState(
            engagement_id=engagement_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            category=category,
            trace_id=trace_id,
            status=EngagementStatus.IN_PROGRESS,
            current_stage=first_stage,
        )
        state.stage_history.append(
            StageHistoryEntry(stage=first_stage, entered_at=time.time())
        )
        self._states[engagement_id] = state
        return state

    def get_state(self, engagement_id: str) -> EngagementState:
        if engagement_id not in self._states:
            raise UnknownEngagementError(f"no engagement {engagement_id!r} loaded")
        return self._states[engagement_id]

    def advance_stage(self, engagement_id: str) -> tuple[QualityGateResult, ...]:
        """Evaluate the current stage's mandatory quality gates. Progression
        STOPS (current_stage unchanged, entry marked BLOCKED) if any mandatory
        gate fails — the concrete enforcement of "workflow progression must
        stop if mandatory quality gates fail." Never raises: a blocked gate
        is an ordinary, expected outcome, reported in the returned results."""
        state = self.get_state(engagement_id)
        workflow = self.resolve_workflow(
            state.category, state.workflow_id, state.workflow_version
        )
        assert state.current_stage is not None  # engagement already COMPLETED

        results = evaluate_stage_gates(
            state.current_stage, state, workflow.quality_gates
        )
        entry = state.stage_history[-1]
        entry.gate_results = results

        if not stage_gates_pass(state.current_stage, state, workflow.quality_gates):
            entry.outcome = StageOutcome.BLOCKED
            return results

        entry.outcome = StageOutcome.PASSED
        entry.exited_at = time.time()

        idx = workflow.required_stages.index(state.current_stage)
        if idx + 1 < len(workflow.required_stages):
            next_stage = workflow.required_stages[idx + 1]
            state.current_stage = next_stage
            state.stage_history.append(
                StageHistoryEntry(stage=next_stage, entered_at=time.time())
            )
        else:
            state.status = EngagementStatus.COMPLETED
            state.current_stage = None
            generate_artifact(state, ArtifactType.EXECUTIVE_SUMMARY)
        return results

    # ---- Analysis execution — delegates to the EXISTING platform stack ---

    async def execute_stage_analysis(self, engagement_id: str, work_text: str):
        """For the ANALYSIS_EXECUTION stage: routes through the real Workflow
        Router + Dispatcher, exactly as any other caller would, so the
        consulting guardrail (ADR-013 sec 6.4/8 — business consulting may
        ONLY reach the governed ``consulting`` target) applies here too. The
        engine never calls an agent or a target directly."""
        from app.workflow.dispatcher import dispatch
        from app.workflow.router import RoutingContext, Work, route

        state = self.get_state(engagement_id)
        ctx = RoutingContext(trace_id=state.trace_id)
        work = Work(text=work_text, skill="solve-case")
        registry = self._targets()
        decision = route(work, ctx, registry=registry)
        result = await dispatch(decision, registry, work)
        if result.output:
            state.analysis_findings.append(result.output)
        return result

    # ---- Pause / resume / checkpoint / rollback --------------------------

    def pause(self, engagement_id: str) -> EngagementState:
        state = self.get_state(engagement_id)
        state.status = EngagementStatus.PAUSED
        return state

    def resume_in_memory(self, engagement_id: str) -> EngagementState:
        """Resume an engagement still held in this process's ``_states``."""
        state = self.get_state(engagement_id)
        if state.status is EngagementStatus.PAUSED:
            state.status = EngagementStatus.IN_PROGRESS
        return state

    async def checkpoint(self, engagement_id: str):
        """Persist the full engagement state via the REAL Memory Platform.
        Writes under two names: the CURRENT stage (so ``rollback`` can target
        it specifically) and ``latest`` (so ``resume_from_checkpoint`` always
        finds the newest state without needing to know which stage it was
        in)."""
        from app.memory.checkpoint import store_checkpoint

        state = self.get_state(engagement_id)
        payload = serialize_state(state)
        stage_name = state.current_stage.value if state.current_stage else "completed"
        memory = self._memory()
        metadata = {"engagement_id": engagement_id}
        await store_checkpoint(
            _checkpoint_key(engagement_id, stage_name),
            payload,
            trace_id=state.trace_id,
            metadata=metadata,
            memory_service=memory,
        )
        return await store_checkpoint(
            _checkpoint_key(engagement_id, _CHECKPOINT_LATEST),
            payload,
            trace_id=state.trace_id,
            metadata=metadata,
            memory_service=memory,
        )

    async def resume_from_checkpoint(self, engagement_id: str) -> EngagementState:
        """Resume an engagement NOT currently held in memory (e.g. after a
        process restart) from its latest checkpoint."""
        from app.memory.checkpoint import load_checkpoint

        value = await load_checkpoint(
            _checkpoint_key(engagement_id, _CHECKPOINT_LATEST),
            memory_service=self._memory(),
        )
        if value is None:
            raise UnknownEngagementError(
                f"no checkpoint found for engagement {engagement_id!r}"
            )
        state = deserialize_state(value)
        state.status = EngagementStatus.IN_PROGRESS
        self._states[engagement_id] = state
        return state

    async def rollback(
        self, engagement_id: str, to_stage: ConsultingStage
    ) -> EngagementState:
        """Restore the engagement to the checkpoint taken while it was in
        ``to_stage`` — the version-history/rollback the requester's
        "Execution State" section named. Requires a prior ``checkpoint()``
        call while in that stage; otherwise reports ``UnknownEngagementError``
        (never silently fabricates a state)."""
        from app.memory.checkpoint import load_checkpoint

        value = await load_checkpoint(
            _checkpoint_key(engagement_id, to_stage.value),
            memory_service=self._memory(),
        )
        if value is None:
            raise UnknownEngagementError(
                f"no checkpoint for engagement {engagement_id!r} "
                f"at stage {to_stage.value!r}"
            )
        state = deserialize_state(value)
        state.status = EngagementStatus.IN_PROGRESS
        self._states[engagement_id] = state
        return state
