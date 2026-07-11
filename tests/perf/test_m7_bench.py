"""M7 performance baselines: report renderer and structural validation.

All benchmarks use pytest-benchmark in pedantic mode (rounds=1, iterations=1)
so they record single cold-run timings as regression references, consistent with
M1.7/M1.8/M1.9 baselines. Timing assertions are intentionally absent; these
are observational baselines only.

Companion non-benchmark tests verify the fixture infrastructure itself
(shape/validity, never timing).
"""

from __future__ import annotations

import pytest

from reporting import (
    check_render_ready,
    render_report,
    validate_consistency,
)
from tests.fixtures.golden_state import make_golden_profitability_state

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden_state():  # type: ignore[no-untyped-def]
    return make_golden_profitability_state()


# ---------------------------------------------------------------------------
# render_report benchmarks
# ---------------------------------------------------------------------------


def test_render_report_cold(benchmark, golden_state) -> None:  # type: ignore[no-untyped-def]
    """Baseline: render_report from a fully-populated golden state (cold)."""
    benchmark.pedantic(render_report, args=(golden_state,), rounds=1, iterations=1)


def test_render_report_warm(benchmark, golden_state) -> None:  # type: ignore[no-untyped-def]
    """Baseline: render_report warm (5 rounds × 3 iterations = 15 runs)."""
    benchmark.pedantic(render_report, args=(golden_state,), rounds=5, iterations=3)


def test_render_report_minimal(benchmark) -> None:  # type: ignore[no-untyped-def]
    """Baseline: render_report on minimal state (metadata only)."""
    from state.identifiers import EngagementId
    from state.models import EngagementMetadata, EngagementState

    minimal = EngagementState(
        metadata=EngagementMetadata(
            engagement_id=EngagementId("eng_bench_min"),
            tenant_id="t_bench",
            slug="bench-minimal",
        )
    )
    benchmark.pedantic(render_report, args=(minimal,), rounds=5, iterations=3)


# ---------------------------------------------------------------------------
# check_render_ready benchmarks
# ---------------------------------------------------------------------------


def test_check_render_ready_golden(benchmark, golden_state) -> None:  # type: ignore[no-untyped-def]
    """Baseline: check_render_ready on golden state (all gates cleared)."""
    benchmark.pedantic(check_render_ready, args=(golden_state,), rounds=5, iterations=3)


def test_validate_consistency_golden(benchmark, golden_state) -> None:  # type: ignore[no-untyped-def]
    """Baseline: validate_consistency on golden state."""
    benchmark.pedantic(
        validate_consistency, args=(golden_state,), rounds=5, iterations=3
    )


# ---------------------------------------------------------------------------
# Infrastructure validity tests (non-benchmark)
# ---------------------------------------------------------------------------


def test_golden_state_fixture_is_valid() -> None:
    state = make_golden_profitability_state()
    assert state.metadata.engagement_id == "eng_golden_profitability"
    assert state.financial_analysis is not None
    assert state.reviewer_notes is not None
    assert state.challenge_notes is not None


def test_render_report_output_shape() -> None:
    state = make_golden_profitability_state()
    report = render_report(state)
    assert isinstance(report, str)
    assert len(report) > 500
    assert "## Executive Summary" in report
    assert "StratAgent RC1" in report


def test_check_render_ready_golden_is_valid() -> None:
    state = make_golden_profitability_state()
    result = check_render_ready(state)
    assert result.valid, [i.detail for i in result.issues]


def test_validate_consistency_golden_is_valid() -> None:
    state = make_golden_profitability_state()
    result = validate_consistency(state)
    assert result.valid, [i.detail for i in result.issues]


def test_render_report_is_deterministic() -> None:
    state = make_golden_profitability_state()
    assert render_report(state) == render_report(state)
