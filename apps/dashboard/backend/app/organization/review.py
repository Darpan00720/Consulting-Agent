"""Multi-stage review workflow (requester's "Review Process" section):
Peer -> Manager -> Partner -> Executive, each validating logic, evidence,
calculations, framework application, recommendations, clarity, and client
readiness.

The reviewer's judgment on each check is supplied by the caller
(``ReviewChecklistInput``) — this module's job is to confirm the reviewing
role actually HOLDS authority for the requested ``ReviewStage``
(``role.review_authority``), derive the outcome from the checklist, and
track iteration history per artifact — never to judge the analysis itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.organization.models import (
    ReviewChecklistInput,
    ReviewChecklistResult,
    ReviewOutcome,
    ReviewResult,
    ReviewStage,
    RoleDefinition,
    new_review_id,
)

_CHECK_NAMES = (
    "logic_sound",
    "evidence_traceable",
    "calculations_verified",
    "framework_application_correct",
    "recommendations_supported",
    "clarity",
    "client_ready",
)


def _checklist_results(
    checklist: ReviewChecklistInput,
) -> tuple[ReviewChecklistResult, ...]:
    return tuple(
        ReviewChecklistResult(name=name, passed=getattr(checklist, name))
        for name in _CHECK_NAMES
    )


def _derive_outcome(checks: tuple[ReviewChecklistResult, ...]) -> ReviewOutcome:
    failed = [c for c in checks if not c.passed]
    if not failed:
        return ReviewOutcome.APPROVED
    # logic/evidence/calculation failures are substantive — rework, not just
    # a comment; clarity/client-readiness alone can be approved with comments.
    substantive = {
        "logic_sound",
        "evidence_traceable",
        "calculations_verified",
        "framework_application_correct",
        "recommendations_supported",
    }
    if any(c.name in substantive for c in failed):
        return ReviewOutcome.REWORK_REQUIRED
    return ReviewOutcome.APPROVED_WITH_COMMENTS


def submit_for_review(
    artifact_ref: str,
    stage: ReviewStage,
    reviewer: RoleDefinition,
    checklist: ReviewChecklistInput,
) -> ReviewResult:
    """Never raises: a reviewer lacking authority for this stage produces a
    ``REJECTED`` result naming the gap, rather than an exception — the same
    "report, don't raise" discipline used everywhere in this platform for an
    expected, not exceptional, outcome."""
    if stage not in reviewer.review_authority:
        return ReviewResult(
            id=new_review_id(),
            artifact_ref=artifact_ref,
            stage=stage,
            reviewer_role_id=reviewer.id,
            outcome=ReviewOutcome.REJECTED,
            checklist=(),
            comments=(f"{reviewer.name} does not hold {stage.value} review authority",),
        )

    checks = _checklist_results(checklist)
    outcome = _derive_outcome(checks)
    return ReviewResult(
        id=new_review_id(),
        artifact_ref=artifact_ref,
        stage=stage,
        reviewer_role_id=reviewer.id,
        outcome=outcome,
        checklist=checks,
        comments=checklist.comments,
    )


@dataclass
class ReviewHistory:
    """Append-only iteration tracking per artifact — how many passes an
    artifact took before reaching ``APPROVED``."""

    _results: dict[str, list[ReviewResult]] = field(default_factory=dict)

    def record(self, result: ReviewResult) -> None:
        self._results.setdefault(result.artifact_ref, []).append(result)

    def all_results(self) -> tuple[ReviewResult, ...]:
        return tuple(r for results in self._results.values() for r in results)

    def history_for(self, artifact_ref: str) -> tuple[ReviewResult, ...]:
        return tuple(self._results.get(artifact_ref, ()))

    def iteration_count(self, artifact_ref: str) -> int:
        return len(self._results.get(artifact_ref, ()))

    def is_approved(self, artifact_ref: str) -> bool:
        history = self._results.get(artifact_ref, ())
        return bool(history) and history[-1].outcome in (
            ReviewOutcome.APPROVED,
            ReviewOutcome.APPROVED_WITH_COMMENTS,
        )
