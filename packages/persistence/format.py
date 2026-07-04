"""Persistence codec — pure (de)serialization + schema validation (M1.8-S2).

This module owns the **on-disk format** and nothing else. Every function is
**pure** (PER-013): deterministic, side-effect-free, no filesystem IO, no
globals, no input mutation, no caching. It **never hashes** and **never touches
the filesystem** — the store (S4) computes SHA-256 and does IO; ``atomic.py``
(S3) does atomic writes. The codec only turns values into text and back.

Error ownership: **malformed JSON / schema-invalid input is the codec's** — it
raises :class:`CorruptArtifactError`. Filesystem and atomic-write failures
belong to the store and atomic modules respectively.

Serialization is deterministic and canonical (PER-014): equivalent objects
serialize identically, so round-trips are byte-stable — the basis of PER-011.

The module-level ``TypeAdapter`` values are immutable validators (like compiled
regexes), not cached results or mutable state.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Final

from pydantic import ConfigDict, Field, TypeAdapter, ValidationError

from core.base import StratAgentModel
from persistence.errors import CorruptArtifactError
from state.events import Event
from state.models import EngagementState

_EVENT: Final[TypeAdapter[Event]] = TypeAdapter(Event)

_Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Manifest(StratAgentModel):
    """Persistence metadata — format version + integrity checksums only (DD-2).

    Deterministic by construction: no timestamps, UUIDs, paths, or machine
    metadata (preserves PER-011). Frozen value object.
    """

    model_config = ConfigDict(frozen=True)

    format_version: int = Field(ge=1)
    log_sha256: _Sha256
    snapshot_sha256: _Sha256


# --- event log ⇄ NDJSON ------------------------------------------------------


def dump_log(events: Sequence[Event]) -> str:
    """Serialize events to NDJSON — one event per line, in order. O(total bytes).

    Pure: inputs are not mutated. A trailing newline terminates every line so
    the result is append-friendly; an empty sequence yields ``""``.
    """
    return "".join(f"{event.model_dump_json()}\n" for event in events)


def load_log(text: str) -> tuple[Event, ...]:
    """Parse NDJSON back into events. O(total bytes).

    Every non-empty line must be a valid event; a malformed or blank interior
    line raises :class:`CorruptArtifactError` (the codec owns malformed input).
    ``""`` parses to an empty tuple.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":  # drop the terminating newline's empty tail
        lines = lines[:-1]
    events: list[Event] = []
    for index, line in enumerate(lines):
        if not line:
            raise CorruptArtifactError(f"empty line at index {index} in event log")
        try:
            events.append(_EVENT.validate_json(line))
        except ValidationError as exc:
            raise CorruptArtifactError(
                f"malformed event at line {index}: {exc.error_count()} error(s)"
            ) from exc
    return tuple(events)


# --- snapshot ⇄ JSON ---------------------------------------------------------


def dump_snapshot(state: EngagementState) -> str:
    """Serialize the state snapshot (canonical JSON). O(|state|). Pure."""
    return state.model_dump_json()


def load_snapshot(text: str) -> EngagementState:
    """Parse the state snapshot. O(|state|). Malformed → CorruptArtifactError."""
    try:
        return EngagementState.model_validate_json(text)
    except ValidationError as exc:
        raise CorruptArtifactError(
            f"malformed state snapshot: {exc.error_count()} error(s)"
        ) from exc


# --- manifest ⇄ JSON ---------------------------------------------------------


def dump_manifest(manifest: Manifest) -> str:
    """Serialize the manifest (canonical JSON). O(1). Pure."""
    return manifest.model_dump_json()


def load_manifest(text: str) -> Manifest:
    """Parse the manifest. O(1). Malformed/schema-invalid → CorruptArtifactError.

    Structural validation only (parseable into :class:`Manifest`); whether the
    ``format_version`` is *supported* is a load-time policy decision (the store,
    S4), not the codec's.
    """
    try:
        return Manifest.model_validate_json(text)
    except ValidationError as exc:
        raise CorruptArtifactError(
            f"malformed manifest: {exc.error_count()} error(s)"
        ) from exc
