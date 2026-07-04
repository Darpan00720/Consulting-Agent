"""M1.8-S3 atomic-primitive tests: visibility, single-authority, byte preservation.

Byte-level only — no serialization/hashing/store. Interrupted writes are
simulated with monkeypatch (deterministic), never real process termination.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import persistence.atomic as atomic
from persistence.atomic import append_bytes, atomic_write, read_bytes
from persistence.errors import MissingArtifactError

_PERSISTENCE_DIR = Path(atomic.__file__).parent


# --- PER-017 byte preservation -----------------------------------------------


@pytest.mark.parametrize(
    "data", [b"", b"hello", b"\x00\x01\xff\xfe", "café ☕".encode()]
)
def test_per_017_byte_preservation(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "artifact"
    atomic_write(path, data)
    assert read_bytes(path) == data


# --- PER-015 atomic visibility -----------------------------------------------


def test_per_015_failure_before_commit_leaves_previous_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "artifact"
    atomic_write(path, b"OLD")  # previous complete artifact

    def _boom(src: str, dst: str) -> None:
        raise OSError("simulated crash before atomic commit")

    monkeypatch.setattr("os.replace", _boom)
    with pytest.raises(OSError, match="before atomic commit"):
        atomic_write(path, b"NEW-would-be-partial")
    monkeypatch.undo()

    # reader sees the PREVIOUS complete artifact, never a mixture …
    assert read_bytes(path) == b"OLD"
    # … and no stray temp file was left behind
    assert list(tmp_path.glob("*.tmp")) == []


def test_per_015_success_commits_new_artifact(tmp_path: Path) -> None:
    path = tmp_path / "artifact"
    atomic_write(path, b"v1")
    atomic_write(path, b"v2-longer")
    assert read_bytes(path) == b"v2-longer"
    assert list(tmp_path.glob("*.tmp")) == []


# --- PER-016 single atomic authority -----------------------------------------


def test_per_016_only_atomic_module_performs_atomic_ops() -> None:
    banned = ("os.replace", "os.rename", "fsync", "mkstemp", "NamedTemporaryFile")
    for module in sorted(_PERSISTENCE_DIR.glob("*.py")):
        src = module.read_text(encoding="utf-8")
        if module.name == "atomic.py":
            # atomic.py IS the authority — it must use these
            assert "os.replace" in src
            assert "mkstemp" in src
            assert "fsync" in src
        else:
            for token in banned:
                assert token not in src, f"{module.name} must not perform {token!r}"


# --- append + read primitives ------------------------------------------------


def test_append_bytes_is_durable_and_ordered(tmp_path: Path) -> None:
    path = tmp_path / "events.log"
    append_bytes(path, b"a\n")
    append_bytes(path, b"b\n")
    append_bytes(path, b"c\n")
    assert read_bytes(path) == b"a\nb\nc\n"


def test_read_missing_artifact_raises(tmp_path: Path) -> None:
    with pytest.raises(MissingArtifactError):
        read_bytes(tmp_path / "does-not-exist")


def test_atomic_module_does_not_serialize_or_hash() -> None:
    # responsibility split: atomic.py works in bytes only
    src = (_PERSISTENCE_DIR / "atomic.py").read_text(encoding="utf-8")
    for banned in ("model_dump", "model_validate", "hashlib", "hexdigest", "json"):
        assert banned not in src, f"atomic.py must be bytes-only; found {banned!r}"
