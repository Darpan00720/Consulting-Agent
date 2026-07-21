"""Executive communication model (requester's "Executive Communication"
section): 8 named audiences, each with emphasis rules that adjust WHICH
sections/visuals get foregrounded and HOW they're framed — never the
underlying recommendation content. "Adjust emphasis. Never change underlying
recommendations" is enforced structurally: ``AudienceProfile`` only ever
lists section ids and framing guidance strings, never recommendation text.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.deliverables.models import Audience


@dataclass(frozen=True)
class AudienceProfile:
    audience: Audience
    emphasis_sections: tuple[str, ...]
    framing_notes: tuple[str, ...]


_PROFILES: dict[Audience, AudienceProfile] = {
    Audience.CEO: AudienceProfile(
        audience=Audience.CEO,
        emphasis_sections=("executive_summary", "recommendations", "business_case"),
        framing_notes=("Lead with strategic impact and growth trajectory",),
    ),
    Audience.BOARD: AudienceProfile(
        audience=Audience.BOARD,
        emphasis_sections=(
            "executive_summary",
            "risk_assessment",
            "governance_and_approvals",
        ),
        framing_notes=("Lead with governance, risk, and fiduciary implications",),
    ),
    Audience.CFO: AudienceProfile(
        audience=Audience.CFO,
        emphasis_sections=("business_case", "trade_off_analysis", "kpis_and_outcomes"),
        framing_notes=("Lead with quantified cost, benefit, and financial risk",),
    ),
    Audience.COO: AudienceProfile(
        audience=Audience.COO,
        emphasis_sections=(
            "implementation_roadmap",
            "kpis_and_outcomes",
            "risk_assessment",
        ),
        framing_notes=("Lead with operational feasibility and execution sequencing",),
    ),
    Audience.CTO: AudienceProfile(
        audience=Audience.CTO,
        emphasis_sections=("implementation_roadmap", "recommendations"),
        framing_notes=(
            "Lead with technical feasibility and architecture implications",
        ),
    ),
    Audience.CHRO: AudienceProfile(
        audience=Audience.CHRO,
        emphasis_sections=("governance_and_approvals", "implementation_roadmap"),
        framing_notes=("Lead with organizational and workforce impact",),
    ),
    Audience.BUSINESS_UNIT_LEADER: AudienceProfile(
        audience=Audience.BUSINESS_UNIT_LEADER,
        emphasis_sections=(
            "situation_complication_resolution",
            "key_findings",
            "implementation_roadmap",
        ),
        framing_notes=("Lead with what changes for this business unit specifically",),
    ),
    Audience.PROGRAM_SPONSOR: AudienceProfile(
        audience=Audience.PROGRAM_SPONSOR,
        emphasis_sections=(
            "implementation_roadmap",
            "kpis_and_outcomes",
            "governance_and_approvals",
        ),
        framing_notes=("Lead with program status, milestones, and blockers",),
    ),
}


def profile_for(audience: Audience) -> AudienceProfile:
    return _PROFILES[audience]


def order_sections_for_audience(
    audience: Audience, section_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """Emphasized sections move to the front, WITHIN the existing set of
    section ids — this reorders presentation only; it never adds, removes,
    or edits a section's content."""
    profile = profile_for(audience)
    emphasized = [sid for sid in profile.emphasis_sections if sid in section_ids]
    rest = [sid for sid in section_ids if sid not in emphasized]
    return tuple(emphasized) + tuple(rest)
