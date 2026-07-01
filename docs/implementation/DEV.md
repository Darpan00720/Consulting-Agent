# Developer Guide

Engineering foundation for StratAgent implementation (established in M0).

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (environment + dependency manager)
- Python 3.12 is used for development (uv fetches it automatically).

## Setup
```bash
make install      # uv sync — create .venv and install deps + dev tools
make hooks        # (optional) install pre-commit git hooks
```

## Quality gate
`make check` is the **canonical gate**. A milestone is not done until it passes:
```bash
make check        # ruff (lint) + black --check (format) + mypy (types) + pytest (tests)
```
Individual targets: `make lint`, `make format`, `make typecheck`, `make test`,
`make fmt` (auto-format).

## Engagement State schema
The Engagement State is modelled in Pydantic (`packages/state/`). The JSON Schema
is **generated**, never hand-edited:
```bash
make schema       # regenerates schema/engagement-state.schema.json from the models
```
`tests/test_schema_generation.py` fails if the committed schema is out of date —
run `make schema` and commit after changing the models.

## Package layout (capability-based)
```
packages/
  core/        # base model, settings, logging         (M0)
  common/      # shared errors/types                    (M0)
  state/       # Engagement State + schema generation   (M0 slice; full model M1)
  knowledge/   # vault + Graphify + Knowledge Agent      (M2)
  planning/    # classifier, gap, planner, framework, issue-tree (M3)
  analysis/    # financial, market, operations, strategy, risk     (M4)
  governance/  # reviewer, challenger gates              (M5)
  reporting/   # engagement manager + report writer      (M6)
```
Source is importable via `pythonpath`/`mypy_path` (the project is a uv virtual
project; formal wheel packaging is deferred until a deployable artifact needs it).

## Conventions
- Architecture is frozen at v1.0 (ADR-001…005). Implementation conforms to the ADRs.
- Small, single-responsibility commits.
- Build only what the current milestone requires.
