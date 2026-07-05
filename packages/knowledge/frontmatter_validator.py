"""Knowledge-note frontmatter validator (M2-S1).

Parses a note's YAML frontmatter block and validates it against the typed
schema in :mod:`knowledge.frontmatter`, dispatching by ``type`` (framework
notes use the ADR-004 §3 model; all others use the common header). Pure and
read-only: it takes note text and returns a validated model or raises
:class:`FrontmatterError` — it never touches the filesystem and never mutates a
note (KV-010). Vault-wide checks (dangling ``[[wikilinks]]``, id uniqueness,
ADR-004 coverage) are a later slice; this is the single-note core.
"""

from __future__ import annotations

import yaml
from pydantic import ValidationError

from knowledge.frontmatter import MODEL_BY_TYPE, CommonHeader, FrontmatterError

_FENCE = "---"


def parse_frontmatter(text: str) -> dict[str, object]:
    """Extract and parse the leading YAML frontmatter block into a mapping.

    Raises :class:`FrontmatterError` if the block is absent, unterminated, not
    valid YAML, or does not parse to a mapping.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise FrontmatterError(
            "note has no YAML frontmatter block (must open with '---')"
        )
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            block = "\n".join(lines[1:index])
            break
    else:
        raise FrontmatterError("unterminated frontmatter block (missing closing '---')")
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"malformed YAML frontmatter: {exc}") from exc
    if data is None or not isinstance(data, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return data


def validate_note(text: str) -> CommonHeader:
    """Validate a note's frontmatter; return the typed model or raise.

    Dispatches on ``type``: ``framework`` → the ADR-004 §3 model, otherwise the
    common header. A missing/unknown ``type`` fails common-header validation.
    """
    data = parse_frontmatter(text)
    model = MODEL_BY_TYPE.get(str(data.get("type")), CommonHeader)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise FrontmatterError(
            f"frontmatter failed schema validation: {exc.error_count()} error(s)"
        ) from exc
