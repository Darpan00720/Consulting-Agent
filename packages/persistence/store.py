"""EngagementStore — save/load orchestration (M1.8-S4).

The store is the persistence package's public entry point. It **composes** the
lower layers and never duplicates their logic:

- serialization → ``format`` (S2)
- atomic byte IO → ``atomic`` (S3)
- log/pair integrity → ``verify_log`` / ``verify_pair`` (M1.7.4)
- reconstruction → ``AppendPipeline`` (M1.7.3), the sole rebuild path

The store **exclusively owns**: directory creation, SHA-256 computation (only
this module imports ``hashlib``), serialization orchestration, atomic-write
orchestration, load orchestration, and engagement reconstruction.

**Canonical persistence representation.** The persisted snapshot is the
canonical projection ``project(log)``, **not** the runtime ``committed.state``.
Runtime incremental state is an implementation detail: ``apply`` stamps only
``state_version`` and inherits ``projection_version`` from ``create`` (which
leaves it 0), so a live snapshot carries stale projection provenance. Save
therefore normalizes the snapshot through the projection engine
(``projection_version`` → ``PROJECTION_VERSION``) before serialization. This
guarantees that every persisted ``(log, snapshot)`` pair satisfies
``verify_pair`` without any replay or repair during load — no bypass, no
relaxation of replay integrity, and ``verify_pair`` remains frozen and
unchanged (M1.8-S4 projection decision).

Save workflow (fixed order): read committed log → build canonical snapshot
``project(log)`` → compute SHA-256 → serialize log/state/manifest →
atomic-write ``events.log`` → ``state.json`` → ``manifest.json``. **The
manifest is always written last** — its presence and matching checksums are the
commit marker (a crash before it leaves the set detectably incomplete, never
"partially persisted"; PER-012).

Load workflow (fixed order): read manifest → state → log → verify SHA-256 →
decode → ``verify_log`` → ``verify_pair`` → ``AppendPipeline(state, log=…,
append_supported=True)`` → return ``Engagement``. No alternate construction, no
reprojection.

Error ownership: missing → ``MissingArtifactError``; malformed JSON/NDJSON or
checksum mismatch → ``CorruptArtifactError``; unsupported version →
``IncompatibleVersionError``; manifest missing/partial → ``TornWriteError``;
any unexpected ``OSError`` is wrapped into the persistence hierarchy (never
leaked raw), preserving ``__cause__``.

Reads the committed log via ``engagement._pipeline.committed()`` — the single
approved consumer of that internal seam (P-DD-A); no new facade accessor.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from persistence.atomic import atomic_write, read_bytes
from persistence.errors import (
    CorruptArtifactError,
    IncompatibleVersionError,
    MissingArtifactError,
    TornWriteError,
)
from persistence.format import (
    Manifest,
    dump_log,
    dump_manifest,
    dump_snapshot,
    load_log,
    load_manifest,
    load_snapshot,
)
from persistence.paths import (
    EVENTS_LOG_FILENAME,
    MANIFEST_FILENAME,
    SNAPSHOT_FILENAME,
    STORE_FORMAT_VERSION,
)
from state.append import AppendPipeline, verify_log, verify_pair
from state.facade import Engagement
from state.projection import project


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class EngagementStore:
    """Durable file-backed save/load for engagements under a root directory."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _engagement_dir(self, slug: str) -> Path:
        if not slug or slug in {".", ".."} or slug != Path(slug).name:
            raise ValueError(f"unsafe engagement slug: {slug!r}")
        return self._root / slug

    def save(self, engagement: Engagement) -> None:
        """Persist ``engagement`` atomically (manifest written last).

        The snapshot is the canonical projection ``project(log)`` — normalized
        through the projection engine so ``projection_version`` equals
        ``PROJECTION_VERSION`` and the persisted ``(log, snapshot)`` pair
        satisfies ``verify_pair`` on load without replay or repair.
        """
        committed = engagement._pipeline.committed()  # P-DD-A: sole consumer
        canonical_state = project(committed.log)  # normalize projection provenance
        slug = canonical_state.metadata.slug
        directory = self._engagement_dir(slug)

        log_bytes = dump_log(committed.log).encode("utf-8")
        snapshot_bytes = dump_snapshot(canonical_state).encode("utf-8")
        manifest_bytes = dump_manifest(
            Manifest(
                format_version=STORE_FORMAT_VERSION,
                log_sha256=_sha256(log_bytes),
                snapshot_sha256=_sha256(snapshot_bytes),
            )
        ).encode("utf-8")

        try:
            directory.mkdir(parents=True, exist_ok=True)
            atomic_write(directory / EVENTS_LOG_FILENAME, log_bytes)
            atomic_write(directory / SNAPSHOT_FILENAME, snapshot_bytes)
            atomic_write(directory / MANIFEST_FILENAME, manifest_bytes)
        except OSError as exc:  # incomplete write ⇒ not persisted (PER-012)
            raise TornWriteError(
                f"save did not complete for engagement {slug!r}: {exc}"
            ) from exc

    def load(self, slug: str) -> Engagement:
        """Load a persisted engagement, verified and append-capable."""
        directory = self._engagement_dir(slug)
        manifest_path = directory / MANIFEST_FILENAME
        state_path = directory / SNAPSHOT_FILENAME
        log_path = directory / EVENTS_LOG_FILENAME
        try:
            manifest = self._read_manifest(manifest_path, state_path, log_path)
            snapshot_bytes, log_bytes = self._read_payload(state_path, log_path)
            if (
                _sha256(log_bytes) != manifest.log_sha256
                or _sha256(snapshot_bytes) != manifest.snapshot_sha256
            ):
                raise CorruptArtifactError(f"checksum mismatch for {slug!r}")
            state = load_snapshot(snapshot_bytes.decode("utf-8"))
            log = load_log(log_bytes.decode("utf-8"))
            verify_log(log)
            verify_pair(log, state)
            pipeline = AppendPipeline(state, log=log, append_supported=True)
            return Engagement(pipeline)
        except (OSError, UnicodeDecodeError) as exc:  # never leak raw OSError
            raise CorruptArtifactError(
                f"could not read persisted engagement {slug!r}: {exc}"
            ) from exc

    @staticmethod
    def _read_manifest(
        manifest_path: Path, state_path: Path, log_path: Path
    ) -> Manifest:
        try:
            raw = read_bytes(manifest_path)
        except MissingArtifactError:
            if log_path.exists() or state_path.exists():
                raise TornWriteError(
                    f"manifest missing for a partially persisted engagement: "
                    f"{manifest_path.parent}"
                ) from None
            raise  # nothing persisted here
        manifest = load_manifest(raw.decode("utf-8"))
        if manifest.format_version != STORE_FORMAT_VERSION:
            raise IncompatibleVersionError(
                f"unsupported store format_version {manifest.format_version} "
                f"(supported: {STORE_FORMAT_VERSION})"
            )
        return manifest

    @staticmethod
    def _read_payload(state_path: Path, log_path: Path) -> tuple[bytes, bytes]:
        try:
            return read_bytes(state_path), read_bytes(log_path)
        except MissingArtifactError as exc:
            raise TornWriteError(
                f"manifest present but a referenced artifact is missing: {exc}"
            ) from exc
