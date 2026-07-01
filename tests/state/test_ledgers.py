"""M1.1 record-level tests for the Evidence and Assumption ledgers (ADR-002 §9, §14).

Record-level validation only; these test ids feed the ADR-002 traceability matrix
assembled in M1.6.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from state.ledgers import Assumption, AssumptionStatus, Evidence, EvidenceType

# --- Evidence: valid construction per type ----------------------------------


def test_client_fact_needs_no_extra_field() -> None:
    ev = Evidence(
        id="e1",
        claim="Revenue was $600M",
        type=EvidenceType.CLIENT_FACT,
        confidence=0.9,
    )
    assert ev.type is EvidenceType.CLIENT_FACT


def test_external_source_with_source_valid() -> None:
    ev = Evidence(
        id="e2",
        claim="Market grew 4%",
        type=EvidenceType.EXTERNAL_SOURCE,
        source="IBISWorld 2026",
        confidence=0.7,
    )
    assert ev.source == "IBISWorld 2026"


def test_computed_with_method_valid() -> None:
    ev = Evidence(
        id="e3",
        claim="Margin fell 4pts",
        type=EvidenceType.COMPUTED,
        method="P&L bridge; inputs: f3, a7",
        confidence=0.7,
    )
    assert ev.method


def test_assumption_evidence_with_ref_valid() -> None:
    ev = Evidence(
        id="e4",
        claim="Churn ~5%",
        type=EvidenceType.ASSUMPTION,
        source="a12",
        confidence=0.4,
    )
    assert ev.source == "a12"


# --- Evidence: rejects missing type-required fields -------------------------


@pytest.mark.parametrize(
    "etype",
    [EvidenceType.EXTERNAL_SOURCE, EvidenceType.ASSUMPTION, EvidenceType.COMPUTED],
)
def test_evidence_missing_required_field_rejected(etype: EvidenceType) -> None:
    with pytest.raises(ValidationError):
        Evidence(id="x", claim="c", type=etype, confidence=0.5)


def test_unknown_evidence_type_rejected() -> None:
    with pytest.raises(ValidationError):
        Evidence.model_validate(
            {"id": "x", "claim": "c", "type": "guesswork", "confidence": 0.5}
        )


# --- Evidence: confidence bounds --------------------------------------------


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_evidence_confidence_bounds(bad: float) -> None:
    with pytest.raises(ValidationError):
        Evidence(id="x", claim="c", type=EvidenceType.CLIENT_FACT, confidence=bad)


def test_evidence_round_trip() -> None:
    ev = Evidence(
        id="e", claim="c", type=EvidenceType.COMPUTED, method="m", confidence=0.6
    )
    assert Evidence.model_validate(ev.model_dump()) == ev


# --- Assumption: breakeven rule ---------------------------------------------


def test_non_load_bearing_without_breakeven_ok() -> None:
    a = Assumption(
        id="a1",
        statement="revenue flat",
        value="0%",
        rationale="base case",
        owner="financial-analyst",
        confidence=0.5,
    )
    assert a.status is AssumptionStatus.ACTIVE


def test_load_bearing_with_breakeven_ok() -> None:
    a = Assumption(
        id="a2",
        statement="COGS +3%",
        value="3%",
        rationale="input inflation",
        owner="financial-analyst",
        confidence=0.5,
        load_bearing=True,
        breakeven="1.5%",
    )
    assert a.load_bearing is True


def test_load_bearing_without_breakeven_rejected() -> None:
    with pytest.raises(ValidationError):
        Assumption(
            id="a3",
            statement="x",
            value="1",
            rationale="r",
            owner="o",
            confidence=0.5,
            load_bearing=True,
        )


@pytest.mark.parametrize("bad", [-0.5, 2.0])
def test_assumption_confidence_bounds(bad: float) -> None:
    with pytest.raises(ValidationError):
        Assumption(
            id="a", statement="s", value="v", rationale="r", owner="o", confidence=bad
        )


def test_assumption_round_trip() -> None:
    a = Assumption(
        id="a", statement="s", value="v", rationale="r", owner="o", confidence=0.5
    )
    assert Assumption.model_validate(a.model_dump()) == a


# --- Enum values match ADR-002 ----------------------------------------------


def test_enum_values() -> None:
    assert {e.value for e in EvidenceType} == {
        "client_fact",
        "external_source",
        "computed",
        "assumption",
    }
    assert {s.value for s in AssumptionStatus} == {"active", "invalidated", "confirmed"}
