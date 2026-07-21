"""Knowledge Library — the typed Python framework catalog (87 frameworks),
approved for integration into ``app.pipeline`` under ADR-014 Phase 1.

This is a **different artifact** from the `knowledge-vault/*.md` prose
knowledge base governed by ADR-003/004/011 — see ADR-011's 2026-07-19 note.
Do not conflate the two.

The re-exports below are exactly the symbols ADR-014 §7.1 names as the
sanctioned integration surface — a future ``app.pipeline`` adapter should
need nothing beyond this package-level import to build a framework-catalog
lookup into its own prompt construction. Reaching into a submodule
(``app.knowledge.catalog``, etc.) or a private (``_``-prefixed) symbol is
prohibited by ADR-014 §7.4.
"""

from __future__ import annotations

from app.knowledge.registry import FrameworkRegistry, default_framework_registry
from app.knowledge.selection import select_frameworks

__all__ = [
    "FrameworkRegistry",
    "default_framework_registry",
    "select_frameworks",
]
