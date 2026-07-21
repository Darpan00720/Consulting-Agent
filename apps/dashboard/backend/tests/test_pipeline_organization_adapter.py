"""ADR-014 Phase 2 — app.pipeline <-> app.organization integration.

Adapter tests (deterministic catalog index), integration tests (the
planning phase prompt with the feature enabled), regression/compatibility
tests (the planning phase prompt is byte-for-byte unaffected with the
feature disabled, the default; W8/Phase 1 behaviour is unaffected)."""

from __future__ import annotations

import asyncio

from app import config, db
from app.pipeline import organization_adapter
from app.pipeline.engine import run_engagement


def _run(coro):
    return asyncio.run(coro)


def _import_lines(source: str) -> str:
    return "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


# ---- adapter unit tests -----------------------------------------------------


def test_organization_layer_index_is_real_deterministic_content():
    import app.organization as organization

    first = organization_adapter.organization_layer_index()
    second = organization_adapter.organization_layer_index()
    assert first == second  # deterministic, no LLM, no randomness
    assert first, "expected the 25-role catalog to produce a non-empty index"

    expected_count = len(organization.default_organization_registry().list())
    assert len(first.splitlines()) == expected_count


def test_organization_layer_index_never_raises_even_if_registry_is_broken(
    monkeypatch,
):
    import app.organization as organization

    def _broken_registry():
        raise RuntimeError("simulated catalog failure")

    monkeypatch.setattr(organization, "default_organization_registry", _broken_registry)
    assert organization_adapter.organization_layer_index() == ""


def test_organization_layer_index_only_uses_the_public_package_api():
    """ADR-014 §7.2/§7.4: no submodule import, no private symbol — checked
    against IMPORT lines only, since the module's own docstring names
    ``allocate_team``/``app.organization.allocation`` in prose to explain
    why they aren't used, which isn't an import (the same false-positive
    fix every architecture-compliance test in this codebase already
    applies)."""
    import inspect

    source = inspect.getsource(organization_adapter)
    imports = _import_lines(source)
    app_imports = [line.strip() for line in imports.splitlines() if "app." in line]
    assert app_imports == ["import app.organization as organization"]

    code_lines = "\n".join(
        line
        for line in source.splitlines()
        if not line.strip().startswith(("#", '"', "'"))
    )
    assert "allocate_team(" not in code_lines  # never CALLED, even if named in prose


def test_import_of_app_organization_is_lazy_not_module_level():
    """2026-07-19 end-to-end validation finding: a module-level
    ``import app.organization`` here would mean an unimportable
    app.organization breaks app.pipeline.engine's own import — i.e. the
    whole production orchestrator fails to start, not just this optional
    enrichment. Checked structurally: the import must appear inside the
    function body, never among the module's own top-level import lines."""
    import inspect

    source = inspect.getsource(organization_adapter)
    top_level_imports = "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
        and not line.startswith((" ", "\t"))
    )
    assert "app.organization" not in top_level_imports


def test_engine_still_imports_when_app_organization_is_unimportable():
    """The real-world proof, run in a fresh subprocess so a simulated
    broken app.organization can't leak into the rest of the test session."""
    import pathlib
    import subprocess
    import sys

    backend_root = pathlib.Path(__file__).resolve().parent.parent
    script = (
        "import sys, types\n"
        "broken = types.ModuleType('app.organization')\n"
        "sys.modules['app.organization'] = broken\n"
        "import app.pipeline.engine\n"
        "from app.pipeline import organization_adapter\n"
        "assert organization_adapter.organization_layer_index() == ''\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


# ---- engine integration tests (feature disabled = default; regression) -----


def test_planning_prompt_unaffected_when_flag_disabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output
):
    assert config.ORGANIZATION_LAYER_ENABLED is False, "flag must default off"

    captured: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        if agent == "planner":
            captured["user"] = user
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert "app.organization" not in captured["user"]
    assert "Structured organization/role catalog" not in captured["user"]


def test_planning_prompt_byte_identical_across_runs_when_disabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output
):
    prompts_seen = []

    async def fake_call(agent, system, user, **kw):
        if agent == "planner":
            prompts_seen.append(user)
        return pipeline_fake_output(agent)

    for _ in range(2):
        eid = db.create_engagement("browser-x", pipeline_case)
        _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert prompts_seen[0] == prompts_seen[1]


def test_framing_phase_and_w8_behaviour_unaffected_by_phase_2(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output, monkeypatch
):
    """Regression: W9 integration must not change W8's own (already-shipped,
    also-disabled-by-default) framing-phase behaviour."""
    monkeypatch.setattr(config, "ORGANIZATION_LAYER_ENABLED", True)

    captured: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        if agent == "framework-selector":
            captured["user"] = user
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert "Structured framework catalog" not in captured["user"]  # W8 flag still off
    assert "governed knowledge vault index" in captured["user"]


# ---- engine integration tests (feature enabled) -----------------------------


def test_planning_prompt_includes_organization_layer_section_when_enabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output, monkeypatch
):
    monkeypatch.setattr(config, "ORGANIZATION_LAYER_ENABLED", True)

    captured: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        if agent == "planner":
            captured["user"] = user
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert "Structured organization/role catalog (app.organization" in captured["user"]
    assert "Produce the engagement plan." in captured["user"]


def test_engagement_completes_successfully_with_both_phase_1_and_2_enabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output, monkeypatch
):
    """Compatibility test: enabling both flags together doesn't break the
    engine's own ability to run an engagement to completion."""
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_ENABLED", True)
    monkeypatch.setattr(config, "ORGANIZATION_LAYER_ENABLED", True)

    async def fake_call(agent, system, user, **kw):
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    record = db.get_engagement(eid)
    assert record["status"] == "completed"
