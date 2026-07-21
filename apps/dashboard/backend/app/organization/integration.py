"""The ONE seam into the Consulting Workflow Engine (W7) and Knowledge
Library (W8) — this module CALLS INTO their existing public APIs; it does
not modify a single line of either (verified in
``tests/test_org_architecture_compliance.py``).

Two entry points, mirroring the requester's own framing:

- ``request_work_from_role`` is how "the Workflow Engine requests work from
  organizational roles" — it logs a ``TASK``-kind ``CollaborationRequest``
  from the engine to the assigned role, through ``CollaborationLog`` (never
  a new orchestration channel).
- ``execute_role_framework`` is how "roles invoke frameworks through the
  existing Knowledge Library" — it validates the role is actually eligible
  for this engagement type and framework (a genuine organizational rule),
  then delegates the ENTIRE execution to the unmodified
  ``app.knowledge.execution.execute_framework`` /
  ``app.knowledge.integration.apply_framework_result`` — this module never
  reimplements framework execution or engagement mutation.
"""

from __future__ import annotations

from app.consulting.state import EngagementState
from app.knowledge.execution import execute_framework
from app.knowledge.integration import apply_framework_result
from app.knowledge.models import FrameworkExecutionRequest, FrameworkExecutionResult
from app.knowledge.registry import FrameworkRegistry
from app.organization.collaboration import CollaborationLog
from app.organization.errors import RoleNotEligibleError
from app.organization.models import CollaborationRequest, RequestKind, RoleDefinition

_WORKFLOW_ENGINE_SENDER = "workflow_engine"


def request_work_from_role(
    log: CollaborationLog,
    role: RoleDefinition,
    subject: str,
    content: str,
    *,
    kind: RequestKind = RequestKind.TASK,
) -> CollaborationRequest:
    """The Workflow Engine requesting work FROM a role — logged, traceable,
    never a direct call into the role's own execution (there is no such
    call; a role's "work" is whichever downstream function — here,
    ``execute_role_framework`` — actually gets invoked once the request is
    acknowledged)."""
    return log.create_request(
        kind=kind,
        from_role=_WORKFLOW_ENGINE_SENDER,
        to_role=role.id,
        subject=subject,
        content=content,
    )


def execute_role_framework(
    state: EngagementState,
    role: RoleDefinition,
    framework_registry: FrameworkRegistry,
    framework_id: str,
    request: FrameworkExecutionRequest,
) -> FrameworkExecutionResult:
    """Validate the role is organizationally eligible (supports this
    engagement's category AND this specific framework), then delegate
    EVERYTHING else — readiness gating, confidence derivation, structured
    output, feeding the engagement — to the unmodified Knowledge Library."""
    if state.category not in role.supported_engagement_types:
        raise RoleNotEligibleError(
            f"{role.id!r} does not support engagement type {state.category.value!r}"
        )
    if framework_id not in role.supported_frameworks:
        raise RoleNotEligibleError(
            f"{role.id!r} does not support framework {framework_id!r}"
        )

    framework = framework_registry.get(framework_id)
    result = execute_framework(framework, request)
    apply_framework_result(state, result)
    return result
