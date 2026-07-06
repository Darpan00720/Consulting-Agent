"""Knowledge capability — the knowledge-vault schema + validators (M2).

M2-S1 provided the frontmatter **validator core**: typed models for the
knowledge-note frontmatter (ADR-003 §5 common header + ADR-004 §3 framework
schema) and a single-note validator. M2-S2 adds a model for **every** note
type and the **vault-wide** validator (:func:`validate_vault`) with cross-note
and coverage checks, producing a structured :class:`VaultReport`.

Out of scope (M3): indexing, embeddings, retrieval, search. Out of scope (S3+):
authoring vault content.
"""

from knowledge.frontmatter import (
    BusinessProblemNote,
    CommonHeader,
    CompanyNote,
    DeliverableKind,
    DeliverableNote,
    DomainNote,
    FrameworkNote,
    FrameworkTier,
    FrontmatterError,
    IndustryNote,
    IssueTreeNote,
    KpiNote,
    LessonNote,
    NoteStatus,
    NoteType,
    PlaybookNote,
    PriorCaseNote,
    RecommendationNote,
    TemplateNote,
    Visibility,
)
from knowledge.frontmatter_validator import parse_frontmatter, validate_note
from knowledge.vault_validator import (
    EXPECTED_CATEGORY_DIRS,
    REQUIRED_DOMAINS,
    ValidationIssue,
    ValidationSeverity,
    VaultReport,
    validate_vault,
)

__all__ = [
    "EXPECTED_CATEGORY_DIRS",
    "REQUIRED_DOMAINS",
    "BusinessProblemNote",
    "CommonHeader",
    "CompanyNote",
    "DeliverableKind",
    "DeliverableNote",
    "DomainNote",
    "FrameworkNote",
    "FrameworkTier",
    "FrontmatterError",
    "IndustryNote",
    "IssueTreeNote",
    "KpiNote",
    "LessonNote",
    "NoteStatus",
    "NoteType",
    "PlaybookNote",
    "PriorCaseNote",
    "RecommendationNote",
    "TemplateNote",
    "ValidationIssue",
    "ValidationSeverity",
    "VaultReport",
    "Visibility",
    "parse_frontmatter",
    "validate_note",
    "validate_vault",
]
