"""Generic checkpoint helpers over the Memory Platform's ``MemoryType.CONSULTING``
bucket.

**2026-07-19 architecture review finding, fixed here:** four independent
layers (``app.consulting.engine``, ``app.synthesis.integration``,
``app.deliverables.integration``, ``app.evaluation.integration``) had each
reimplemented the identical mechanical core of "wrap a payload in a
``MemoryRecord`` under ``MemoryType.CONSULTING`` and store it" / "retrieve a
key and unwrap the first record, or report nothing found" — the same ~15
lines, four times, with zero domain-specific variation. This module is that
shared mechanical core; every caller keeps its OWN ``serialize_x``/
``deserialize_x`` functions and its OWN domain-specific "not found" error —
only the store/retrieve boilerplate is centralized.

This is NOT a new architectural layer: it is two functions living inside the
Memory Platform package every one of those four callers already directly
depends on, exactly the kind of low-level, domain-free infrastructure helper
that is safe to centralize without creating the cross-layer coupling this
codebase's "duplication over coupling to a private symbol" precedent
otherwise guards against — a checkpoint key and a payload have no domain
meaning to entangle.

**2026-07-19 ADR-014 Phase 0 addition — production database namespace
isolation.** ``MemoryType.CONSULTING`` resolves (via ``MemoryService``'s
default-provider fallback) to ``CheckpointAdapter``, which wraps the SAME
``app.db`` event-sourced SQLite store ``app.pipeline.engine`` writes its own
real, live phase-completion events into (both write ``event_type=
"phase_completed"`` rows into the same ``events`` table, keyed by
``engagement_id``). Before this fix, a W7–W12 checkpoint written under an
``engagement_id`` that happened to collide with a real production
engagement id would be indistinguishable, in that engagement's event
history, from a genuine completed pipeline phase — exactly the risk
ADR-014 §9 identifies as a Phase-1 precondition. Every key this module
handles is now transparently reserved under a namespace no real engagement
id can plausibly collide with (``_RESERVED_NAMESPACE``), so a W7–W12
checkpoint is *physically* isolated from ``app.pipeline``'s own event
stream in the shared store, regardless of what identifier the caller's own
key embeds. This changes only the physical storage key; every caller's own
key format, and every existing test, is unaffected because store/load are
always used as a symmetric pair through this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_RESERVED_NAMESPACE = "__w7w12_reserved__"


def _namespaced_key(key: str) -> str:
    return f"{_RESERVED_NAMESPACE}::{key}"


async def store_checkpoint(
    key: str,
    payload: Any,
    *,
    trace_id: str = "",
    metadata: Mapping[str, str] | None = None,
    memory_service=None,
):
    """Persist ``payload`` under ``key`` in ``MemoryType.CONSULTING`` — the
    one memory type every checkpoint in this platform reuses; never a new
    one. Physically stored under a reserved namespace (see module docstring)
    so it can never be mistaken for a real ``app.pipeline`` engagement
    event, even under an identical caller-supplied ``key``."""
    from app.memory.models import MemoryRecord, MemoryType
    from app.memory.service import default_service

    memory = memory_service or default_service()
    return await memory.store(
        MemoryRecord(
            key=_namespaced_key(key),
            value=payload,
            memory_type=MemoryType.CONSULTING,
            metadata=metadata or {},
        ),
        trace_id=trace_id,
    )


async def load_checkpoint(key: str, memory_service=None) -> Any | None:
    """Returns the stored payload, or ``None`` if nothing was checkpointed
    under ``key`` — the caller decides what "not found" means for their own
    domain (which error to raise, if any), so this helper never raises."""
    from app.memory.models import MemoryType
    from app.memory.service import default_service

    memory = memory_service or default_service()
    result = await memory.retrieve(_namespaced_key(key), MemoryType.CONSULTING)
    if not result.success or not result.records:
        return None
    return result.records[0].value
