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
