"""M1.6 traceability tests: frozen rule ids, 1:1 Rule->Test, matrix freshness."""

from __future__ import annotations

import json
import re
from pathlib import Path

from state.validation import ALL_RULES

_ROOT = Path(__file__).resolve().parents[3]
_TESTS = _ROOT / "tests" / "state" / "validation"
_JSON = _ROOT / "docs" / "implementation" / "traceability.json"


def test_rule_ids_are_unique() -> None:
    ids = [rule.rule_id for rule in ALL_RULES]
    assert len(ids) == len(set(ids))


def test_rule_ids_are_well_formed() -> None:
    pattern = re.compile(r"^[A-Z]+-\d{3}$")
    for rule in ALL_RULES:
        assert pattern.match(rule.rule_id), rule.rule_id


def test_every_rule_has_a_test() -> None:
    sources = "\n".join(p.read_text(encoding="utf-8") for p in _TESTS.glob("*.py"))
    for rule in ALL_RULES:
        slug = rule.rule_id.lower().replace("-", "_")
        assert re.search(
            rf"def test_{slug}\w*\(", sources
        ), f"no test for {rule.rule_id}"


def test_traceability_json_is_fresh() -> None:
    committed = json.loads(_JSON.read_text(encoding="utf-8"))
    assert {row["rule_id"] for row in committed} == {r.rule_id for r in ALL_RULES}
