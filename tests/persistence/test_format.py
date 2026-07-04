"""M1.8-S2 codec tests: purity, canonical serialization, round-trips, errors.

Pure codec only — no filesystem, no hashing (the store supplies checksums).
One dedicated deterministic test per invariant; no randomness.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from persistence import format as codec
from persistence.errors import CorruptArtifactError
from persistence.format import (
    Manifest,
    dump_log,
    dump_manifest,
    dump_snapshot,
    load_log,
    load_manifest,
    load_snapshot,
)
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.ledgers import Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState

_SHA = "0" * 64
_SHA2 = "a" * 64


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _events() -> list[Event]:
    return [
        EngagementCreated(metadata=_meta(seq=1), slug="demo", tenant_id="t_1"),
        EvidenceAdded(
            metadata=_meta(seq=2),
            evidence=Evidence(claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5),
        ),
    ]


def _state() -> EngagementState:
    return EngagementState(
        metadata=EngagementMetadata(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    )


def _manifest() -> Manifest:
    return Manifest(format_version=1, log_sha256=_SHA, snapshot_sha256=_SHA2)


# --- PER-013 purity ----------------------------------------------------------


def test_per_013_codec_is_pure_and_deterministic() -> None:
    events = _events()
    before = [e.model_copy(deep=True) for e in events]
    a, b = dump_log(events), dump_log(events)
    assert a == b  # deterministic
    assert events == before  # inputs not mutated
    state = _state()
    assert dump_snapshot(state) == dump_snapshot(state)
    m = _manifest()
    assert dump_manifest(m) == dump_manifest(m)


def test_per_013_module_does_no_io_and_no_hashing() -> None:
    src = inspect.getsource(codec)
    # NB: the manifest FIELD names contain "sha256" legitimately (the codec
    # carries checksums; it never computes them) — so scan for hashing
    # imports/calls, not that substring.
    for banned in (
        "open(",
        "Path(",
        "pathlib",
        "hashlib",
        "hexdigest",
        "os.",
        "mkdir",
        "exists(",
        "write_text",
        "read_text",
        ".replace(",
        "rename",
    ):
        assert banned not in src, f"format.py must be pure/IO-free; found {banned!r}"


# --- PER-014 canonical serialization -----------------------------------------


def test_per_014_canonical_event() -> None:
    x = _events()[1]
    once = x.model_dump_json()
    from pydantic import TypeAdapter

    twice = TypeAdapter(Event).validate_json(once).model_dump_json()
    assert twice == once


def test_per_014_canonical_state() -> None:
    x = _state()
    once = dump_snapshot(x)
    assert dump_snapshot(load_snapshot(once)) == once


def test_per_014_canonical_manifest() -> None:
    x = _manifest()
    once = dump_manifest(x)
    assert dump_manifest(load_manifest(once)) == once


# --- log codec ---------------------------------------------------------------


def test_log_round_trip_preserves_events() -> None:
    events = _events()
    restored = load_log(dump_log(events))
    assert restored == tuple(events)
    assert [type(e).__name__ for e in restored] == [
        "EngagementCreated",
        "EvidenceAdded",
    ]
    assert [e.metadata.seq for e in restored] == [1, 2]


def test_log_is_ndjson_one_line_per_event() -> None:
    text = dump_log(_events())
    assert text.endswith("\n")
    assert len(text.rstrip("\n").split("\n")) == 2


def test_empty_log_round_trips_to_empty_tuple() -> None:
    assert dump_log([]) == ""
    assert load_log("") == ()
    assert load_log(dump_log([])) == ()


# --- snapshot / manifest codecs ----------------------------------------------


def test_snapshot_round_trip() -> None:
    state = _state()
    assert load_snapshot(dump_snapshot(state)) == state


def test_manifest_round_trip_and_fields() -> None:
    assert set(Manifest.model_fields) == {
        "format_version",
        "log_sha256",
        "snapshot_sha256",
    }
    assert load_manifest(dump_manifest(_manifest())) == _manifest()


# --- error ownership: malformed input → CorruptArtifactError ------------------


def test_malformed_log_line_raises_corrupt() -> None:
    with pytest.raises(CorruptArtifactError):
        load_log('{"not":"an event"}\n')
    with pytest.raises(CorruptArtifactError):
        load_log("{ broken json\n")


def test_blank_interior_line_raises_corrupt() -> None:
    good = _events()[0].model_dump_json()
    with pytest.raises(CorruptArtifactError):
        load_log(f"{good}\n\n{good}\n")


def test_malformed_snapshot_raises_corrupt() -> None:
    with pytest.raises(CorruptArtifactError):
        load_snapshot("not json at all")
    with pytest.raises(CorruptArtifactError):
        load_snapshot('{"missing":"metadata"}')


def test_malformed_manifest_raises_corrupt() -> None:
    with pytest.raises(CorruptArtifactError):
        load_manifest("not json")
    with pytest.raises(CorruptArtifactError):  # bad sha (schema validation)
        load_manifest('{"format_version":1,"log_sha256":"short","snapshot_sha256":"x"}')
    with pytest.raises(CorruptArtifactError):  # extra field (extra=forbid)
        load_manifest(
            '{"format_version":1,"log_sha256":"'
            + _SHA
            + '","snapshot_sha256":"'
            + _SHA2
            + '","extra":1}'
        )
