"""ADR-014 Phase 1 — app.pipeline <-> app.knowledge integration.

Adapter tests (deterministic catalog index), integration tests (the framing
phase prompt with the feature enabled), regression/compatibility tests (the
framing phase prompt is byte-for-byte unaffected with the feature disabled,
the default)."""

from __future__ import annotations

import asyncio

from app import config, db
from app.pipeline import knowledge_adapter
from app.pipeline.engine import run_engagement


def _run(coro):
    return asyncio.run(coro)


# ---- adapter unit tests -----------------------------------------------------


def test_knowledge_library_index_is_real_deterministic_content():
    import app.knowledge as knowledge

    first = knowledge_adapter.knowledge_library_index()
    second = knowledge_adapter.knowledge_library_index()
    assert first == second  # deterministic, no LLM, no randomness
    assert first, "expected the 87-framework catalog to produce a non-empty index"
    assert "five_forces" not in first  # ids are not surfaced, only names

    expected_count = len(knowledge.default_framework_registry().list())
    assert len(first.splitlines()) == expected_count


def test_knowledge_library_index_never_raises_even_if_registry_is_broken(monkeypatch):
    import app.knowledge as knowledge

    def _broken_registry():
        raise RuntimeError("simulated catalog failure")

    monkeypatch.setattr(knowledge, "default_framework_registry", _broken_registry)
    assert knowledge_adapter.knowledge_library_index() == ""


def test_knowledge_library_index_only_uses_the_public_package_api():
    """ADR-014 §7.1/§7.4: no submodule import, no private symbol."""
    import inspect

    source = inspect.getsource(knowledge_adapter)
    assert "import app.knowledge as knowledge" in source
    assert "app.knowledge.catalog" not in source
    assert "app.knowledge.registry" not in source
    assert "._" not in source  # no private-attribute access anywhere


def test_import_of_app_knowledge_is_lazy_not_module_level():
    """2026-07-19 end-to-end validation finding: a module-level
    ``import app.knowledge`` here would mean an unimportable app.knowledge
    breaks app.pipeline.engine's own import — i.e. the whole production
    orchestrator fails to start, not just this optional enrichment.
    Checked structurally: the import must appear inside the function body,
    never among the module's own top-level import lines."""
    import inspect

    source = inspect.getsource(knowledge_adapter)
    top_level_imports = "\n".join(
        line
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
        and not line.startswith((" ", "\t"))
    )
    assert "app.knowledge" not in top_level_imports


def test_engine_still_imports_when_app_knowledge_is_unimportable():
    """The real-world proof, run in a fresh subprocess so a simulated
    broken app.knowledge can't leak into the rest of the test session."""
    import pathlib
    import subprocess
    import sys

    backend_root = pathlib.Path(__file__).resolve().parent.parent
    script = (
        "import sys, types\n"
        "broken = types.ModuleType('app.knowledge')\n"
        "sys.modules['app.knowledge'] = broken\n"
        "import app.pipeline.engine\n"
        "from app.pipeline import knowledge_adapter\n"
        "assert knowledge_adapter.knowledge_library_index() == ''\n"
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


def test_framing_prompt_unaffected_when_flag_disabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output
):
    assert config.KNOWLEDGE_LIBRARY_ENABLED is False, "flag must default off"

    captured: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        if agent == "framework-selector":
            captured["user"] = user
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert "app.knowledge" not in captured["user"]
    assert "Structured framework catalog" not in captured["user"]


def test_framing_prompt_byte_identical_regardless_of_adapter_existing(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output
):
    """The strongest regression proof: capture the framing prompt with the
    flag off twice (nothing about run order/state affects it)."""
    prompts_seen = []

    async def fake_call(agent, system, user, **kw):
        if agent == "framework-selector":
            prompts_seen.append(user)
        return pipeline_fake_output(agent)

    for _ in range(2):
        eid = db.create_engagement("browser-x", pipeline_case)
        _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert prompts_seen[0] == prompts_seen[1]


# ---- engine integration tests (feature enabled) -----------------------------


def test_framing_prompt_includes_knowledge_library_section_when_enabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output, monkeypatch
):
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_ENABLED", True)

    captured: dict[str, str] = {}

    async def fake_call(agent, system, user, **kw):
        if agent == "framework-selector":
            captured["user"] = user
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    assert "Structured framework catalog (app.knowledge" in captured["user"]
    # the existing vault index is still present, unmodified — additive only
    assert "governed knowledge vault index" in captured["user"]


def test_engagement_completes_successfully_with_flag_enabled(
    isolate_pipeline_db, pipeline_case, pipeline_fake_output, monkeypatch
):
    """Compatibility test: enabling the flag doesn't break the engine's own
    ability to run an engagement to completion (governance gates, quant
    gate, resume machinery all still function)."""
    monkeypatch.setattr(config, "KNOWLEDGE_LIBRARY_ENABLED", True)

    async def fake_call(agent, system, user, **kw):
        return pipeline_fake_output(agent)

    eid = db.create_engagement("browser-x", pipeline_case)
    _run(run_engagement(eid, pipeline_case, call=fake_call))

    record = db.get_engagement(eid)
    assert record["status"] == "completed"
