"""M1.7.3-S1 tests: append error hierarchy + AppendResult contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from common.errors import StratAgentError
from state.append import (
    AppendError,
    AppendErrorCode,
    AppendResult,
    EventAdmissionError,
    VersionConflictError,
)
from state.validation import ValidationGroup, Violation, ViolationSeverity


def _warning() -> Violation:
    return Violation(
        rule_id="LIFE-004",
        group=ValidationGroup.LIFECYCLE,
        severity=ViolationSeverity.WARNING,
        path="status",
        message="status does not match last phase",
    )


def _result(**overrides: object) -> AppendResult:
    fields: dict[str, object] = {
        "success": True,
        "version": 5,
        "projection_version": 2,
        "first_seq": 4,
        "last_seq": 5,
        "appended": 2,
        "warnings": [_warning()],
    }
    fields.update(overrides)
    return AppendResult.model_validate(fields)


# --- errors -------------------------------------------------------------------


def test_version_conflict_error_contract() -> None:
    err = VersionConflictError(expected=3, actual=5)
    assert err.expected == 3
    assert err.actual == 5
    assert err.error_code is AppendErrorCode.VERSION_CONFLICT
    assert "3" in str(err) and "5" in str(err)
    assert isinstance(err, AppendError)
    assert isinstance(err, StratAgentError)


def test_event_admission_error_contract() -> None:
    err = EventAdmissionError("sequence already assigned", event_id="ev_1")
    assert err.reason == "sequence already assigned"
    assert err.event_id == "ev_1"
    assert err.error_code is AppendErrorCode.EVENT_ADMISSION
    assert "sequence already assigned" in str(err)
    assert "ev_1" in str(err)
    assert isinstance(err, AppendError)
    assert isinstance(err, StratAgentError)


def test_event_admission_error_without_event_id() -> None:
    err = EventAdmissionError("empty batch")
    assert err.event_id is None
    assert str(err) == "event not admitted: empty batch"


def test_error_codes_are_a_frozen_namespace() -> None:
    # additive-frozen: values never change or vanish; S5 added append_unsupported
    assert {code.value for code in AppendErrorCode} == {
        "version_conflict",
        "event_admission",
        "append_unsupported",
    }


# --- AppendResult ---------------------------------------------------------------


def test_append_result_carries_all_fields() -> None:
    result = _result()
    assert result.success is True
    assert result.version == 5
    assert result.projection_version == 2
    assert result.first_seq == 4
    assert result.last_seq == 5
    assert result.appended == 2
    assert result.warnings[0].rule_id == "LIFE-004"


def test_append_result_is_frozen() -> None:
    result = _result()
    with pytest.raises(ValidationError):
        result.version = 99  # type: ignore[misc]


def test_append_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _result(unexpected="x")


def test_append_result_model_dump_round_trip() -> None:
    result = _result()
    assert AppendResult.model_validate(result.model_dump()) == result


def test_append_result_json_round_trip() -> None:
    result = _result()
    restored = AppendResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.projection_version == 2
    assert restored.warnings[0].severity is ViolationSeverity.WARNING
