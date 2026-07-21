"""Business impact model (requester's "Business Impact" section): assemble
and validate per-dimension estimates across all 8 named dimensions, each
carrying its own confidence — "confidence must accompany every estimate" is
enforced structurally, not left to convention.
"""

from __future__ import annotations

from app.synthesis.errors import SynthesisError
from app.synthesis.models import (
    BusinessImpactAssessment,
    BusinessImpactDimension,
    BusinessImpactEstimate,
    new_business_impact_id,
)


def assess_business_impact(
    target_ref: str, estimates: tuple[BusinessImpactEstimate, ...]
) -> BusinessImpactAssessment:
    """Every estimate must name a distinct dimension and carry a confidence
    — the requester's "confidence must accompany every estimate" as a hard
    check, the same discipline every "no unsupported X" invariant in this
    codebase already enforces at construction time."""
    if not estimates:
        raise SynthesisError(
            "a business impact assessment must include at least one estimate"
        )
    seen_dimensions: set[BusinessImpactDimension] = set()
    for est in estimates:
        if est.dimension in seen_dimensions:
            raise SynthesisError(
                f"duplicate estimate for dimension {est.dimension.value!r}"
            )
        seen_dimensions.add(est.dimension)
        if not (0.0 <= est.confidence <= 1.0):
            raise SynthesisError(
                f"confidence for dimension {est.dimension.value!r} must be in [0, 1]"
            )

    overall_confidence = sum(e.confidence for e in estimates) / len(estimates)
    return BusinessImpactAssessment(
        id=new_business_impact_id(),
        target_ref=target_ref,
        estimates=estimates,
        overall_confidence=overall_confidence,
    )


def coverage(assessment: BusinessImpactAssessment) -> float:
    """Fraction of the 8 named dimensions this assessment actually covers —
    a partial assessment (e.g. only financial dimensions estimated) is
    legitimate, but callers checking "how complete is this?" need a real
    number, not a guess."""
    covered = {e.dimension for e in assessment.estimates}
    return len(covered) / len(BusinessImpactDimension)
