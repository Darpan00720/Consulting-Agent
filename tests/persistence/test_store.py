"""M1.8-S4 EngagementStore tests: save/load orchestration invariants S4-1..S4-16.

Deterministic only. Interrupted saves use monkeypatch, never process kills.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

import persistence.store as store_module
from persistence import (
    CorruptArtifactError,
    EngagementStore,
    IncompatibleVersionError,
    MissingArtifactError,
    TornWriteError,
)
from persistence.atomic import atomic_write as _real_atomic_write
from persistence.format import (
    Manifest,
    dump_log,
    dump_manifest,
    dump_snapshot,
    load_log,
    load_snapshot,
)
from persistence.paths import (
    EVENTS_LOG_FILENAME,
    MANIFEST_FILENAME,
    SNAPSHOT_FILENAME,
)
from state import Engagement, Evidence, EvidenceType
from state.append import ReplayIntegrityError, verify_pair
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.projection import PROJECTION_VERSION, project

_STATE_DIR = Path(store_module.__file__).parent.parent / "state"


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _engagement(slug: str = "demo") -> Engagement:
    e = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug=slug)
    events: list[Event] = [
        EngagementCreated(metadata=_meta(), slug=slug, tenant_id="t_1"),
        EvidenceAdded(
            metadata=_meta(),
            evidence=Evidence(claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5),
        ),
    ]
    e.append_events(events, expected_version=0)
    return e


def _committed_bytes(engagement: Engagement) -> tuple[bytes, bytes]:
    """Canonical persisted bytes: (log, project(log)) — the form store writes."""
    committed = engagement._pipeline.committed()
    return (
        dump_log(committed.log).encode("utf-8"),
        dump_snapshot(project(committed.log)).encode("utf-8"),
    )


def _write_set(
    directory: Path,
    *,
    log_bytes: bytes,
    state_bytes: bytes,
    log_sha: str | None = None,
    state_sha: str | None = None,
    format_version: int = 1,
) -> None:
    """Write a raw persistence set (test-only) with chosen/derived checksums."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / EVENTS_LOG_FILENAME).write_bytes(log_bytes)
    (directory / SNAPSHOT_FILENAME).write_bytes(state_bytes)
    manifest = Manifest(
        format_version=format_version,
        log_sha256=log_sha or hashlib.sha256(log_bytes).hexdigest(),
        snapshot_sha256=state_sha or hashlib.sha256(state_bytes).hexdigest(),
    )
    (directory / MANIFEST_FILENAME).write_text(
        dump_manifest(manifest), encoding="utf-8"
    )


# --- S4-1 / S4-2 -------------------------------------------------------------


def test_s4_1_save_creates_complete_set(tmp_path: Path) -> None:
    EngagementStore(tmp_path).save(_engagement())
    d = tmp_path / "demo"
    assert (d / EVENTS_LOG_FILENAME).exists()
    assert (d / SNAPSHOT_FILENAME).exists()
    assert (d / MANIFEST_FILENAME).exists()


def test_s4_2_load_reconstructs_canonical_engagement(tmp_path: Path) -> None:
    """Canonical engagement semantics (M1.8-S4 projection decision): the event
    log, the domain state, and the version are preserved exactly; only the
    projection *provenance* is normalized to ``PROJECTION_VERSION``. Runtime
    ``committed.state`` (built directly, ``projection_version == 0``) is an
    implementation detail — the persisted representation is ``project(log)``.
    """
    store = EngagementStore(tmp_path)
    original = _engagement()
    store.save(original)
    loaded = store.load("demo")

    # event log preserved exactly
    assert loaded._pipeline.committed().log == original._pipeline.committed().log
    # version preserved exactly
    assert loaded.current_version() == original.current_version()
    # projection provenance normalized: runtime built state directly (0),
    # the persisted/loaded state is the canonical projection (PROJECTION_VERSION)
    assert original.get_state().projection_version == 0
    assert loaded.get_state().projection_version == PROJECTION_VERSION
    # domain/business state identical modulo the normalized provenance stamp
    normalized_original = original.get_state().model_copy(
        update={"projection_version": PROJECTION_VERSION}
    )
    assert loaded.get_state() == normalized_original


# --- S4-3 deterministic persistence (PER-011) --------------------------------


def test_s4_3_save_load_save_is_byte_identical(tmp_path: Path) -> None:
    root1, root2 = tmp_path / "r1", tmp_path / "r2"
    EngagementStore(root1).save(_engagement())
    reloaded = EngagementStore(root1).load("demo")
    EngagementStore(root2).save(reloaded)
    for name in (EVENTS_LOG_FILENAME, SNAPSHOT_FILENAME, MANIFEST_FILENAME):
        assert (root1 / "demo" / name).read_bytes() == (
            root2 / "demo" / name
        ).read_bytes()


# --- S4-4..S4-9 rejection paths ----------------------------------------------


def test_s4_4_checksum_corruption_rejected(tmp_path: Path) -> None:
    store = EngagementStore(tmp_path)
    store.save(_engagement())
    (tmp_path / "demo" / EVENTS_LOG_FILENAME).write_bytes(
        b"tampered\n"
    )  # manifest stale
    with pytest.raises(CorruptArtifactError):
        store.load("demo")


def test_s4_5_malformed_log_rejected(tmp_path: Path) -> None:
    _, state_bytes = _committed_bytes(_engagement())
    _write_set(tmp_path / "demo", log_bytes=b"not-an-event\n", state_bytes=state_bytes)
    with pytest.raises(CorruptArtifactError):
        EngagementStore(tmp_path).load("demo")


def test_s4_6_malformed_snapshot_rejected(tmp_path: Path) -> None:
    log_bytes, _ = _committed_bytes(_engagement())
    _write_set(tmp_path / "demo", log_bytes=log_bytes, state_bytes=b"{not json}")
    with pytest.raises(CorruptArtifactError):
        EngagementStore(tmp_path).load("demo")


def test_s4_7_unsupported_format_rejected(tmp_path: Path) -> None:
    log_bytes, state_bytes = _committed_bytes(_engagement())
    _write_set(
        tmp_path / "demo",
        log_bytes=log_bytes,
        state_bytes=state_bytes,
        format_version=99,
    )
    with pytest.raises(IncompatibleVersionError):
        EngagementStore(tmp_path).load("demo")


def test_s4_8_missing_artifact_rejected(tmp_path: Path) -> None:
    with pytest.raises(MissingArtifactError):
        EngagementStore(tmp_path).load("never-saved")


def test_s4_9_torn_persistence_rejected(tmp_path: Path) -> None:
    # manifest missing but other files present → partial → torn
    d = tmp_path / "demo"
    d.mkdir(parents=True)
    (d / EVENTS_LOG_FILENAME).write_bytes(b"x\n")
    with pytest.raises(TornWriteError):
        EngagementStore(tmp_path).load("demo")
    # manifest present but a referenced file missing → torn
    d2 = tmp_path / "demo2"
    log_bytes, state_bytes = _committed_bytes(_engagement("demo2"))
    _write_set(d2, log_bytes=log_bytes, state_bytes=state_bytes)
    (d2 / SNAPSHOT_FILENAME).unlink()
    with pytest.raises(TornWriteError):
        EngagementStore(tmp_path).load("demo2")


# --- S4-10 / S4-11 integrity propagation -------------------------------------


def test_s4_10_verify_log_failure_propagates(tmp_path: Path) -> None:
    # a log that passes checksum but fails verify_log (no genesis first)
    lone = EvidenceAdded(
        metadata=_meta(seq=1),
        evidence=Evidence(claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5),
    )
    _, state_bytes = _committed_bytes(_engagement())
    _write_set(
        tmp_path / "demo",
        log_bytes=dump_log([lone]).encode("utf-8"),
        state_bytes=state_bytes,
    )
    with pytest.raises(ReplayIntegrityError):
        EngagementStore(tmp_path).load("demo")


def test_s4_11_verify_pair_failure_propagates(tmp_path: Path) -> None:
    # canonical snapshot (passes the projection check) whose state_version alone
    # disagrees with the log → verify_pair fails specifically on that mismatch
    e = _engagement()
    log = e._pipeline.committed().log
    canonical = project(log)
    wrong = canonical.model_copy(
        update={"metadata": canonical.metadata.model_copy(update={"state_version": 99})}
    )
    _write_set(
        tmp_path / "demo",
        log_bytes=dump_log(log).encode("utf-8"),
        state_bytes=dump_snapshot(wrong).encode("utf-8"),
    )
    with pytest.raises(ReplayIntegrityError):
        EngagementStore(tmp_path).load("demo")


# --- S4-12 append-capable ----------------------------------------------------


def test_s4_12_loaded_engagement_is_append_capable(tmp_path: Path) -> None:
    store = EngagementStore(tmp_path)
    store.save(_engagement())
    loaded = store.load("demo")
    version = loaded.current_version()
    result = loaded.append_event(
        EvidenceAdded(
            metadata=_meta(),
            evidence=Evidence(
                claim="more", type=EvidenceType.CLIENT_FACT, confidence=0.6
            ),
        ),
        expected_version=version,
    )
    assert result.version == version + 1


# --- S4-13 / S4-14 ownership source-scans ------------------------------------


def test_s4_13_only_store_imports_hashlib() -> None:
    persistence_dir = Path(store_module.__file__).parent
    for module in sorted(persistence_dir.glob("*.py")):
        src = module.read_text(encoding="utf-8")
        if module.name == "store.py":
            assert "hashlib" in src
        else:
            assert "hashlib" not in src, f"{module.name} must not import hashlib"
    # packages/state/** must not import hashlib either
    for module in _STATE_DIR.rglob("*.py"):
        assert "hashlib" not in module.read_text(encoding="utf-8"), module


def test_s4_14_only_store_orchestrates_persistence() -> None:
    persistence_dir = Path(store_module.__file__).parent
    orchestration = ("AppendPipeline", "verify_log", "verify_pair", "state.facade")
    store_src = (persistence_dir / "store.py").read_text(encoding="utf-8")
    for token in orchestration:
        assert token in store_src
    for module in ("format.py", "atomic.py", "paths.py"):
        src = (persistence_dir / module).read_text(encoding="utf-8")
        for token in ("AppendPipeline", "verify_log", "verify_pair"):
            assert token not in src, f"{module} must not orchestrate ({token})"


# --- S4-15 interrupted save never exposes partial persistence ----------------


def test_s4_15_interrupted_save_never_loadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EngagementStore(tmp_path)
    calls = {"n": 0}

    def _fail_on_manifest(path: Path, data: bytes) -> None:
        calls["n"] += 1
        if path.name == MANIFEST_FILENAME:
            raise OSError("simulated crash before the manifest commit")
        _real_atomic_write(path, data)  # let events.log / state.json land

    monkeypatch.setattr(store_module, "atomic_write", _fail_on_manifest)
    with pytest.raises(TornWriteError):
        store.save(_engagement())
    monkeypatch.undo()
    # log + state landed, manifest did not → load must refuse (torn), never partial
    assert not (tmp_path / "demo" / MANIFEST_FILENAME).exists()
    with pytest.raises(TornWriteError):
        store.load("demo")


# --- S4-16 projection provenance normalized on persist (decision record) -----


def test_s4_16_projection_provenance_normalized_on_persist(tmp_path: Path) -> None:
    """Permanent record of the M1.8-S4 projection decision.

    runtime committed.state (projection_version == 0)
        ↓ save()
    persisted state.json has projection_version == PROJECTION_VERSION
        ↓ load()
    verify_pair(log, persisted_state) succeeds — no replay, no repair.
    """
    store = EngagementStore(tmp_path)
    original = _engagement()
    # runtime incremental state is built directly and carries stale provenance
    assert original.get_state().projection_version == 0

    store.save(original)

    # the persisted snapshot is normalized to the canonical PROJECTION_VERSION
    raw_snapshot = (tmp_path / "demo" / SNAPSHOT_FILENAME).read_bytes()
    persisted = load_snapshot(raw_snapshot.decode("utf-8"))
    assert persisted.projection_version == PROJECTION_VERSION

    # the persisted (log, snapshot) pair satisfies frozen verify_pair as-is
    raw_log = (tmp_path / "demo" / EVENTS_LOG_FILENAME).read_bytes()
    log = load_log(raw_log.decode("utf-8"))
    verify_pair(log, persisted)  # must not raise — no reprojection needed

    # and load reconstructs the canonical engagement end to end
    loaded = store.load("demo")
    assert loaded.get_state().projection_version == PROJECTION_VERSION


# --- coverage: wrapped OS/decode errors, slug guard --------------------------


def test_load_wraps_unexpected_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = EngagementStore(tmp_path)
    store.save(_engagement())

    def _boom(path: Path) -> bytes:
        raise OSError("permission denied")

    monkeypatch.setattr(store_module, "read_bytes", _boom)
    with pytest.raises(CorruptArtifactError):
        store.load("demo")


def test_load_wraps_non_utf8_manifest(tmp_path: Path) -> None:
    d = tmp_path / "demo"
    d.mkdir(parents=True)
    (d / MANIFEST_FILENAME).write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(CorruptArtifactError):
        EngagementStore(tmp_path).load("demo")


def test_unsafe_slug_rejected(tmp_path: Path) -> None:
    store = EngagementStore(tmp_path)
    for bad in ("", "..", "a/b", "../evil"):
        with pytest.raises(ValueError, match="unsafe"):
            store.load(bad)
