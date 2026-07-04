"""Atomic filesystem primitives — the sole IO-authority module (M1.8-S3).

This is the **only** persistence module permitted to create temp files, call
``fsync``, or perform ``os.replace``/``rename`` (PER-016). It works
**exclusively with bytes** — it never understands JSON, events,
``EngagementState``, or manifests, never computes checksums, and never
constructs engagements (those belong to ``format`` / the store).

Atomic write protocol (PER-015 — atomic visibility):

    temp file (same dir) → write → flush → fsync → os.replace → fsync(dir)

Because ``os.replace`` is atomic on POSIX, a reader observes **either** the
previous complete file **or** the new one — never a mixture. On any failure
before ``replace``, the target is untouched and the temp is removed (no stray
temp, no partial target). The directory fsync makes the rename itself durable.

**Crash boundary:** a crash before ``replace`` leaves the old file intact and
at worst an orphaned ``*.tmp`` that nothing references (the store never reads
temp files); a crash after ``replace`` leaves the new file. There is no
in-between visible state.

**Portability:** POSIX ``os.replace`` + directory fsync are assumed (dev target
macOS/Linux); Windows rename semantics differ [noted in the M1.8 design risks].

Error ownership: absent-file reads raise ``MissingArtifactError`` (the one clean
taxonomy mapping); other raw OS errors propagate after atomicity is preserved,
for the store (S4) to surface — this module never invents error mappings.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from persistence.errors import MissingArtifactError


def atomic_write(path: Path, data: bytes) -> None:
    """Atomically replace ``path`` with ``data`` (PER-015/PER-017). O(len(data)).

    The parent directory must already exist — directory creation is the store's
    responsibility, not this primitive's.
    """
    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=f"{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)  # atomic commit
    except BaseException:
        tmp.unlink(missing_ok=True)  # never leave a stray temp behind
        raise
    _fsync_dir(parent)


def append_bytes(path: Path, data: bytes) -> None:
    """Durably append ``data`` to ``path`` (created if absent), then fsync.

    O(len(data)). The parent directory must already exist.
    """
    with open(path, "ab") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def read_bytes(path: Path) -> bytes:
    """Read all bytes of ``path``. O(size). Absent → ``MissingArtifactError``."""
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise MissingArtifactError(f"missing artifact: {path}") from exc


def _fsync_dir(directory: Path) -> None:
    """fsync a directory so a completed rename is itself durable."""
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
