"""The ONE seam into the Consulting Workflow Engine (requester's
"Integration" section) — this module CALLS INTO ``app.consulting``'s
existing public API; it does not modify a single line of it (verified in
``tests/test_knowledge_architecture_compliance.py``).

Two entry points:

- ``select_frameworks_for_engagement`` builds a ``SelectionContext`` FROM a
  real ``EngagementState`` and delegates to ``selection.select_frameworks`` —
  the Workflow Engine's ``ProblemDefinition``/category become the selection
  inputs, never duplicated.
- ``apply_framework_result`` takes a completed ``FrameworkExecutionResult``
  and feeds it into the engagement through ``app.consulting.tracking``'s
  EXISTING mutators (``add_evidence``, ``state.analysis_findings``) — never a
  new persistence path, never a new orchestration layer.

**Structural enforcement of "framework execution never generates executive
recommendations":** this module has no function that calls
``app.consulting.tracking.create_recommendation``. A framework's analytical
``recommendations`` (e.g. "this force is a major threat") become EVIDENCE
content here, at most — turning that into an engagement-level
``Recommendation`` remains a separate, later, evidence-linked call a human or
agent makes explicitly, exactly like every other recommendation in this
platform.
"""

from __future__ import annotations

from app.consulting.models import Evidence, EvidenceQuality, EvidenceSourceType
from app.consulting.state import EngagementState
from app.consulting.tracking import add_evidence
from app.knowledge.models import (
    CompanySize,
    FrameworkExecutionResult,
    SelectionContext,
    SelectionResult,
)
from app.knowledge.registry import FrameworkRegistry
from app.knowledge.selection import select_frameworks


def select_frameworks_for_engagement(
    state: EngagementState,
    registry: FrameworkRegistry,
    *,
    industry: str = "all",
    available_data: tuple[str, ...] = (),
    available_evidence: tuple[str, ...] = (),
    company_size: CompanySize = CompanySize.MIDMARKET,
    workflow_stage: str = "",
) -> SelectionResult:
    """Build a ``SelectionContext`` from the engagement's OWN recorded state
    (category, problem objective, evidence already collected) rather than
    asking the caller to repeat it."""
    business_problem = state.problem.objective
    evidence_from_state = tuple(e.source for e in state.evidence.values())
    context = SelectionContext(
        engagement_type=state.category,
        industry=industry,
        business_problem=business_problem,
        available_data=available_data,
        available_evidence=(*evidence_from_state, *available_evidence),
        company_size=company_size,
        workflow_stage=workflow_stage
        or (state.current_stage.value if state.current_stage else ""),
        confidence=0.5,
    )
    return select_frameworks(context, registry)


_QUALITY_BY_CONFIDENCE = (
    (0.7, EvidenceQuality.HIGH),
    (0.4, EvidenceQuality.MEDIUM),
)


def _quality_for_confidence(confidence: float) -> EvidenceQuality:
    for threshold, quality in _QUALITY_BY_CONFIDENCE:
        if confidence >= threshold:
            return quality
    return EvidenceQuality.LOW


def apply_framework_result(
    state: EngagementState, result: FrameworkExecutionResult
) -> tuple[Evidence, ...]:
    """Feed a completed framework execution into the EXISTING engagement:
    each finding becomes real ``Evidence`` (via ``app.consulting.tracking``,
    unmodified) and ``state.analysis_findings`` — the same list
    ``ConsultingEngine.execute_stage_analysis`` already appends to — gains
    the framework's findings, so the two integration points read from one
    consistent history. Returns the created ``Evidence`` records; does
    nothing (returns an empty tuple) if the execution itself failed, since a
    failed framework run produced no analytical content worth recording."""
    if not result.success:
        return ()

    created = []
    quality = _quality_for_confidence(result.confidence)
    for finding in result.findings:
        state.analysis_findings.append(finding)
        evidence = add_evidence(
            state,
            source=f"framework:{result.framework_id}",
            source_type=EvidenceSourceType.CALCULATION,
            quality=quality,
            confidence=result.confidence,
            content=finding,
        )
        created.append(evidence)
    return tuple(created)
