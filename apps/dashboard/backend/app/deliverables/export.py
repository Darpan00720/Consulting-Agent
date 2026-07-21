"""Export model (requester's "Exports" section) — structured export to all
6 named formats, every one preserving the full traceability chain
internally.

**Markdown, HTML, and JSON are REAL** — pure Python stdlib, genuine
rendering, no new dependency.

**PowerPoint, Word, and PDF are honest placeholders behind an injectable
renderer** — this backend has no document-generation library as a
dependency (verified: no ``python-pptx``/``python-docx``/``reportlab`` in
``pyproject.toml``), the exact same "verify before claiming, placeholder +
injectable client" boundary ``app.memory.adapters``' Graphify/AgentDB
adapters and ``app.tools.adapters``' Codex/GitHub adapters already
established for external systems this process doesn't natively have a
library for. A real renderer plugs in via the ``renderer`` parameter without
touching this module — even in placeholder mode, the FULL structured
intermediate representation (sections, visuals, traceability metadata) is
preserved as the placeholder's content, never a stub string.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable

from app.deliverables.models import (
    ExportFormat,
    ExportResult,
    GeneratedDeliverable,
    TraceabilityMetadata,
)
from app.synthesis.state import SynthesisState

RendererFn = Callable[[GeneratedDeliverable, TraceabilityMetadata], bytes]

_BINARY_CONTENT_TYPES = {
    ExportFormat.POWERPOINT: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
    ExportFormat.WORD: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ExportFormat.PDF: "application/pdf",
}


def compute_traceability(
    deliverable: GeneratedDeliverable, state: SynthesisState
) -> TraceabilityMetadata:
    all_ids = {tid for s in deliverable.sections for tid in s.traced_ids}
    recommendation_ids = tuple(sorted(i for i in all_ids if i in state.recommendations))
    finding_ids = tuple(sorted(i for i in all_ids if i in state.findings))
    evidence_ids = tuple(
        sorted(i for i in all_ids if i in state.engagement_state.evidence)
    )
    narrative_ids = [i for i in all_ids if i in state.narratives]
    return TraceabilityMetadata(
        deliverable_id=deliverable.id,
        recommendation_ids=recommendation_ids,
        finding_ids=finding_ids,
        evidence_ids=evidence_ids,
        narrative_id=narrative_ids[0] if narrative_ids else None,
    )


def _to_dict(
    deliverable: GeneratedDeliverable, traceability: TraceabilityMetadata
) -> dict:
    return {
        "id": deliverable.id,
        "deliverable_type": deliverable.deliverable_type.value,
        "audience": deliverable.audience.value,
        "sections": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "content": list(s.content),
                "traced_ids": list(s.traced_ids),
                "visual_ids": list(s.visual_ids),
            }
            for s in deliverable.sections
        ],
        "visuals": [
            {
                "id": v.id,
                "visual_type": v.visual_type.value,
                "title": v.title,
                "data_refs": list(v.data_refs),
                "data": v.data,
            }
            for v in deliverable.visuals
        ],
        "traceability": {
            "deliverable_id": traceability.deliverable_id,
            "recommendation_ids": list(traceability.recommendation_ids),
            "finding_ids": list(traceability.finding_ids),
            "evidence_ids": list(traceability.evidence_ids),
            "narrative_id": traceability.narrative_id,
        },
    }


def _export_json(
    deliverable: GeneratedDeliverable, traceability: TraceabilityMetadata
) -> bytes:
    payload = _to_dict(deliverable, traceability)
    return json.dumps(payload, indent=2).encode("utf-8")


def _export_markdown(
    deliverable: GeneratedDeliverable, traceability: TraceabilityMetadata
) -> bytes:
    lines = [f"# {deliverable.deliverable_type.value.replace('_', ' ').title()}", ""]
    for section in deliverable.sections:
        lines.append(f"## {section.title}")
        for item in section.content:
            lines.append(f"- {item} [{', '.join(section.traced_ids)}]")
        lines.append("")
    lines.append("## Traceability")
    lines.append(
        f"- Recommendations: {', '.join(traceability.recommendation_ids) or 'none'}"
    )
    lines.append(f"- Findings: {', '.join(traceability.finding_ids) or 'none'}")
    lines.append(f"- Evidence: {', '.join(traceability.evidence_ids) or 'none'}")
    return "\n".join(lines).encode("utf-8")


def _export_html(
    deliverable: GeneratedDeliverable, traceability: TraceabilityMetadata
) -> bytes:
    traceability_json = json.dumps(_to_dict(deliverable, traceability)["traceability"])
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(deliverable.deliverable_type.value)}</title>",
        "<script type='application/json' id='traceability'>"
        f"{traceability_json}</script>",
        "</head><body>",
    ]
    for section in deliverable.sections:
        parts.append(f"<h2>{html.escape(section.title)}</h2><ul>")
        for item in section.content:
            traced = html.escape(", ".join(section.traced_ids))
            parts.append(
                f"<li>{html.escape(item)} <small data-traced='{traced}'></small></li>"
            )
        parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts).encode("utf-8")


_REAL_EXPORTERS: dict[ExportFormat, Callable] = {
    ExportFormat.JSON: _export_json,
    ExportFormat.MARKDOWN: _export_markdown,
    ExportFormat.HTML: _export_html,
}

_CONTENT_TYPES = {
    ExportFormat.JSON: "application/json",
    ExportFormat.MARKDOWN: "text/markdown",
    ExportFormat.HTML: "text/html",
}


def export_deliverable(
    deliverable: GeneratedDeliverable,
    state: SynthesisState,
    export_format: ExportFormat,
    *,
    renderer: RendererFn | None = None,
) -> ExportResult:
    traceability = compute_traceability(deliverable, state)

    if renderer is not None:
        content = renderer(deliverable, traceability)
        return ExportResult(
            format=export_format,
            content=content,
            content_type=_BINARY_CONTENT_TYPES.get(
                export_format,
                _CONTENT_TYPES.get(export_format, "application/octet-stream"),
            ),
            traceability=traceability,
            is_placeholder=False,
        )

    if export_format in _REAL_EXPORTERS:
        content = _REAL_EXPORTERS[export_format](deliverable, traceability)
        return ExportResult(
            format=export_format,
            content=content,
            content_type=_CONTENT_TYPES[export_format],
            traceability=traceability,
            is_placeholder=False,
        )

    # PowerPoint / Word / PDF placeholder: the FULL structured intermediate
    # representation, never a stub — see module docstring.
    content = json.dumps(
        {
            "note": f"placeholder {export_format.value} export — no renderer injected",
            **_to_dict(deliverable, traceability),
        },
        indent=2,
    ).encode("utf-8")
    return ExportResult(
        format=export_format,
        content=content,
        content_type=_BINARY_CONTENT_TYPES.get(
            export_format, "application/octet-stream"
        ),
        traceability=traceability,
        is_placeholder=True,
    )
