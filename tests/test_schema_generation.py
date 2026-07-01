"""Guard against schema drift: the committed JSON Schema must equal the generated one.

This enforces the rule that JSON Schema is generated from Pydantic, not edited by
hand. If this fails, run ``make schema`` and commit the result.
"""

from __future__ import annotations

import json
from pathlib import Path

from state.schema import engagement_state_json_schema

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schema" / "engagement-state.schema.json"
)


def test_committed_schema_matches_models() -> None:
    committed = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert (
        committed == engagement_state_json_schema()
    ), "schema/engagement-state.schema.json is stale; run `make schema` and commit."
