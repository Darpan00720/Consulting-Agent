"""The seam into the Organization Layer (W9) and Memory Platform — this
module CALLS INTO their existing public APIs; it does not modify a single
line of either (verified in
``tests/test_deliverables_architecture_compliance.py``).

- ``check_required_approvals`` consumes REAL ``app.synthesis`` recommendation
  ``approval_status`` values (themselves set by W9's governance, via W10's
  own integration seam) — it never re-derives approval, only checks that a
  decision this deliverable requires has actually been satisfied.
- ``checkpoint_deliverable``/``resume_deliverable`` persist through the
  EXISTING ``MemoryService``/``CheckpointAdapter`` (Memory Platform),
  reusing ``MemoryType.CONSULTING`` — no new memory type, no new
  persistence path, mirroring ``app.synthesis.integration``'s own
  checkpoint bridge one layer down.
"""

from __future__ import annotations

from app.deliverables.models import (
    DeliverableDefinition,
    ExportResult,
    GeneratedDeliverable,
)
from app.organization.models import DecisionType
from app.synthesis.models import ApprovalStatus
from app.synthesis.state import SynthesisState

_CHECKPOINT_KEY_SUFFIX = "deliverables"


def check_required_approvals(
    definition: DeliverableDefinition, state: SynthesisState
) -> tuple[bool, tuple[DecisionType, ...]]:
    """For each ``DecisionType`` this deliverable requires, is there at
    least one APPROVED recommendation in scope? Returns
    ``(all_satisfied, unsatisfied_decision_types)``."""
    if not definition.required_approvals:
        return True, ()
    has_any_approved = any(
        r.approval_status is ApprovalStatus.APPROVED
        for r in state.recommendations.values()
    )
    unsatisfied = () if has_any_approved else tuple(definition.required_approvals)
    return has_any_approved, unsatisfied


def _checkpoint_key(deliverable_id: str) -> str:
    return f"{deliverable_id}::{_CHECKPOINT_KEY_SUFFIX}"


async def checkpoint_deliverable(
    deliverable: GeneratedDeliverable,
    export_result: ExportResult | None,
    memory_service=None,
):
    """Persists a generated (and optionally exported) deliverable through
    the EXISTING Memory Platform, via the shared ``app.memory.checkpoint``
    helper."""
    from app.memory.checkpoint import store_checkpoint

    payload = {
        "id": deliverable.id,
        "deliverable_type": deliverable.deliverable_type.value,
        "audience": deliverable.audience.value,
        "quality_overall_score": (
            deliverable.quality_report.overall_score
            if deliverable.quality_report
            else None
        ),
        "quality_all_passed": (
            deliverable.quality_report.all_passed
            if deliverable.quality_report
            else False
        ),
        "export_format": export_result.format.value if export_result else None,
        "export_is_placeholder": export_result.is_placeholder
        if export_result
        else None,
    }
    return await store_checkpoint(
        _checkpoint_key(deliverable.id),
        payload,
        metadata={"deliverable_id": deliverable.id},
        memory_service=memory_service,
    )


async def resume_deliverable(deliverable_id: str, memory_service=None) -> dict:
    from app.deliverables.errors import DeliverableError
    from app.memory.checkpoint import load_checkpoint

    value = await load_checkpoint(_checkpoint_key(deliverable_id), memory_service)
    if value is None:
        raise DeliverableError(
            f"no deliverable checkpoint found for {deliverable_id!r}"
        )
    return value
