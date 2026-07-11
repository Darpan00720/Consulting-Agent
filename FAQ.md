# FAQ

### What is StratAgent, in one sentence?
An AI management-consulting platform (a Claude Code plugin on the Ruflo harness)
that runs a full, governed consulting engagement on a business problem and
produces an evidence-traceable, executive-ready report.

### Is it production-ready?
No — it is **Ready for Limited Beta** (`0.1.0-rc2`). It is decision *support*
under mandatory human review, not an autonomous advisor. See the
[Research Evaluation](docs/reviews/v1.0-Research-Evaluation.md).

### Why are all the numbers labeled `[ASSUMPTION]`?
By design. The knowledge vault holds analytical *frameworks*, not *data*
(ADR-003, decision D-6). Any number is an assumption unless **you** supplied it
in the prompt or a configured **Evidence Provider**
([ADR-007](docs/architecture/ADR-007-Evidence-Providers.md)) sourced it. This is
deliberate honesty — the platform never invents data. Populating a provider is
the top roadmap item.

### Do I have to check the numbers myself?
**Yes.** A qualified human must verify every quantitative claim, confirm the
load-bearing assumptions and their breakevens, and own the final recommendation
before it is used or shared.

### Why did the Challenger send my engagement back for rework?
That's the system working. The Challenger caught an overconfident, inconsistent,
or unsupported conclusion before it reached a report — the single clearest way
StratAgent beats a one-shot answer. Fix the analysis and re-run; don't bypass it.

### Why did the report gate block me?
The deterministic validation gate refuses to emit a report that isn't
evidence-traceable or hasn't cleared both governance gates. Read the diagnostics
and fix the named issue at its source — [Runbook §6.3](docs/operations/Operations-Runbook.md#63-validation-failures-report-gate).

### Will I get the same answer if I run the same case twice?
Not necessarily. The LLM layer is **non-deterministic**; treat output as one
reasoned draft, not "the answer." The deterministic layer (validators, gates,
renderer, analytics) *is* reproducible.

### How long does an engagement take?
Minutes to tens of minutes — it is model-inference-bound (~11–13 subagent
dispatches), not code-bound.

### Do I need the Ruflo MCP server?
No. StratAgent is fully functional on plain files. Installing the full harness
(`npx ruflo init`) lights up optional integrations (memory, swarm,
cost/observability) but is not required.

### How is telemetry different from the event log?
The ADR-002 **domain event log** records *what happened* to the engagement
(business facts). **Telemetry** records *how the machinery performed*
(durations, tokens, retries). They are separate and correlate by
`engagement_id`. See [Observability](docs/observability/Telemetry-Architecture.md).

### Can I use it for regulated financial/legal/medical decisions?
**No.** Those are prohibited uses. So are live trading and irreversible
high-stakes decisions without expert review. See
[Appropriate Use](docs/beta/Beta-Program-Guide.md#5-ethics--appropriate-use-full).

### How do I add a framework or an agent?
Frameworks: add a governed note under `knowledge-vault/frameworks/` (no code).
Agents: an ADR-005 contract wired into the SKILL. See
[Runbook §5](docs/operations/Operations-Runbook.md#5-maintenance).

### Where do I start reading?
[README](README.md) → [Operations Runbook](docs/operations/Operations-Runbook.md)
→ [Quickstart](docs/guides/QUICKSTART.md).
