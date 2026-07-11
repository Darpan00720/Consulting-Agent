# Support

Where to go for help with StratAgent.

## Start here
1. **[Operations Runbook](docs/operations/Operations-Runbook.md)** — the canonical
   manual: install, run, maintain, debug, evaluate. Most questions are answered
   here, especially [§6 Failure Modes](docs/operations/Operations-Runbook.md#6-failure-modes).
2. **[FAQ](FAQ.md)** — quick answers to common questions.
3. **[Quickstart](docs/guides/QUICKSTART.md)** / **[User Guide](docs/guides/USER_GUIDE.md)** — using it.
4. **[Developer Guide](docs/guides/DEVELOPER_GUIDE.md)** — building on it.

## Common questions → direct links
| Question | See |
|---|---|
| "Why are all the numbers assumptions?" | [FAQ](FAQ.md) · [ADR-007](docs/architecture/ADR-007-Evidence-Providers.md) |
| "The report gate blocked my engagement." | [Runbook §6.3](docs/operations/Operations-Runbook.md#63-validation-failures-report-gate) |
| "The Challenger said needs_rework." | [Runbook §6.4](docs/operations/Operations-Runbook.md#64-governance-failures) |
| "How do I read telemetry?" | [Runbook §6.2](docs/operations/Operations-Runbook.md#62-telemetry-diagnosis) · [Observability](docs/observability/Telemetry-Architecture.md) |
| "How do I add a framework / agent?" | [Runbook §5](docs/operations/Operations-Runbook.md#5-maintenance) |

## Filing an issue
Open a GitHub issue with: what you ran (`/solve-case` prompt or command), what
you expected, what happened, the relevant `engagements/<slug>/` artifacts or the
telemetry trace, and your version (`0.1.0-rc2`). Reproducible reports get help
fastest.

## Security
Do **not** file security issues publicly — follow [SECURITY.md](SECURITY.md).

## Scope of support
StratAgent is pre-1.0 (*Ready for Limited Beta*). It is decision *support* under
human review, not a production advisory service. Support is best-effort via
issues; there is no SLA.
