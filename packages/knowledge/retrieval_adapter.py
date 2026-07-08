"""Knowledge vault retrieval adapter (M3, Phase 1C contract).

Implements the approved retrieval contract from M3-Design.md §9.
Primary path: direct vault scan (frontmatter + body) per Phase 1B Option A.
Graphify is an optional runtime supplement via graphify-mcp — this module
succeeds without it.

Public symbols exported via ``knowledge.__all__`` (D-14):
    KnowledgeRetrievalError, RetrievalQuery, RetrievalResult, retrieve
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.errors import StratAgentError
from knowledge.frontmatter import CommonHeader, FrontmatterError, NoteType, Visibility
from knowledge.frontmatter_validator import validate_note

_log = logging.getLogger(__name__)

_MAX_RESULTS: int = 50  # hard cap; NOT in __all__

# Ranking field weights — M3-Design.md §9.4
_WEIGHTS: dict[str, float] = {
    "title": 4.0,
    "name": 3.5,
    "purpose": 3.0,
    "when_to_use": 2.0,
    "domains": 1.5,
    "diagnostic_questions": 1.5,
    "body": 1.0,
}

# Tie-breaking type priority — M3-Design.md §9.5 (lower = higher priority)
_TYPE_PRIORITY: dict[NoteType, int] = {
    NoteType.FRAMEWORK: 0,
    NoteType.DOMAIN: 1,
    NoteType.KPI: 2,
    NoteType.INDUSTRY: 3,
    NoteType.ISSUE_TREE: 4,
    NoteType.BUSINESS_PROBLEM: 5,
}


class KnowledgeRetrievalError(StratAgentError):
    """Raised for invalid query parameters or missing vault_dir.

    Empty results are NOT an error — retrieve() returns [] when nothing matches.
    """


@dataclass(frozen=True)
class RetrievalQuery:
    """Input to retrieve() — query text + optional tenant/type filter + limit.

    M3-Design.md §9.2.
    """

    text: str
    tenant_id: str | None = None  # None → return global-visibility notes only
    types: frozenset[NoteType] | None = None  # None → all types
    limit: int = 10


@dataclass(frozen=True)
class RetrievalResult:
    """One retrieved note with full provenance (M3-Design.md §9.3)."""

    note_id: str
    note_path: Path  # relative to vault_dir
    commit_hash: str  # git HEAD at retrieval time; "unknown" if git unavailable
    title: str
    note_type: NoteType
    source: str
    score: float  # normalised to [0.0, 1.0]
    excerpt: str  # most-relevant body section ≤ 500 chars
    visibility: Visibility
    tenant: str | None
    last_verified: str  # ISO "YYYY-MM-DD"


# ── internal helpers ──────────────────────────────────────────────────────────


@dataclass
class _Candidate:
    score: float
    note: CommonHeader
    rel_path: Path
    body: str


def _is_excluded(rel: Path) -> bool:
    """True for graphify-out/**, hidden dirs (.), and underscore dirs (_)."""
    return any(
        part.startswith((".", "_")) or part == "graphify-out" for part in rel.parts
    )


def _tokenize(text: str) -> frozenset[str]:
    """Lower-case tokens ≥ 2 chars; split on whitespace and non-word chars."""
    return frozenset(t.lower() for t in re.split(r"[\s\W]+", text) if len(t) >= 2)


def _field_text(value: object) -> str:
    """Coerce a frontmatter field value to a searchable lower-case string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(v) for v in value).lower()
    return str(value).lower()


def _score(fm: dict[str, Any], tokens: frozenset[str]) -> float:
    """Weighted field-hit score normalised to [0.0, 1.0] (M3-Design.md §9.4).

    Only fields with non-empty text contribute to the denominator, so non-
    framework notes (title + body only) are scored fairly against their peers.
    """
    total_weight = 0.0
    hit_weight = 0.0
    for field, weight in _WEIGHTS.items():
        text = _field_text(fm.get(field))
        if not text:
            continue  # absent/empty → excluded from denominator
        total_weight += weight
        if any(t in text for t in tokens):
            hit_weight += weight
    return hit_weight / total_weight if total_weight > 0.0 else 0.0


def _extract_body(text: str) -> str:
    """Return everything after the closing '---' of the YAML frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).strip()
    return ""


def _excerpt(body: str, tokens: frozenset[str]) -> str:
    """Return the first body section that contains a query token, ≤ 500 chars.

    Falls back to the first 500 chars of body when no section matches.
    """
    if not body:
        return ""
    sections = re.split(r"\n(?=#{1,2}\s)", body)
    for section in sections:
        if any(t in section.lower() for t in tokens):
            return section.strip()[:500]
    return body[:500]


def _git_head(vault_dir: Path) -> str:
    """Return the current git HEAD commit hash; 'unknown' on any failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=vault_dir,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def _sort_key(c: _Candidate) -> tuple[float, int, int, str]:
    """Tie-breaking key — M3-Design.md §9.5."""
    return (
        -c.score,
        -c.note.last_verified.toordinal(),  # DESC: negate ordinal
        _TYPE_PRIORITY.get(c.note.type, 99),  # ASC
        c.note.id,  # ASC
    )


# ── public API ────────────────────────────────────────────────────────────────


def retrieve(
    query: RetrievalQuery,
    *,
    vault_dir: Path = Path("knowledge-vault"),
) -> list[RetrievalResult]:
    """Scan vault_dir, score notes against query, return ranked results.

    Implements the M3-Design.md §9.6 filtering pipeline:
        glob → frontmatter → type filter → tenant filter → score → drop zeros
        → sort → slice → extract excerpts → evidence-pin → return

    Returns [] when no notes match; never raises for empty results.
    Raises KnowledgeRetrievalError for invalid inputs or missing vault_dir.
    """
    # ── input validation (§9.8) ───────────────────────────────────────────────
    if not query.text.strip():
        raise KnowledgeRetrievalError("RetrievalQuery.text must not be empty")
    if query.limit < 1:
        raise KnowledgeRetrievalError(
            f"RetrievalQuery.limit must be ≥ 1, got {query.limit}"
        )
    if not vault_dir.is_dir():
        raise KnowledgeRetrievalError(
            f"vault_dir not found or not a directory: {vault_dir}"
        )

    tokens = _tokenize(query.text)
    cap = min(query.limit, _MAX_RESULTS)

    # ── step 1: glob, sorted ascending ───────────────────────────────────────
    candidates: list[_Candidate] = []

    for path in sorted(vault_dir.rglob("*.md")):
        rel = path.relative_to(vault_dir)
        if _is_excluded(rel):
            continue

        # ── step 2: read + parse frontmatter ─────────────────────────────────
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("cannot read %s: %s — skipping", rel, exc)
            continue

        try:
            note = validate_note(text)
        except FrontmatterError as exc:
            _log.warning("bad frontmatter in %s: %s — skipping", rel, exc)
            continue

        # ── step 3: type filter ───────────────────────────────────────────────
        if query.types is not None and note.type not in query.types:
            continue

        # ── step 4: tenant filter (KR-003 — always enforced) ─────────────────
        if note.visibility is Visibility.TENANT and note.tenant != query.tenant_id:
            continue

        # ── step 5: score ─────────────────────────────────────────────────────
        body = _extract_body(text)
        fm: dict[str, Any] = note.model_dump()
        fm["body"] = body

        s = _score(fm, tokens)
        if s == 0.0:
            continue

        candidates.append(_Candidate(score=s, note=note, rel_path=rel, body=body))

    # ── step 6: sort (§9.5 tie-breaking) ─────────────────────────────────────
    candidates.sort(key=_sort_key)

    # ── step 7: slice ─────────────────────────────────────────────────────────
    top = candidates[:cap]

    # ── step 8: evidence pin — one git call per retrieve() invocation ─────────
    commit_hash = _git_head(vault_dir)

    # ── step 9: build results ─────────────────────────────────────────────────
    return [
        RetrievalResult(
            note_id=c.note.id,
            note_path=c.rel_path,
            commit_hash=commit_hash,
            title=c.note.title,
            note_type=c.note.type,
            source=c.note.source,
            score=c.score,
            excerpt=_excerpt(c.body, tokens),
            visibility=c.note.visibility,
            tenant=c.note.tenant,
            last_verified=c.note.last_verified.isoformat(),
        )
        for c in top
    ]
