# StratAgent Developer Guide

Practical reference for contributing to the **reference core** under `packages/`.
(For using the consulting product, see [USER_GUIDE.md](USER_GUIDE.md).)

> **Read [ADR-008](../architecture/ADR-008-Repository-Topology.md) first — this
> repo has three artifacts and this guide covers only one of them.**
>
> | Changing… | Edit | Tests |
> |---|---|---|
> | consulting behaviour (an agent, a framework) | `plugins/ruflo-stratagent/` | both surfaces inherit it |
> | the **web product** (pipeline, resilience, UI) | `apps/dashboard/` | `cd apps/dashboard/backend && uv run --extra dev pytest` |
> | the reference core (this guide) | `packages/` | `uv run pytest` |
>
> `packages/` is **not** on the dashboard's execution path except for
> `telemetry` — a change here does not reach the web product. CI
> (`.github/workflows/ci.yml`) gates all three.

## Repository layout

```
packages/            — the Python platform (import roots; see pythonpath below)
  common/            — base errors, shared value types
  core/              — config, logging, base classes
  state/             — EngagementState aggregate + sections (FROZEN — do not modify)
  persistence/       — append-only store (FROZEN)
  replay/            — event replay engine (FROZEN)
  knowledge/         — vault frontmatter + retrieval adapter
  planning/          — MECE validator, planning preconditions
  analysis/          — analysis-block contracts
  governance/        — lifecycle transitions + governance gates
  reporting/         — render_report + structural validation
  evidence/          — Evidence Provider extension mechanism (RC1.2, ADR-007)
  orchestration/     — live report-validation gate (RC1.2, ADR-006)
scripts/             — CLI entrypoints (schema gen, engagement validation)
tests/               — mirrors packages/; fixtures/ holds golden state
plugins/ruflo-stratagent/ — the Claude Code plugin (agents, skill, README)
knowledge-vault/     — the single framework/knowledge source of truth (READ-ONLY)
docs/architecture/   — ADRs + architecture docs
```

## Import convention

`pyproject.toml` sets `pythonpath = ["packages"]` (pytest) and
`mypy_path = "packages"`. Import packages by their top-level name — `from
state.models import EngagementState`, `from evidence import ProviderRegistry` —
never by a `packages.` prefix.

A **standalone script** (run via bare `uv run python scripts/foo.py`) does not
get `pythonpath`; bootstrap `sys.path` at the top (see
`scripts/validate_engagement.py`).

## Adding a package

1. Create `packages/<name>/__init__.py` exporting a curated `__all__`.
2. Add `<name>` to `pyproject.toml` `[tool.ruff.lint.isort] known-first-party`.
3. mypy discovers it automatically (`files = ["packages", "scripts"]`).
4. Mirror it under `tests/<name>/` with an `__init__.py` (needed so
   `from tests.fixtures... import` resolves the package root).

## Conventions

- **Types:** mypy `strict = true`. Full annotations; no untyped defs.
- **Style:** ruff (`E,F,I,UP,B,SIM`) + black, line length 88.
- **Immutability:** value objects are frozen dataclasses; state models are
  frozen Pydantic v2 (`model_copy(update={...})` to derive variants).
- **Errors:** everything derives from `common.errors.StratAgentError`.
- **Never modify** `packages/state/**`, `persistence/**`, `replay/**`, the ADRs'
  intent, or `knowledge-vault/**` notes.

## Tests & golden state

- `tests/fixtures/golden_state.py::make_golden_profitability_state()` returns a
  fully-populated, governance-cleared `EngagementState` — use it for reporting,
  validation, and gate tests.
- To exercise the live gate on a state, dump it to `state.json`
  (`state.model_dump_json()`) and call `orchestration.run_report_gate` (or the
  `scripts/validate_engagement.py` CLI).

## The live validation gate (RC1.2)

`packages/orchestration/report_gate.py` bridges the deterministic `reporting`
validators onto the live path. `run_report_gate(state)` returns a
`ReportGateResult`; `enforce_report_gate(state)` raises `ReportRenderError` with
diagnostics if the engagement may not be reported. See [ADR-006](../architecture/ADR-006-Governance-and-Live-Validation.md)
and [Execution-Flow.md](../architecture/Execution-Flow.md).

## Evidence Providers (RC1.2)

`packages/evidence/` is the extension seam for sourced external evidence — no
providers are shipped. Implement the `EvidenceProvider` Protocol, register it on
a `ProviderRegistry`, and results (`ProviderResult`, provenance-carrying) can be
promoted into the Evidence Ledger. See [ADR-007](../architecture/ADR-007-Evidence-Providers.md).

## Local quality gate

```
uv run ruff check packages tests scripts
uv run black --check packages tests scripts
uv run mypy
uv run pytest -q
```
