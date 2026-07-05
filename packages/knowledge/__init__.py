"""Knowledge capability — the knowledge-vault schema + validators (M2).

M2-S1 provides the frontmatter **validator core**: typed models for the
knowledge-note frontmatter (ADR-003 §5 common header + ADR-004 §3 framework
schema) and a single-note validator. Vault content, vault-wide checks
(dangling ``[[wikilinks]]``, ADR-004 coverage), and indexing/retrieval (M3) are
out of scope for this slice.
"""

from knowledge.frontmatter import (
    CommonHeader,
    FrameworkNote,
    FrameworkTier,
    FrontmatterError,
    NoteStatus,
    NoteType,
    Visibility,
)
from knowledge.frontmatter_validator import parse_frontmatter, validate_note

__all__ = [
    "CommonHeader",
    "FrameworkNote",
    "FrameworkTier",
    "FrontmatterError",
    "NoteStatus",
    "NoteType",
    "Visibility",
    "parse_frontmatter",
    "validate_note",
]
