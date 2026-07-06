"""Vault-wide, cross-note validator (M2-S2).

Walks a ``knowledge-vault/`` directory, validates each note's frontmatter (the
S1 single-note core), then runs **cross-note** checks and **coverage** checks,
aggregating everything into a structured :class:`VaultReport` (pure API — no
``print``, no CLI). Unlike ``validate_note`` (which raises on the first defect
of one note), the vault validator never fails fast: it collects all issues so a
caller sees the whole picture.

Severity split: **ERROR** = a malformed or broken note/relationship (makes the
vault invalid); **WARNING** = an *incompleteness* (missing expected directory or
ADR-004 coverage) that does not, on its own, invalidate the vault.

Reference resolution: a note is addressable by its ``id``, its vault-relative
path (without ``.md``), its ``title``, and its ``aliases``. Both frontmatter ref
fields and body links are written as ``[[target]]`` (ADR-003 §5/§8), so a single
``[[...]]`` scan covers "broken wikilinks" and "missing referenced notes".

Scoping: files under ``.obsidian``/``_attachments``/``_meta``/``graphify-out``
(any component starting ``.`` or ``_``, plus ``graphify-out``) are ignored.

Not implemented — **schema-version consistency**: neither ADR-003 §5 nor ADR-004
defines a per-note ``schema_version`` field (ADR-003 §11 versions the *graph*
schema at index time, which is M3/out of scope). "Schema consistency" here means
every note validates against its type's current model; a dedicated per-note
``schema_version`` field is an open decision (D-9), not invented here.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from knowledge.frontmatter import (
    CommonHeader,
    FrameworkNote,
    FrameworkTier,
    FrontmatterError,
    NoteType,
)
from knowledge.frontmatter_validator import validate_note

#: The 15 required consulting domains — ADR-004 §2 (matched by note ``title``).
REQUIRED_DOMAINS: frozenset[str] = frozenset(
    {
        "Profitability",
        "Revenue Growth",
        "Cost Reduction",
        "Pricing",
        "Market Entry",
        "M&A",
        "New Product Launch",
        "Digital Transformation",
        "Supply Chain",
        "Organizational Design",
        "AI Strategy",
        "Corporate Strategy",
        "Customer Strategy",
        "Sales & Marketing",
        "Private Equity Due Diligence",
    }
)

#: Expected vault category directories (one per note type). [Inference] — the
#: ADRs do not fix directory names; this is the repo convention + ADR-004 types.
#: Advisory (WARNING), so it can be tuned without breaking validation.
EXPECTED_CATEGORY_DIRS: frozenset[str] = frozenset(
    {
        "frameworks",
        "domains",
        "industries",
        "kpis",
        "deliverables",
        "playbooks",
        "companies",
        "prior-cases",
        "lessons",
        "templates",
        "issue-trees",
        "business-problems",
        "recommendations",
    }
)

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    """One finding: the rule, its severity, a message, and the note (if any)."""

    rule: str
    severity: ValidationSeverity
    message: str
    note: str | None = None


@dataclass(frozen=True)
class VaultReport:
    """Aggregated vault validation result."""

    issues: tuple[ValidationIssue, ...]
    note_count: int

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity is ValidationSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity is ValidationSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        """True when there are no ERROR-severity issues (WARNINGs are allowed)."""
        return not self.errors


@dataclass(frozen=True)
class _ParsedNote:
    rel: str
    model: CommonHeader
    text: str
    keys: frozenset[str] = field(default_factory=frozenset)


def _link_target(inner: str) -> str:
    """The addressable target of a ``[[inner]]`` link (drop ``|alias``/``#anchor``)."""
    return inner.split("|", 1)[0].split("#", 1)[0].strip()


def _normalize_ref(value: str) -> str:
    """Normalize a ref-field value — ``[[target]]`` or a bare key — to its key."""
    text = value.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    return _link_target(text)


def _link_targets(text: str) -> list[str]:
    targets = [_link_target(m.group(1)) for m in _WIKILINK.finditer(text)]
    return [t for t in targets if t]


def _addressable_keys(rel: str, model: CommonHeader) -> frozenset[str]:
    rel_no_ext = rel.replace("\\", "/").removesuffix(".md")
    return frozenset({model.id, model.title, rel_no_ext, *model.aliases})


def _is_excluded(rel: Path) -> bool:
    return any(
        part.startswith((".", "_")) or part == "graphify-out" for part in rel.parts
    )


def _check_duplicate_ids(notes: list[_ParsedNote]) -> list[ValidationIssue]:
    by_id: dict[str, list[str]] = defaultdict(list)
    for note in notes:
        by_id[note.model.id].append(note.rel)
    issues: list[ValidationIssue] = []
    for note_id in sorted(by_id):
        rels = by_id[note_id]
        if len(rels) > 1:
            issues.append(
                ValidationIssue(
                    "duplicate_id",
                    ValidationSeverity.ERROR,
                    f"id {note_id!r} is used by {len(rels)} notes: {sorted(rels)}",
                )
            )
    return issues


def _check_duplicate_aliases(notes: list[_ParsedNote]) -> list[ValidationIssue]:
    by_alias: dict[str, list[str]] = defaultdict(list)
    for note in notes:
        for alias in note.model.aliases:
            by_alias[alias].append(note.rel)
    return [
        ValidationIssue(
            "duplicate_alias",
            ValidationSeverity.ERROR,
            f"alias {alias!r} is claimed by {len(by_alias[alias])} notes: "
            f"{sorted(by_alias[alias])}",
        )
        for alias in sorted(by_alias)
        if len(by_alias[alias]) > 1
    ]


def _check_links(notes: list[_ParsedNote]) -> list[ValidationIssue]:
    resolvable: set[str] = set()
    for note in notes:
        resolvable |= note.keys
    issues: list[ValidationIssue] = []
    for note in notes:
        for target in _link_targets(note.text):
            if target not in resolvable:
                issues.append(
                    ValidationIssue(
                        "broken_wikilink",
                        ValidationSeverity.ERROR,
                        f"unresolved link [[{target}]]",
                        note.rel,
                    )
                )
            elif target in note.keys:
                issues.append(
                    ValidationIssue(
                        "circular_self_link",
                        ValidationSeverity.ERROR,
                        f"note references itself via [[{target}]]",
                        note.rel,
                    )
                )
    return issues


def _check_directories(vault_dir: Path) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            "missing_directory",
            ValidationSeverity.WARNING,
            f"expected category directory is missing: {name}/",
        )
        for name in sorted(EXPECTED_CATEGORY_DIRS)
        if not (vault_dir / name).is_dir()
    ]


def _check_domain_coverage(notes: list[_ParsedNote]) -> list[ValidationIssue]:
    domains = [n for n in notes if n.model.type is NoteType.DOMAIN]
    covered = {n.model.title for n in domains}
    issues: list[ValidationIssue] = [
        ValidationIssue(
            "missing_domain",
            ValidationSeverity.WARNING,
            f"required domain not covered by a domain note: {name}",
        )
        for name in sorted(REQUIRED_DOMAINS)
        if name not in covered
    ]
    primary_refs: set[str] = set()
    for note in notes:
        model = note.model
        if isinstance(model, FrameworkNote) and model.tier is FrameworkTier.PRIMARY:
            primary_refs.update(_normalize_ref(d) for d in model.domains)
    for domain in domains:
        if not (domain.keys & primary_refs):
            issues.append(
                ValidationIssue(
                    "domain_without_primary_framework",
                    ValidationSeverity.WARNING,
                    f"domain {domain.model.title!r} has no primary framework",
                    domain.rel,
                )
            )
    return issues


def validate_vault(vault_dir: Path) -> VaultReport:
    """Validate every note under ``vault_dir`` and return an aggregated report."""
    if not vault_dir.is_dir():
        return VaultReport(
            (
                ValidationIssue(
                    "vault_directory",
                    ValidationSeverity.ERROR,
                    f"vault path is not a directory: {vault_dir}",
                ),
            ),
            0,
        )
    issues: list[ValidationIssue] = []
    notes: list[_ParsedNote] = []
    for path in sorted(vault_dir.rglob("*.md")):
        rel = path.relative_to(vault_dir)
        if _is_excluded(rel):
            continue
        rel_str = str(rel).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        try:
            model = validate_note(text)
        except FrontmatterError as exc:
            issues.append(
                ValidationIssue(
                    "frontmatter", ValidationSeverity.ERROR, str(exc), rel_str
                )
            )
            continue
        notes.append(
            _ParsedNote(
                rel=rel_str,
                model=model,
                text=text,
                keys=_addressable_keys(rel_str, model),
            )
        )
    issues.extend(_check_duplicate_ids(notes))
    issues.extend(_check_duplicate_aliases(notes))
    issues.extend(_check_links(notes))
    issues.extend(_check_directories(vault_dir))
    issues.extend(_check_domain_coverage(notes))
    return VaultReport(tuple(issues), len(notes))
