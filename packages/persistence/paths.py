"""Engagement storage-layout constants (M1.8-S1) — the on-disk format names.

The persistence package **exclusively owns** the ``engagements/<slug>/`` layout
(DD-4): no other package may depend on these names. This module is **constants
only** — no filesystem access, no validation, no IO (those arrive in later
slices). Layout:

    <root>/<slug>/
        events.log      append-only NDJSON event log
        state.json      EngagementState snapshot
        manifest.json   persistence metadata (format version + checksums)
"""

from __future__ import annotations

from typing import Final

#: Default root directory holding one folder per engagement.
ENGAGEMENTS_DIRNAME: Final = "engagements"

#: Append-only NDJSON event log (one Event per line, seq order).
EVENTS_LOG_FILENAME: Final = "events.log"

#: EngagementState snapshot (facade ``to_json`` output).
SNAPSHOT_FILENAME: Final = "state.json"

#: Persistence metadata: format version + integrity checksums (DD-2).
MANIFEST_FILENAME: Final = "manifest.json"

#: On-disk layout version (the store's own format, not a domain version).
STORE_FORMAT_VERSION: Final = 1
