# Acknowledgements

StratAgent stands on the shoulders of several projects and bodies of practice.

## Built on
- **[Ruflo](https://github.com/ruvnet/ruflo)** — the horizontal harness
  (orchestration, vector memory, MCP, cost/observability, guardrails, learning)
  that StratAgent composes with as a consulting vertical. When the full harness
  is installed (`npx ruflo init`), StratAgent lights up the `mcp__claude-flow__*`
  integrations; without it, it runs fully on plain files.
- **[Claude Code](https://claude.com/claude-code)** — the agent runtime that
  hosts the `/solve-case` skill and the specialist subagents.

## Tooling
- **[uv](https://docs.astral.sh/uv/)** (environments/packaging),
  **[Pydantic](https://docs.pydantic.dev/)** (typed state),
  **[Ruff](https://docs.astral.sh/ruff/)**, **[Black](https://black.readthedocs.io/)**,
  **[mypy](https://mypy-lang.org/)**, **[pytest](https://docs.pytest.org/)**.
- **[OpenTelemetry](https://opentelemetry.io/)** — the span model the telemetry
  layer is compatible with.
- **[Contributor Covenant](https://www.contributor-covenant.org/)** — the basis
  of our Code of Conduct.

## Practice
The consulting method draws on standard management-consulting problem-solving —
MECE issue trees, hypothesis-driven analysis, and structured framework
application — as taught in the case-interview and strategy literature. The
knowledge vault encodes these as reusable, governed notes rather than hardcoding
them into prompts.

## A note on evidence
StratAgent deliberately ships **no proprietary or third-party benchmark data**.
Its knowledge vault contains analytical frameworks, not datasets; any numbers in
an engagement are labeled assumptions unless supplied by the user or a configured
evidence provider. This keeps the platform honest about what it does and does not
know.
