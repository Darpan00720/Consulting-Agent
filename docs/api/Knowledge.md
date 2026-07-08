---
title: Knowledge — Public API Reference
status: Stable
lifecycle_entered: 2026-07-08 (M2 finalization)
governing_adr: ADR-003 (Knowledge Architecture), ADR-004 (Consulting Knowledge Library)
applies_to: packages/knowledge
tags: [api, knowledge, validator, reference]
---

# Knowledge — Public API Reference

The public contract for the `packages/knowledge` package. This is the reference
all future milestones build against. **M3 (Graphify + Knowledge Agent) depends on
this surface; do not remove or rename any symbol without a new ADR and an updated
freeze test.**

This document covers **only the public surface** — models, enums, entry-point
functions, and their guarantees. Internal helpers (prefixed `_`) are not part of
the contract and may change without notice.

---

## Access and entry point

```python
from knowledge import (
    validate_note,    # single-note validation
    validate_vault,   # vault-wide validation
    parse_frontmatter, # raw YAML extraction (rarely needed directly)
)
```

The full `__all__` has **28 symbols** (pinned in `tests/knowledge/test_api_freeze.py`).

---

## Entry-point functions

### `parse_frontmatter(text: str) -> dict[str, object]`

Extracts and parses the leading `---` … `---` YAML frontmatter block from note
text. Returns a plain mapping. Raises `FrontmatterError` if:
- the note does not open with `---`
- the frontmatter block is unterminated (missing closing `---`)
- the block is invalid YAML
- the YAML parses to something other than a mapping (e.g. a bare scalar)

**Called by** `validate_note`; callers rarely need this directly.

### `validate_note(text: str) -> CommonHeader`

Validates one note's frontmatter against the typed schema. Returns the typed
model (a `CommonHeader` subclass specific to the note's `type`). Raises
`FrontmatterError` on any schema failure.

**Dispatch rule:** the `type` field routes to a per-type model:
- `framework` → `FrameworkNote` (ADR-004 §3 required attributes enforced)
- all other types → their typed subclass of `CommonHeader` (optional per-type
  fields; required fields: `id`, `type`, `title`, `source`, `last_verified`,
  `status`, `visibility`)

**Guarantees:**
- Pure and read-only — never touches the filesystem, never mutates the note (KV-010)
- Deterministic — given the same text it always returns the same model or raises
  the same error
- `extra="allow"` on every model — unrecognised frontmatter fields are ignored, not errors

### `validate_vault(vault_dir: Path) -> VaultReport`

Validates every note under `vault_dir` and returns an aggregated `VaultReport`.
Never raises — all defects are collected into the report.

**Per-note checks:**
- `validate_note` is called; a `FrontmatterError` is recorded as an ERROR for
  that note and scanning continues

**Cross-note checks (collected before returning):**
- `broken_wikilink` (ERROR) — a `[[target]]` link in any note (frontmatter or body)
  does not resolve to any known note by id, title, rel-path-no-ext, or alias
- `circular_self_link` (ERROR) — a note links to itself
- `duplicate_id` (ERROR) — two or more notes share the same `id`
- `duplicate_alias` (ERROR) — two or more notes claim the same alias

**Coverage checks (WARNINGs — do not make the vault invalid):**
- `missing_directory` — an expected category directory (e.g. `frameworks/`) is
  absent from the vault
- `missing_domain` — one of the 15 required ADR-004 §2 domains has no `domain`
  note with a matching `title`
- `domain_without_primary_framework` — a `domain` note has no `primary` `framework`
  note pointing at it

**Scoping:** files under `.obsidian`, `_attachments`, `_meta`, `graphify-out`, and
any path component beginning with `.` or `_` are excluded.

**Guarantees:**
- Pure and read-only — never mutates any note (KV-010)
- Collect-all — does not fail fast; the full report is always returned
- `VaultReport.is_valid` is `True` iff there are zero ERROR-severity issues

---

## Models

### `CommonHeader` (base for all notes)

The ADR-003 §5 common frontmatter header. Required on every note type.

| Field | Type | Constraint | Source |
|---|---|---|---|
| `id` | `str` | non-empty | ADR-003 §5 |
| `type` | `NoteType` | one of 13 values | ADR-003 §5 ∪ ADR-004 |
| `title` | `str` | non-empty | ADR-003 §5 |
| `source` | `str` | non-empty (provenance required) | ADR-003 §10 |
| `last_verified` | `date` | ISO date | ADR-003 §10 |
| `status` | `NoteStatus` | `approved` or `draft` | Roadmap M2 |
| `visibility` | `Visibility` | `global` or `tenant` | ADR-003 §5/§10 |
| `tenant` | `str \| None` | required iff `visibility=tenant` | ADR-003 §5 |
| `tags` | `list[str]` | optional | ADR-003 §5 |
| `aliases` | `list[str]` | optional (used for wikilink resolution) | ADR-003 §5 |
| `confidence` | `float \| None` | `[0.0, 1.0]` | ADR-003 §5 |
| `created`, `updated` | `date \| None` | optional | ADR-003 §5 |

### `FrameworkNote(CommonHeader)` — required for `type: framework`

Adds the 11 required ADR-004 §3 framework asset attributes (all non-empty):

`name`, `domains` (list of refs), `tier` (`FrameworkTier`), `purpose`,
`when_to_use`, `diagnostic_questions` (list), `success_metrics` (list),
`common_risks` (list), `common_mistakes` (list), `related_frameworks` (list,
may be empty), `version`.

### `KpiNote(CommonHeader)` — for `type: kpi`

Optional typed additions (ADR-003 §5): `formula: str | None`, `unit: str | None`,
`benchmark: str | None` (reviewer-supplied per D-6), `industry: str | None` (ref).

### `IndustryNote(CommonHeader)` — for `type: industry`

Optional typed additions (ADR-003 §5): `structure: str | None`,
`typical_margins: str | None` (reviewer-supplied), `growth_rate: str | None`
(reviewer-supplied), `key_kpis: list[str]` (refs).

### Other typed models

`DomainNote`, `IssueTreeNote`, `DeliverableNote`, `BusinessProblemNote`,
`RecommendationNote` — validated at `CommonHeader` level (no additional required
fields; see open decision D-8). `PlaybookNote`, `CompanyNote`, `PriorCaseNote`,
`LessonNote`, `TemplateNote` — optional typed fields per ADR-003 §5.

---

## Enums

### `NoteType` (13 values)

| Value | Note type | Source |
|---|---|---|
| `framework` | Consulting framework | ADR-003 §5 |
| `playbook` | Industry playbook | ADR-003 §5 |
| `industry` | Industry reference | ADR-003 §5 |
| `company` | Company profile (tenant-scoped) | ADR-003 §5 |
| `kpi` | KPI definition | ADR-003 §5 |
| `prior_case` | Sanitized prior case | ADR-003 §5 |
| `lesson` | Lesson learned | ADR-003 §5 |
| `template` | Deliverable template | ADR-003 §5 |
| `domain` | Consulting domain | ADR-004 |
| `issue_tree` | Issue tree (MECE branches) | ADR-004 |
| `deliverable` | Deliverable definition | ADR-004 |
| `business_problem` | Business problem classification | ADR-004 |
| `recommendation` | Engagement recommendation | ADR-004 |

### `NoteStatus`

`approved` — reviewed and promoted by a domain reviewer.
`draft` — AI-authored or pending reviewer sign-off (Hybrid D-6 policy).

### `FrameworkTier`

`primary` — the main framework for a domain (one per domain minimum).
`supporting` — supplementary frameworks within a domain.

### `Visibility`

`global` — available to all tenants.
`tenant` — scoped to a specific tenant (`tenant` field required).

### `ValidationSeverity`

`error` — a defect that makes the vault invalid (`VaultReport.is_valid = False`).
`warning` — an incompleteness (missing expected directory, ADR-004 coverage gap)
that does not invalidate the vault on its own.

---

## Report models

### `VaultReport`

Returned by `validate_vault`. Frozen dataclass.

| Attribute | Type | Meaning |
|---|---|---|
| `note_count` | `int` | Number of notes successfully scanned |
| `issues` | `tuple[ValidationIssue, ...]` | All issues (errors + warnings) |
| `errors` | property → `tuple[ValidationIssue, ...]` | ERROR-severity subset |
| `warnings` | property → `tuple[ValidationIssue, ...]` | WARNING-severity subset |
| `is_valid` | property → `bool` | `True` iff `len(errors) == 0` |

### `ValidationIssue`

One finding. Frozen dataclass.

| Field | Type | Meaning |
|---|---|---|
| `rule` | `str` | Rule identifier (e.g. `"broken_wikilink"`, `"duplicate_id"`) |
| `severity` | `ValidationSeverity` | ERROR or WARNING |
| `message` | `str` | Human-readable description |
| `note` | `str \| None` | Vault-relative path of the offending note (if applicable) |

---

## Constants

### `REQUIRED_DOMAINS: frozenset[str]`

The 15 domain titles required by ADR-004 §2. Used by `validate_vault` for
`missing_domain` coverage checks.

### `EXPECTED_CATEGORY_DIRS: frozenset[str]`

The expected vault category directory names (e.g. `"frameworks"`, `"kpis"`).
Used by `validate_vault` for `missing_directory` advisory warnings.

---

## Errors

### `FrontmatterError`

Raised by `parse_frontmatter` and `validate_note`. Inherits from
`common.errors.StratAgentError`. Carries a descriptive message; wraps the
underlying `yaml.YAMLError` or `pydantic.ValidationError` as `__cause__`.

---

## Known limitations (open decisions)

| Decision | Impact |
|---|---|
| **D-8** — 5 ADR-004-added types (`domain`, `issue_tree`, `deliverable`, `business_problem`, `recommendation`) have no per-type frontmatter field schema in the ADRs | These types are validated at `CommonHeader` level only; per-type field requiredness is deferred to M3/a future ADR |
| **D-9** — No per-note `schema_version` field | Schema consistency means every note validates against the *current* model; a dedicated version field is not yet specified |
| **D-4** — ADR-003/004 remain `status: Proposed` | The ADRs govern this implementation but have not been formally ratified to `Accepted`; deferred to a standalone review |

---

## Governance model

**Hybrid D-6 authorship policy:** the assistant drafts notes (`status: draft`);
a domain reviewer promotes to `status: approved` and supplies benchmark values,
KPI targets, company-specific knowledge, and prior-case details. No AI-authored
note becomes authoritative without reviewer sign-off.

**Validator role:** the validator enforces form (schema, provenance, wikilink
integrity, coverage). It does **not** judge correctness of consulting content —
that is the reviewer's responsibility.

**Vault as single source of truth (ADR-003):** the vault is the only authoritative
firm-knowledge store. Graphify (M3) will derive a queryable graph+index from it;
the validator is a precondition for that pipeline.

---

## Stability guarantee

The 28-symbol `__all__` is pinned by `tests/knowledge/test_api_freeze.py`. Any
addition, removal, or rename of a public symbol, or any change to a frozen function
signature or required field, will fail the freeze test. Changes require a new ADR
and an updated freeze test before merging.
