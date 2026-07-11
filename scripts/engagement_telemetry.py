#!/usr/bin/env python3
"""Summarize / export StratAgent telemetry (v1.0 Observability).

Reads the JSONL event store and emits dashboard-ready analytics as JSON, or
OpenTelemetry-compatible spans.

    uv run python scripts/engagement_telemetry.py --engagement eng_x
    uv run python scripts/engagement_telemetry.py --all --quality
    uv run python scripts/engagement_telemetry.py --engagement eng_x --otlp
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parent.parent / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from telemetry import (  # noqa: E402
    JSONLSink,
    engagement_analytics,
    quality_analytics,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Summarize/export StratAgent telemetry.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--engagement", help="one engagement_id")
    src.add_argument("--all", action="store_true", help="all engagements under root")
    p.add_argument("--quality", action="store_true", help="quality analytics")
    p.add_argument("--otlp", action="store_true", help="emit OTLP spans instead")
    p.add_argument("--root", default="telemetry")
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    sink = JSONLSink(root=args.root)
    events = list(sink.read_all()) if args.all else sink.read(args.engagement)

    if args.otlp:
        print(json.dumps([e.to_otlp() for e in events], indent=2))
        return 0

    if args.quality or args.all:
        print(json.dumps(asdict(quality_analytics(events)), indent=2, default=str))
    else:
        print(json.dumps(asdict(engagement_analytics(events)), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
