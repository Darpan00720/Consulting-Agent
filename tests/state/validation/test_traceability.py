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
    assert {row["rule_id"] for row in committed["rules"]} == {
        r.rule_id for r in ALL_RULES
    }


def test_dispositions_cover_all_adr_items_exactly_once() -> None:
    committed = json.loads(_JSON.read_text(encoding="utf-8"))
    dispositions = committed["dispositions"]
    # ADR-002 §Validation Rules: 6 preconditions + 5 forbidden transitions
    # + 7 state invariants + 4 concurrency rules + 3 approval rules
    assert len(dispositions) == 25
    items = [d["adr_item"] for d in dispositions]
    assert len(items) == len(set(items)), "an ADR item is mapped twice"
    allowed = {
        "registry",
        "record-level",
        "boundary-write",
        "boundary-at-rest",
        "by-construction",
        "deferred",
    }
    assert {d["disposition"] for d in dispositions} <= allowed


def test_registry_dispositions_reference_live_rules() -> None:
    committed = json.loads(_JSON.read_text(encoding="utf-8"))
    live_ids = {r.rule_id for r in ALL_RULES}
    for entry in committed["dispositions"]:
        if entry["disposition"] != "registry":
            continue
        referenced = set(re.findall(r"\b[A-Z]+-\d{3}\b", entry["mechanism"]))
        assert referenced, f"registry row without a rule id: {entry['adr_item']}"
        assert referenced <= live_ids, f"stale rule ids in: {entry['mechanism']}"
