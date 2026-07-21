"""RACI model (requester's "Responsibility Matrix" section) — derived FROM
the registry's real ``deliverables_owned``/``decision_authority`` data,
never a second hand-maintained table that could drift from the catalog.

Activities are the 10 ``ConsultingStage`` values (reused from
``app.consulting.models`` — not duplicated) plus the 6 ``DecisionType``
values — 16 activities total.
"""

from __future__ import annotations

from app.consulting.models import ArtifactType, ConsultingStage
from app.organization.models import (
    EXPERIENCE_RANK,
    DecisionType,
    RACIAssignment,
    RACIMatrix,
    RACIRole,
    ResponsibilityConflict,
)
from app.organization.registry import OrganizationRegistry

# One canonical deliverable per lifecycle stage — matches
# ``app.consulting.artifacts``' own stage-to-artifact mapping (small,
# intentional duplication of a 10-entry table rather than importing that
# module's private ``_STAGE_OF_ARTIFACT``, the same "duplication over
# coupling to a private symbol" call ``app.memory.models`` already made for
# ``HealthState``).
_STAGE_ARTIFACT: dict[ConsultingStage, ArtifactType] = {
    ConsultingStage.PROBLEM_DEFINITION: ArtifactType.PROBLEM_STATEMENT,
    ConsultingStage.HYPOTHESIS_DEVELOPMENT: ArtifactType.HYPOTHESIS_LOG,
    ConsultingStage.ISSUE_TREE_CONSTRUCTION: ArtifactType.ISSUE_TREE,
    ConsultingStage.ANALYSIS_PLANNING: ArtifactType.ANALYSIS_PLAN,
    ConsultingStage.EVIDENCE_COLLECTION: ArtifactType.RESEARCH_SUMMARY,
    ConsultingStage.ANALYSIS_EXECUTION: ArtifactType.ASSUMPTION_REGISTER,
    ConsultingStage.SYNTHESIS: ArtifactType.FINDINGS_REPORT,
    ConsultingStage.RECOMMENDATIONS: ArtifactType.RECOMMENDATION_MATRIX,
    ConsultingStage.IMPLEMENTATION_ROADMAP: ArtifactType.IMPLEMENTATION_ROADMAP,
    ConsultingStage.EXECUTIVE_DELIVERABLE: ArtifactType.EXECUTIVE_SUMMARY,
}


def _owner_of(registry: OrganizationRegistry, artifact: ArtifactType) -> str | None:
    for role in registry.list():
        if artifact in role.deliverables_owned:
            return role.id
    return None


def _add(
    matrix: RACIMatrix, activity: str, role_id: str | None, raci: RACIRole
) -> None:
    if role_id is None:
        return
    key = (activity, role_id, raci)
    if any((a.activity, a.role_id, a.raci) == key for a in matrix.assignments):
        return  # already recorded — never duplicate the same triple
    matrix.assignments.append(
        RACIAssignment(activity=activity, role_id=role_id, raci=raci)
    )


def build_default_raci_matrix(registry: OrganizationRegistry) -> RACIMatrix:
    matrix = RACIMatrix()
    managing_partner = next(
        (r for r in registry.list() if r.reporting_line is None), None
    )
    top_id = managing_partner.id if managing_partner else None

    for stage, artifact in _STAGE_ARTIFACT.items():
        owner_id = _owner_of(registry, artifact)
        _add(matrix, stage.value, owner_id, RACIRole.RESPONSIBLE)
        _add(matrix, stage.value, owner_id, RACIRole.ACCOUNTABLE)
        if owner_id is not None:
            owner = registry.get(owner_id)
            if owner.reporting_line:
                _add(matrix, stage.value, owner.reporting_line, RACIRole.CONSULTED)
        if top_id is not None and top_id != owner_id:
            _add(matrix, stage.value, top_id, RACIRole.INFORMED)

    for decision in DecisionType:
        holders = registry.find_by_decision_authority(decision)
        if not holders:
            continue
        by_seniority = sorted(
            holders, key=lambda r: EXPERIENCE_RANK[r.experience_level]
        )
        most_senior = by_seniority[-1]
        least_senior = by_seniority[0]
        _add(matrix, decision.value, most_senior.id, RACIRole.ACCOUNTABLE)
        _add(matrix, decision.value, least_senior.id, RACIRole.RESPONSIBLE)
        if "qa_reviewer" not in (most_senior.id, least_senior.id):
            _add(matrix, decision.value, "qa_reviewer", RACIRole.CONSULTED)
        if top_id is not None and top_id not in (most_senior.id, least_senior.id):
            _add(matrix, decision.value, top_id, RACIRole.INFORMED)

    return matrix


def detect_conflicts(matrix: RACIMatrix) -> tuple[ResponsibilityConflict, ...]:
    """ "No duplicate ownership. Detect responsibility conflicts" — the two
    real conflict shapes a RACI matrix can have: an activity with zero
    Accountable owners, or an activity with more than one."""
    conflicts: list[ResponsibilityConflict] = []
    activities = {a.activity for a in matrix.assignments}
    for activity in sorted(activities):
        accountable = [
            a.role_id
            for a in matrix.assignments
            if a.activity == activity and a.raci is RACIRole.ACCOUNTABLE
        ]
        if len(accountable) == 0:
            conflicts.append(
                ResponsibilityConflict(
                    activity=activity, reason="no accountable owner", role_ids=()
                )
            )
        elif len(accountable) > 1:
            conflicts.append(
                ResponsibilityConflict(
                    activity=activity,
                    reason="multiple accountable owners",
                    role_ids=tuple(accountable),
                )
            )
    return tuple(conflicts)
