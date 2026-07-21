"""The deliverable generator — orchestrates registry + sections + narrative
+ presentation + quality into one ``GeneratedDeliverable``, and is the ONE
place "no deliverable may publish without validation" is actually enforced:
``export_validated_deliverable`` refuses to call the export model unless
the quality report already attached to the deliverable passed every check.
"""

from __future__ import annotations

import dataclasses

from app.deliverables.audience import order_sections_for_audience
from app.deliverables.errors import QualityValidationFailedError
from app.deliverables.export import export_deliverable
from app.deliverables.models import (
    Audience,
    DeliverableType,
    ExportFormat,
    ExportResult,
    GeneratedDeliverable,
    VisualSpec,
    new_deliverable_id,
)
from app.deliverables.quality import assess_deliverable_quality
from app.deliverables.registry import DeliverableRegistry, default_deliverable_registry
from app.deliverables.section_builder import build_section
from app.deliverables.sections import resolve_order
from app.synthesis.state import SynthesisState


def generate_deliverable(
    deliverable_type: DeliverableType,
    state: SynthesisState,
    audience: Audience,
    registry: DeliverableRegistry | None = None,
    *,
    narrative_id: str | None = None,
    trade_off_result=None,
    include_optional_sections: tuple[str, ...] = (),
    visuals: tuple[VisualSpec, ...] = (),
    section_visual_ids: dict | None = None,
) -> GeneratedDeliverable:
    """Assembles every REQUIRED section (plus any requested optional ones),
    orders them for the given audience, attaches quality validation, and
    returns a ``GeneratedDeliverable`` — never yet exported."""
    reg = registry or default_deliverable_registry()
    definition = reg.get(deliverable_type.value)

    optional = tuple(
        s for s in include_optional_sections if s in definition.optional_sections
    )
    section_ids = resolve_order(definition.required_sections + optional)

    section_visual_ids = section_visual_ids or {}
    sections = []
    for sid in section_ids:
        section = build_section(
            sid, state, narrative_id=narrative_id, trade_off_result=trade_off_result
        )
        if sid in section_visual_ids:
            section = dataclasses.replace(section, visual_ids=section_visual_ids[sid])
        sections.append(section)

    ordered_ids = order_sections_for_audience(
        audience, tuple(s.section_id for s in sections)
    )
    by_id = {s.section_id: s for s in sections}
    ordered_sections = tuple(by_id[sid] for sid in ordered_ids)

    deliverable = GeneratedDeliverable(
        id=new_deliverable_id(),
        deliverable_type=deliverable_type,
        audience=audience,
        sections=ordered_sections,
        visuals=visuals,
    )

    quality_report = assess_deliverable_quality(
        deliverable, definition, state, audience
    )
    return dataclasses.replace(deliverable, quality_report=quality_report)


def export_validated_deliverable(
    deliverable: GeneratedDeliverable,
    state: SynthesisState,
    export_format: ExportFormat,
    *,
    renderer=None,
) -> ExportResult:
    """ "No deliverable may publish without validation" — enforced here, not
    by convention. A deliverable with no quality report, or one that failed
    any check, cannot be exported."""
    if deliverable.quality_report is None:
        raise QualityValidationFailedError(
            f"deliverable {deliverable.id!r} has not been quality-validated"
        )
    if not deliverable.quality_report.all_passed:
        failed = [
            c.dimension.value for c in deliverable.quality_report.checks if not c.passed
        ]
        raise QualityValidationFailedError(
            f"deliverable {deliverable.id!r} failed quality validation: {failed}"
        )
    return export_deliverable(deliverable, state, export_format, renderer=renderer)
