"""Framework composition validator (requester's "Framework Composition"
section) — e.g. the Market Entry chain: PESTLE -> Five Forces -> TAM/SAM/SOM
-> SWOT -> Financial Model -> Risk Matrix.

**Blocking vs. advisory, the same asymmetry ``app.consulting.quality_gates``
established:** an unknown framework, a dependency cycle, or an engagement
incompatibility make the composition unusable (``valid=False``) — nothing can
be executed. A caller-given order that violates a dependency, or a weak
output-to-input alignment, are advisory: this module still returns a
corrected, usable ``execution_order`` (via the registry's topological sort)
alongside the finding, rather than blocking on something it can fix itself.
"""

from __future__ import annotations

from app.consulting.models import EngagementCategory
from app.knowledge.errors import CircularDependencyError, UnknownFrameworkError
from app.knowledge.models import CompositionIssue, CompositionPlan
from app.knowledge.registry import FrameworkRegistry


def _loose_match(needle: str, haystacks: tuple[str, ...]) -> bool:
    n = needle.lower()
    return any(n in h.lower() or h.lower() in n for h in haystacks)


def validate_composition(
    framework_ids: tuple[str, ...],
    registry: FrameworkRegistry,
    *,
    engagement: EngagementCategory | None = None,
) -> CompositionPlan:
    issues: list[CompositionIssue] = []
    frameworks = {}

    for fid in framework_ids:
        try:
            frameworks[fid] = registry.get(fid)
        except UnknownFrameworkError as exc:
            issues.append(CompositionIssue(fid, str(exc)))
    if issues:
        return CompositionPlan(execution_order=(), valid=False, issues=tuple(issues))

    blocking = False
    if engagement is not None:
        for fid, framework in frameworks.items():
            if engagement not in framework.supported_engagements:
                issues.append(
                    CompositionIssue(
                        fid, f"does not support engagement '{engagement.value}'"
                    )
                )
                blocking = True

    try:
        order = registry.resolve_dependency_order(framework_ids)
    except CircularDependencyError as exc:
        issues.append(CompositionIssue("<composition>", str(exc)))
        return CompositionPlan(execution_order=(), valid=False, issues=tuple(issues))

    if blocking:
        return CompositionPlan(execution_order=order, valid=False, issues=tuple(issues))

    implicit = set(order) - set(framework_ids)
    for fid in sorted(implicit):
        issues.append(
            CompositionIssue(fid, "pulled in implicitly as a required dependency")
        )

    position = {fid: i for i, fid in enumerate(framework_ids)}
    for fid in framework_ids:
        for dep in frameworks[fid].dependencies:
            if dep in position and position[dep] > position[fid]:
                issues.append(
                    CompositionIssue(
                        fid,
                        f"declared dependency '{dep}' appears AFTER it in the "
                        "given order — execution_order has been corrected",
                    )
                )

    for fid in framework_ids:
        framework = frameworks[fid]
        if not framework.required_inputs or not framework.dependencies:
            continue
        upstream_ids = [d for d in framework.dependencies if d in frameworks]
        upstream_outputs = tuple(
            o for d in upstream_ids for o in frameworks[d].output_schema.fields
        )
        if upstream_ids and not any(
            _loose_match(ri, upstream_outputs) for ri in framework.required_inputs
        ):
            issues.append(
                CompositionIssue(
                    fid,
                    "no declared upstream output appears to satisfy its "
                    "required inputs — verify data will come from elsewhere",
                )
            )

    return CompositionPlan(execution_order=order, valid=True, issues=tuple(issues))
