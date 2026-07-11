#!/usr/bin/env python3
"""Append one telemetry event from the command line (v1.0 Observability).

This is the bridge the live (markdown/LLM) ``solve-case`` orchestrator uses to
emit telemetry: at each phase it shells out to this script, which appends a
structured event to ``telemetry/<engagement_id>.jsonl``. That is how a
prompt-driven orchestrator "instruments every agent" without agent code.

Example:
    uv run python scripts/record_telemetry.py \
        --engagement eng_x --agent financial-analyst --phase analysis \
        --status finished --duration-ms 85936 --confidence 0.5 \
        --frameworks profit-tree,contribution-margin-analysis --tokens 12596
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parent.parent / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from telemetry import (  # noqa: E402
    EventStatus,
    JSONLSink,
    Phase,
    Recorder,
    ValidationStatus,
)


def _parse_meta(pairs: list[str]) -> dict[str, object]:
    meta: dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"--meta must be key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        meta[key] = value
    return meta


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Append one StratAgent telemetry event.")
    p.add_argument("--engagement", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--phase", required=True, choices=[e.value for e in Phase])
    p.add_argument("--status", required=True, choices=[e.value for e in EventStatus])
    p.add_argument("--duration-ms", type=float, default=None)
    p.add_argument("--confidence", type=float, default=None)
    p.add_argument("--frameworks", default="", help="comma-separated")
    p.add_argument("--tokens", type=int, default=None)
    p.add_argument("--retry", type=int, default=0)
    p.add_argument(
        "--validation-status",
        default=None,
        choices=[e.value for e in ValidationStatus],
    )
    p.add_argument("--meta", action="append", default=[], help="key=value (repeatable)")
    p.add_argument("--root", default="telemetry")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    frameworks = tuple(f for f in args.frameworks.split(",") if f)
    recorder = Recorder(JSONLSink(root=args.root))
    event = recorder.emit(
        engagement_id=args.engagement,
        agent_name=args.agent,
        phase=Phase(args.phase),
        status=EventStatus(args.status),
        duration_ms=args.duration_ms,
        confidence=args.confidence,
        frameworks_used=frameworks,
        tokens=args.tokens,
        retry_count=args.retry,
        validation_status=(
            ValidationStatus(args.validation_status) if args.validation_status else None
        ),
        metadata=_parse_meta(args.meta),
    )
    if event is not None:
        print(f"recorded {event.agent_name}:{event.phase.value} [{event.status.value}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
