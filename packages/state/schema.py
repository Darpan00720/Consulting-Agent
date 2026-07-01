"""Generate the canonical Engagement State JSON Schema from the Pydantic models.

Per ADR-002 (as refined): JSON Schema is GENERATED from Pydantic and never
hand-maintained. ``scripts/generate_schema.py`` writes the rendered output to
``schema/engagement-state.schema.json``; a test guards against drift.
"""

from __future__ import annotations

import json
from typing import Any

from state.models import EngagementState


def engagement_state_json_schema() -> dict[str, Any]:
    """Return the JSON Schema for the Engagement State model."""
    return EngagementState.model_json_schema()


def render() -> str:
    """Render the schema as deterministic, sorted JSON text."""
    return json.dumps(engagement_state_json_schema(), indent=2, sort_keys=True) + "\n"
