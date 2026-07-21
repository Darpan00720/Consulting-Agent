"""Shared test fixtures for the dashboard backend."""

from __future__ import annotations

import pytest

# NOTE: do NOT import `app.*` at module scope. conftest is imported before the
# test modules, and test_api.py sets STRATAGENT_MOCK/DAILY_QUOTA in os.environ
# *before* it imports app.config — which reads them at import time. Importing
# app here would freeze config with mock mode OFF and 503 every request.


@pytest.fixture(autouse=True)
def _isolate_telemetry(tmp_path, monkeypatch):
    """Keep every test's telemetry inside its own tmp_path.

    ``config.TELEMETRY_DIR`` is resolved at import time from the default
    DB_PATH, so a test that monkeypatches only DB_PATH still writes traces to
    the REAL ``apps/dashboard/backend/telemetry/`` directory — which is how 93
    stray JSONL files once landed in a commit. Redirect it for all tests, and
    reset the recorder singleton so each test builds a fresh sink.

    Tests that assert on telemetry override TELEMETRY_DIR themselves; this
    fixture only guarantees nothing escapes into the working tree.
    """
    from app import config, telemetry_bridge  # lazy — see note above

    monkeypatch.setattr(config, "TELEMETRY_DIR", str(tmp_path / "telemetry"))
    telemetry_bridge.reset_for_tests()
    yield
    telemetry_bridge.reset_for_tests()


# ---- shared fixtures for ADR-014 pipeline-integration test files ----------
#
# 2026-07-19 Phase 2 independent review finding: test_pipeline_knowledge_
# adapter.py and test_pipeline_organization_adapter.py had each hand-rolled
# an identical CASE/QUANT/fake-output/db-isolation block. Extracted here so
# Phase 3's test_pipeline_evaluation_adapter.py (and any future ADR-014
# integration-phase test file) doesn't repeat it a third time.
#
# Real fixtures (not plain module-level functions/constants imported via
# ``from conftest import ...``) — this project's pytest configuration has no
# ``tests/__init__.py`` and does not put ``tests/`` on ``sys.path``, so a
# plain cross-file import of conftest.py fails at collection with
# ``ModuleNotFoundError: No module named 'conftest'`` (caught by actually
# running the suite, not just reading the diff). Fixtures are the only
# reliably portable way pytest shares code across test files without one.


@pytest.fixture
def pipeline_case() -> str:
    return (
        "A regional grocery chain with $800M revenue has seen margins compress "
        "from 4% to 2% over three years. Should it double down on private label, "
        "exit low-density stores, or merge with a competitor?"
    )


@pytest.fixture
def pipeline_fake_output():
    """Default fake agent output for ``run_engagement()``-driven tests:
    parseable verdicts for governance agents and a valid quant ledger for
    the engagement manager. Returns the output function itself — call it as
    ``pipeline_fake_output(agent_name)``."""
    quant_block = """

```quant
{"facts": [{"id": "A-1", "label": "revenue", "value": 800000000, "unit": "usd"}],
"derived": []}
```"""

    def _fake_output(agent: str) -> str:
        if agent == "reviewer":
            return "Verdict: approved"
        if agent == "challenger":
            return "Verdict: stands"
        if agent == "engagement-manager":
            return f"output-of-{agent}" + quant_block
        return f"output-of-{agent}"

    return _fake_output


@pytest.fixture
def isolate_pipeline_db(tmp_path, monkeypatch):
    """Point ``config.DB_PATH`` at a fresh tmp file and reset ``app.db``'s
    connection cache — every ADR-014 integration-phase test needs this
    before creating an engagement."""
    from app import config, db

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "pipeline-test.db")
    db.reset_for_tests()
