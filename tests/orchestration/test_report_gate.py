"""Live report-gate tests (RC1.2, WI-2 / ADR-006).

Verifies the deterministic validation layer is enforced on the live path,
including the real JSON round-trip the orchestrator uses (state.json → gate).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from orchestration import (
    enforce_report_gate,
    load_state,
    run_report_gate,
)
from orchestration.report_gate import ReportGateResult
from reporting import ReportRenderError
from tests.fixtures.golden_state import make_golden_profitability_state

# ---------------------------------------------------------------------------
# Passing path
# ---------------------------------------------------------------------------


def test_golden_state_passes_gate() -> None:
    result = run_report_gate(make_golden_profitability_state())
    assert result.ok, result.diagnostics()
    assert result.render_ready and result.consistent
    assert result.issues == ()


def test_enforce_passes_silently_on_golden() -> None:
    out = enforce_report_gate(make_golden_profitability_state())
    assert out.ok


def test_diagnostics_message_on_pass() -> None:
    result = run_report_gate(make_golden_profitability_state())
    assert "PASSED" in result.diagnostics()


# ---------------------------------------------------------------------------
# Blocking path — each rule blocks report delivery
# ---------------------------------------------------------------------------


def test_missing_reviewer_gate_blocks() -> None:
    state = make_golden_profitability_state().model_copy(
        update={"reviewer_notes": None}
    )
    result = run_report_gate(state)
    assert not result.ok
    assert any(i.check == "render_ready" for i in result.issues)
    assert "REVIEWER_GATE_NOT_RUN" in result.diagnostics()


def test_missing_challenger_gate_blocks() -> None:
    state = make_golden_profitability_state().model_copy(
        update={"challenge_notes": None}
    )
    result = run_report_gate(state)
    assert not result.ok
    assert "CHALLENGER_GATE_NOT_RUN" in result.diagnostics()


def test_enforce_raises_when_blocked() -> None:
    state = make_golden_profitability_state().model_copy(
        update={"reviewer_notes": None}
    )
    with pytest.raises(ReportRenderError) as exc:
        enforce_report_gate(state)
    assert "BLOCKED" in str(exc.value)


def test_diagnostics_are_actionable() -> None:
    state = make_golden_profitability_state().model_copy(
        update={"reviewer_notes": None}
    )
    diag = run_report_gate(state).diagnostics()
    # names the check, the rule, and says delivery is not permitted
    assert "render_ready" in diag
    assert "not permitted" in diag


# ---------------------------------------------------------------------------
# Real JSON bridge (state.json → load_state → gate)
# ---------------------------------------------------------------------------


def test_state_json_roundtrip_passes(tmp_path: Path) -> None:
    state = make_golden_profitability_state()
    path = tmp_path / "state.json"
    path.write_text(state.model_dump_json(), encoding="utf-8")
    loaded = load_state(path)
    assert run_report_gate(loaded).ok


def test_load_state_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ReportRenderError) as exc:
        load_state(tmp_path / "nope.json")
    assert "not found" in str(exc.value)


def test_load_state_malformed_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ReportRenderError):
        load_state(path)


def test_load_state_schema_violation_raises(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"metadata": {"bogus": true}}', encoding="utf-8")
    with pytest.raises(ReportRenderError) as exc:
        load_state(path)
    assert "schema" in str(exc.value)


def test_result_type_is_frozen_dataclass() -> None:
    result = run_report_gate(make_golden_profitability_state())
    assert isinstance(result, ReportGateResult)
    with pytest.raises(FrozenInstanceError):
        result.render_ready = False  # type: ignore[misc]
