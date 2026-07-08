"""Performance benchmarks for retrieve() (M3-Design.md §9.9, D-19).

Targets (Phase 1C):
  - retrieve() end-to-end ≤ 200 ms (without Graphify) on 132-note vault
  - Vault scan ≤ 150 ms

Run with:  uv run pytest tests/knowledge/test_retrieval_perf.py --benchmark-only -v
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from knowledge import NoteType, RetrievalQuery, retrieve

_REAL_VAULT = Path(__file__).resolve().parents[2] / "knowledge-vault"

_skip_no_vault = pytest.mark.skipif(
    not _REAL_VAULT.is_dir(), reason="real vault not present"
)


# ── pytest-benchmark tests (preferred) ───────────────────────────────────────


@_skip_no_vault
def test_retrieve_latency_benchmark(benchmark: pytest.fixture) -> None:  # type: ignore[type-arg]
    """retrieve() on 132 notes must complete in ≤ 200 ms (§9.9 perf target, D-19)."""
    q = RetrievalQuery(text="profitability margin framework", limit=10)

    result = benchmark(retrieve, q, vault_dir=_REAL_VAULT)
    assert isinstance(result, list)

    # Assert the mean across all benchmark rounds is within target
    stats = benchmark.stats
    mean_ms = stats["mean"] * 1000
    assert mean_ms <= 200, (
        f"retrieve() mean latency {mean_ms:.1f} ms exceeds 200 ms target"
    )


@_skip_no_vault
def test_retrieve_framework_filter_benchmark(benchmark: pytest.fixture) -> None:  # type: ignore[type-arg]
    """Type-filtered retrieve() (frameworks only) also meets the 200 ms target."""
    q = RetrievalQuery(
        text="competitive strategy positioning",
        types=frozenset({NoteType.FRAMEWORK}),
        limit=10,
    )

    result = benchmark(retrieve, q, vault_dir=_REAL_VAULT)
    assert isinstance(result, list)

    stats = benchmark.stats
    mean_ms = stats["mean"] * 1000
    assert mean_ms <= 200, (
        f"filtered retrieve() mean latency {mean_ms:.1f} ms exceeds 200 ms target"
    )


# ── wall-clock fallback (runs even without pytest-benchmark rounds) ────────────


@_skip_no_vault
def test_retrieve_wall_clock_under_200ms() -> None:
    """Wall-clock single-run guard — fails fast if retrieve() grossly regresses."""
    q = RetrievalQuery(text="profitability margin", limit=10)

    start = time.perf_counter()
    results = retrieve(q, vault_dir=_REAL_VAULT)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert isinstance(results, list)
    assert elapsed_ms <= 200, (
        f"retrieve() took {elapsed_ms:.1f} ms — exceeds 200 ms target (§9.9)"
    )


@_skip_no_vault
def test_retrieve_multiple_queries_consistent() -> None:
    """Ten sequential calls must all complete under 200 ms each."""
    q = RetrievalQuery(text="market entry competitive dynamics", limit=10)
    for _ in range(10):
        start = time.perf_counter()
        results = retrieve(q, vault_dir=_REAL_VAULT)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms <= 200, f"retrieve() took {elapsed_ms:.1f} ms in iteration"
        assert isinstance(results, list)
