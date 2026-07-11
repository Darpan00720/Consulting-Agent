# Contributing to StratAgent

Thanks for your interest. StratAgent is a governed, design-first codebase; a few
conventions keep it internally consistent over the long haul.

## Ground rules (read once)

- **Frozen core is off-limits.** Do not modify `packages/state`,
  `packages/persistence`, or `packages/replay`. New capability is *additive*
  (new package), not a change to these.
- **Design-first for architecture.** Architectural changes go through an ADR
  (`docs/architecture/ADR-00X-*.md`). Do **not** rewrite an *accepted* ADR —
  supersede it with a new one (`supersedes:` header), as ADR-006 did.
- **Knowledge is human-curated.** `knowledge-vault/` notes are the single source
  of truth for frameworks/domain knowledge; treat note content as read-only
  except via the `knowledge-curator` agent.
- **Don't reintroduce drift.** The convergence guards in `tests/convergence/`
  pin invariants (single framework store, mandatory governance gates). A failure
  there is architecture drift, not a flaky test.

## Development setup

```bash
uv sync                      # Python ≥ 3.12 + uv
```

Import packages by top-level name (`from state.models import ...`); `pythonpath`
is `["packages"]`. See the [Developer Guide](docs/guides/DEVELOPER_GUIDE.md).

## The quality gate (must pass before a PR)

```bash
make check          # = ruff + black --check + mypy + pytest
# or individually:
uv run ruff check packages tests scripts
uv run black --check packages tests scripts
uv run mypy                       # strict
uv run pytest -q                  # 954 tests
```

Standards: `ruff` (rules `E,F,I,UP,B,SIM`) + `black`, line length **88**;
`mypy --strict` (full annotations, no untyped defs); immutable value objects
(frozen dataclasses / frozen Pydantic v2, mutate via `model_copy`).

## Making a change

1. Branch from `main`.
2. Keep the change scoped; match the surrounding code's idiom and comment density.
3. Add/adjust tests (mirror the package under `tests/`); new packages need a
   `tests/<pkg>/__init__.py`.
4. Update the relevant docs **in the same PR** — especially the
   [Operations Runbook](docs/operations/Operations-Runbook.md) if you change a
   command, path, package, agent, or failure mode, and `CHANGELOG.md`.
5. Run `make check`. Green ⇒ open the PR.

## Adding things (pointers)

- **A framework** → a new note under `knowledge-vault/frameworks/` (correct
  ADR-003 frontmatter); no code change. See [Runbook §5.2](docs/operations/Operations-Runbook.md#52-adding-frameworks).
- **An agent** → an ADR-005-style contract in `plugins/ruflo-stratagent/agents/`,
  wired into the SKILL; never give an agent private memory or another agent's
  state. See [Runbook §5.3](docs/operations/Operations-Runbook.md#53-adding-analysts-agents).
- **An evidence provider** → implement the `evidence.EvidenceProvider` Protocol
  (ADR-007); do not commit credentials.

## Commit & PR hygiene

- Small, focused commits; imperative subject lines.
- PRs describe *what* and *why*; link the ADR/issue if architectural.
- Do not commit runtime artifacts (`telemetry/`, caches, `.venv`) — they're
  gitignored.

## Reporting issues

Bugs and ideas: open an issue with repro steps and the relevant engagement
artifacts / telemetry trace. Security issues: **do not** open a public issue —
follow [SECURITY.md](SECURITY.md).

By contributing you agree your contributions are licensed under the repository's
[MIT License](LICENSE) and that you follow the [Code of Conduct](CODE_OF_CONDUCT.md).
