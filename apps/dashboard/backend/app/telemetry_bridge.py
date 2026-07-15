"""Bridge from the dashboard to the frozen telemetry core (`packages/telemetry`).

Why this exists
---------------
ADR-008 keeps `packages/` as a frozen reference core with no production
consumer. Telemetry was the one subsystem in it that the shipping product
genuinely needed and did not have: before this module, the dashboard emitted
**no** operational telemetry at all, and incidents were diagnosed by reading
`docker logs`. Rather than duplicate 900 lines, the dashboard imports the real
package — the first live code seam between the two artifacts.

Domain events vs telemetry
--------------------------
These are deliberately separate and must stay separate (ADR-002 /
docs/observability):

* the **domain event log** (`db.append_event`) is the engagement's own history —
  it is replayed to rebuild state and drives the UI. It is a product feature.
* **telemetry** is operational: durations, retries, provider, failures. It is
  for operators, is sampled, is redacted, and may be dropped without affecting
  the engagement. Nothing here may become load-bearing for the product.

Path bootstrap
--------------
The dashboard is a separate uv project, so `telemetry` is not a declared
dependency. It is made importable in two ways, matching how `config.py` already
reaches the plugin's `agents/*.md`:
  * in Docker the package is COPYied to `/app/telemetry` (see Dockerfile);
  * in a source checkout the repo-root `packages/` dir is appended to sys.path.
If neither works, telemetry degrades to a no-op rather than breaking a run —
observability must never be the reason an engagement fails.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app import config

log = logging.getLogger(__name__)


def _bootstrap_path() -> None:
    """Make `packages/` importable from a source checkout (no-op in Docker)."""
    try:
        repo_packages = Path(__file__).resolve().parents[4] / "packages"
    except IndexError:  # pragma: no cover - depends on install layout
        return
    if repo_packages.is_dir() and str(repo_packages) not in sys.path:
        sys.path.append(str(repo_packages))


_bootstrap_path()

try:
    from telemetry import (
        EventStatus,
        JSONLSink,
        NullSink,
        Phase,
        Recorder,
        ValidationStatus,
    )

    TELEMETRY_AVAILABLE = True
except ImportError:  # pragma: no cover - only when the core isn't on the path
    TELEMETRY_AVAILABLE = False
    log.warning(
        "telemetry core not importable — engagements will run without "
        "operational telemetry (this is degraded, not fatal)"
    )


# The dashboard's phase names map onto the core's Phase enum. `reconcile` has no
# 1:1 member — it is engagement-manager orchestration, so it maps to
# ORCHESTRATION. Anything unmapped also falls back to ORCHESTRATION rather than
# raising: an unknown phase must not break a run.
_PHASE_MAP: dict[str, str] = {
    "classify": "CLASSIFY",
    "gap_analysis": "GAP_ANALYSIS",
    "planning": "PLANNING",
    "framing": "FRAMING",
    "issue_tree": "ISSUE_TREE",
    "analysis": "ANALYSIS",
    "reconcile": "ORCHESTRATION",
    "review": "REVIEW",
    "challenge": "CHALLENGE",
    "reporting": "REPORTING",
}

_recorder: Any | None = None


def recorder() -> Any | None:
    """Lazy singleton Recorder, or None when telemetry is unavailable/disabled.

    Writes one JSONL file per engagement under ``STRATAGENT_TELEMETRY_DIR``.
    Sampling and the kill switch come from config so an operator can turn this
    down without a redeploy.
    """
    global _recorder
    if not TELEMETRY_AVAILABLE or not config.TELEMETRY_ENABLED:
        return None
    if _recorder is None:
        try:
            sink = (
                JSONLSink(config.TELEMETRY_DIR) if config.TELEMETRY_DIR else NullSink()
            )
            _recorder = Recorder(sink, sample_rate=config.TELEMETRY_SAMPLE_RATE)
        except Exception:  # noqa: BLE001 - telemetry must never break a run
            log.exception("telemetry recorder init failed; continuing without it")
            return None
    return _recorder


def reset_for_tests() -> None:
    global _recorder
    _recorder = None


def _phase(name: str) -> Any:
    return getattr(Phase, _PHASE_MAP.get(name, "ORCHESTRATION"))


@contextmanager
def span(engagement_id: str, agent_name: str, phase_name: str) -> Iterator[Any]:
    """Time one unit of work, emitting STARTED then FINISHED/FAILED.

    A sync context manager around an ``await`` is correct here: ``__exit__``
    runs once the awaited call resolves, so the duration is the real wall time.
    Yields the core's SpanHandle (or None) so callers may attach signals.

    Two exception sources are deliberately treated differently:
      * the **body** raising (the real work failed) — always propagates;
      * the **telemetry machinery** raising (sink full, disk error) — swallowed
        and logged. Observability may never be the reason an engagement dies,
        so the span is driven manually rather than with `with`, which would
        conflate the two.
    """
    rec = recorder()
    cm: Any | None = None
    handle: Any = None
    if rec is not None:
        try:
            cm = rec.span(
                engagement_id=engagement_id,
                agent_name=agent_name,
                phase=_phase(phase_name),
            )
            handle = cm.__enter__()
        except Exception:  # noqa: BLE001 - telemetry must not break the run
            log.exception("telemetry span failed to start; continuing without it")
            cm = None
    try:
        yield handle
    except BaseException as exc:
        if cm is not None:
            try:
                cm.__exit__(type(exc), exc, exc.__traceback__)
            except Exception:  # noqa: BLE001
                log.exception("telemetry span teardown failed; continuing")
        raise  # the real error always wins
    else:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                log.exception("telemetry span teardown failed; continuing")


def attach(
    handle: Any,
    *,
    validation_status: str | None = None,
    **metadata: Any,
) -> None:
    """Attach signals to an open span, so they ride its ONE terminal event.

    Use this instead of a second ``emit`` for something the span already covers:
    a separate event would double-count in the core's analytics (two terminal
    REVIEW events, only one carrying a verdict, halves reviewer_pass_rate).
    Takes plain strings; the enum conversion stays inside this bridge.
    """
    if handle is None:
        return
    try:
        if validation_status is not None:
            handle.set(
                validation_status=getattr(ValidationStatus, validation_status.upper()),
                **metadata,
            )
        else:
            handle.set(**metadata)
    except Exception:  # noqa: BLE001 - observability must not break the product
        log.exception("telemetry attach failed; continuing")


def emit(
    engagement_id: str,
    agent_name: str,
    phase_name: str,
    status: str,
    *,
    validation_status: str | None = None,
    **kw: Any,
) -> None:
    """Emit a point-in-time event. Never raises — telemetry is best-effort.

    Callers pass plain strings ("finished", "passed"); this bridge is the only
    place that knows the core's enums, so the engine never imports from
    `packages/` directly and the seam stays in one file.
    """
    rec = recorder()
    if rec is None:
        return
    try:
        if validation_status is not None:
            kw["validation_status"] = getattr(
                ValidationStatus, validation_status.upper()
            )
        rec.emit(
            engagement_id=engagement_id,
            agent_name=agent_name,
            phase=_phase(phase_name),
            status=getattr(EventStatus, status.upper()),
            **kw,
        )
    except Exception:  # noqa: BLE001 - observability must not break the product
        log.exception("telemetry emit failed; continuing")
