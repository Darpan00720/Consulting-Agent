"""Generate the ADR-002 traceability matrix (markdown + JSON) from the rule registry.

Run via ``make traceability``. One row per validation rule — **Rule → Validator →
Test(s)** — sourced from `state.validation.ALL_RULES` plus a scan of the validation
tests for slug-named test functions (`test_<rule_id>_...`). Guarded by
`tests/state/validation/test_traceability.py`.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from state.ownership import COMPONENT_OWNERSHIP, EVENT_OWNERSHIP, SECTION_OWNERSHIP
from state.validation import ALL_RULES

_ROOT = Path(__file__).resolve().parent.parent
_TESTS = _ROOT / "tests" / "state" / "validation"
_MD = _ROOT / "docs" / "implementation" / "traceability-ADR-002.md"
_JSON = _ROOT / "docs" / "implementation" / "traceability.json"


def _slug(rule_id: str) -> str:
    return rule_id.lower().replace("-", "_")


def _tests_for(rule_id: str) -> list[str]:
    pattern = re.compile(rf"def (test_{_slug(rule_id)}\w*)\(")
    found: list[str] = []
    for path in sorted(_TESTS.glob("*.py")):
        found.extend(pattern.findall(path.read_text(encoding="utf-8")))
    return found


def rows() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for rule in ALL_RULES:
        module = rule.validator.__module__.rsplit(".", 1)[-1]
        result.append(
            {
                "rule_id": rule.rule_id,
                "group": rule.group.value,
                "severity": rule.severity.value,
                "adr_reference": rule.adr_reference,
                "description": rule.description,
                "validator": f"{module}.{rule.validator.__name__}",
                "tests": _tests_for(rule.rule_id),
            }
        )
    return result


# ADR-002 §Validation Rules — disposition of EVERY line item, exactly once
# (TD-004, M1.7.5). Reviewed data: each item maps to a registry rule, a
# record-level constructor rule (M1.1), a boundary mechanism, enforcement by
# construction, or an explicit deferral with its owning milestone.
DISPOSITIONS: list[dict[str, str]] = [
    # -- Required fields (gate preconditions) --
    {
        "adr_item": "Enter Planning: archetype + real_question; "
        "load-bearing gaps answered/assumed",
        "disposition": "registry",
        "mechanism": "LIFE-005",
    },
    {
        "adr_item": "Enter Specialist Analysis: non-empty issue_tree + engagement_plan",
        "disposition": "registry",
        "mechanism": "LIFE-006 (leaf-owner half: STRUCT-001)",
    },
    {
        "adr_item": "Enter Reviewer: every leaf answered; findings carry evidence",
        "disposition": "registry",
        "mechanism": "LIFE-007 (finding-evidence half: STRUCT-002)",
    },
    {
        "adr_item": "Enter Challenger: review verdict approved",
        "disposition": "registry",
        "mechanism": "LIFE-008",
    },
    {
        "adr_item": "Generate Report: reviewer approved AND challenger stands",
        "disposition": "registry",
        "mechanism": "LIFE-001",
    },
    {
        "adr_item": "Complete: report deliverable + recommendation accepted",
        "disposition": "registry",
        "mechanism": "LIFE-002",
    },
    # -- Forbidden transitions --
    {
        "adr_item": "Reaching reporting without both gate approvals",
        "disposition": "registry",
        "mechanism": "LIFE-001",
    },
    {
        "adr_item": "Skipping review or challenge",
        "disposition": "registry",
        "mechanism": "LIFE-003 (legal-transition map)",
    },
    {
        "adr_item": "Mutating any section after status=completed",
        "disposition": "deferred",
        "mechanism": "append-boundary admission policy (EngagementReopened) — M1.8",
    },
    {
        "adr_item": "Editing or deleting any event",
        "disposition": "by-construction",
        "mechanism": "frozen event models; append-only committed log (M1.4/M1.7.3)",
    },
    {
        "adr_item": "A specialist writing another specialist's section",
        "disposition": "deferred",
        "mechanism": "R/W matrix data M1.7.6; role enforcement M6 (TD-003)",
    },
    # -- State invariants --
    {
        "adr_item": "Evidence type-specific provenance (source/method/ref)",
        "disposition": "record-level",
        "mechanism": "ledgers._EVIDENCE_RULES (M1.1)",
    },
    {
        "adr_item": "Every load-bearing assumption has a breakeven",
        "disposition": "record-level",
        "mechanism": "ledgers.Assumption._enforce_breakeven (M1.1)",
    },
    {
        "adr_item": "Every issue-tree leaf has exactly one owner",
        "disposition": "registry",
        "mechanism": "STRUCT-001",
    },
    {
        "adr_item": "recommendation.confidence <= min validated-evidence confidence",
        "disposition": "registry",
        "mechanism": "BIZ-001",
    },
    {
        "adr_item": "No recommendation without >=1 validated evidence",
        "disposition": "registry",
        "mechanism": "BIZ-002",
    },
    {
        "adr_item": "Every assumption_ref/evidence_ref resolves",
        "disposition": "registry",
        "mechanism": "REF-001, REF-002, REF-003, REF-004",
    },
    {
        "adr_item": "state_version == max(events.seq)",
        "disposition": "boundary-at-rest",
        "mechanism": "apply() stamp (M1.7.2) + verify_pair R11 (M1.7.4)",
    },
    # -- Concurrency rules --
    {
        "adr_item": "Writes are event appends with monotonic seq",
        "disposition": "boundary-write",
        "mechanism": "sequencing.stamp + pipeline (M1.7.3)",
    },
    {
        "adr_item": "Section ownership is exclusive",
        "disposition": "deferred",
        "mechanism": "R/W matrix data M1.7.6; enforcement M6",
    },
    {
        "adr_item": "Lifecycle transitions serialized through the Manager",
        "disposition": "deferred",
        "mechanism": "Engagement Manager — M6",
    },
    {
        "adr_item": "Optimistic concurrency: stale-version append rejected",
        "disposition": "boundary-write",
        "mechanism": "guard version compare (M1.7.3, D3)",
    },
    # -- Approval rules --
    {
        "adr_item": "Analysis gate only Reviewer; recommendation gate only "
        "Challenger; final acceptance Human",
        "disposition": "deferred",
        "mechanism": "role registry — M6 (TD-003; QualityGate.by already captured)",
    },
    {
        "adr_item": "No agent may approve its own output",
        "disposition": "deferred",
        "mechanism": "role registry — M6 (TD-003)",
    },
    {
        "adr_item": "A rejection must carry an actionable required_fix",
        "disposition": "registry",
        "mechanism": "GOV-002 (+GOV-003)",
    },
]


def _ownership_payload() -> dict[str, Any]:
    return {
        "components": [asdict(row) for row in COMPONENT_OWNERSHIP],
        "sections": [asdict(row) for row in SECTION_OWNERSHIP],
        "events": [
            {"event_type": event_type.value, **asdict(ownership)}
            for event_type, ownership in EVENT_OWNERSHIP.items()
        ],
    }


def render_json(data: list[dict[str, Any]]) -> str:
    document = {
        "rules": data,
        "dispositions": DISPOSITIONS,
        "ownership": _ownership_payload(),
    }
    return json.dumps(document, indent=2) + "\n"


def render_markdown(data: list[dict[str, Any]]) -> str:
    lines = [
        "# ADR-002 Traceability Matrix",
        "",
        "Generated by `scripts/generate_traceability.py` (`make traceability`).",
        "One row per validation rule: **Rule → Validator → Test(s)**. Rule ids are a",
        "**frozen namespace** — never reused or renumbered.",
        "",
        "| Rule ID | Group | Severity | ADR Reference | Description | Validator | Test(s) |",  # noqa: E501
        "|---|---|---|---|---|---|---|",
    ]
    for row in data:
        tests = "<br>".join(row["tests"]) or "—"
        lines.append(
            f"| {row['rule_id']} | {row['group']} | {row['severity']} | "
            f"{row['adr_reference']} | {row['description']} | `{row['validator']}` | {tests} |"  # noqa: E501
        )
    lines += [
        "",
        "## ADR-002 disposition (every §Validation-Rules item, exactly once — TD-004)",
        "",
        "| ADR-002 item | Disposition | Mechanism |",
        "|---|---|---|",
    ]
    for item in DISPOSITIONS:
        lines.append(
            f"| {item['adr_item']} | {item['disposition']} | {item['mechanism']} |"
        )
    lines += [
        "",
        "## Ownership (M1.7.6 — data only; enforcement owner: M6 Agent Manager)",
        "",
        "### Component ownership",
        "",
        "| Component | Owner | Writes | Enforcement | Status |",
        "|---|---|---|---|---|",
    ]
    for comp in COMPONENT_OWNERSHIP:
        writes = ", ".join(comp.writes) or "—"
        lines.append(
            f"| {comp.component} | {comp.owner} | {writes} | "
            f"{comp.enforcement} | {comp.status} |"
        )
    lines += [
        "",
        "### ADR-002 section ownership (agent roles)",
        "",
        "| Section | Fields | Write | Update | Approve | Reject |",
        "|---|---|---|---|---|---|",
    ]
    for sec in SECTION_OWNERSHIP:
        lines.append(
            f"| {sec.section} | {', '.join(sec.fields) or '—'} | "
            f"{', '.join(sec.write) or '—'} | {', '.join(sec.update) or '—'} | "
            f"{', '.join(sec.approve) or '—'} | {', '.join(sec.reject) or '—'} |"
        )
    lines += [
        "",
        "### Event ownership (event → writer roles → sections)",
        "",
        "| Event type | Writers | Sections |",
        "|---|---|---|",
    ]
    for event_type, ownership in EVENT_OWNERSHIP.items():
        lines.append(
            f"| {event_type.value} | {', '.join(ownership.writers)} | "
            f"{', '.join(ownership.sections)} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    data = rows()
    _MD.write_text(render_markdown(data), encoding="utf-8")
    _JSON.write_text(render_json(data), encoding="utf-8")
    print(f"wrote {_MD} and {_JSON}")


if __name__ == "__main__":
    main()
