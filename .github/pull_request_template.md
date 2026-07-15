<!-- Thanks for contributing to StratAgent. -->

## What & why

<!-- What does this change, and what problem does it solve? -->

## Which artifact does this touch?

<!-- The repo has three: tick the one(s) you changed. See docs/architecture/ADR-008. -->

- [ ] `apps/dashboard/` — the shipping web product
- [ ] `plugins/ruflo-stratagent/` — the Claude Code plugin (agents, skills, vault)
- [ ] `packages/` — the reference core library
- [ ] docs / CI / tooling

## Checklist

- [ ] Tests pass locally (`uv run pytest` for the core; `cd apps/dashboard/backend && uv run --extra dev pytest` for the dashboard)
- [ ] Lint/format clean (`ruff`, `black --check`)
- [ ] No secrets, API keys, or `.env` values committed
- [ ] Docs updated if behaviour changed
