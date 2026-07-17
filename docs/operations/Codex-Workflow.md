# Codex Plugin — Development Workflow

**Status:** Installed 2026-07-17 (user scope — applies across every Claude
Code project on this machine, not just this repo). This document is
operational/developer-facing: it governs how the *engineering team* builds
StratAgent. It has no relationship to the product itself — StratAgent's own
consulting pipeline never calls Codex or any component described here.

## What this is

[`openai/codex-plugin-cc`](https://github.com/openai/codex-plugin-cc) — an
official OpenAI-published Claude Code plugin that lets a Claude Code session
call out to OpenAI's Codex CLI for code review and task delegation, without
leaving the Claude Code workflow.

Installed via:

```bash
claude plugin marketplace add openai/codex-plugin-cc
claude plugin install codex@openai-codex
```

Verify:

```bash
claude plugin list                    # should show codex@openai-codex, enabled
claude plugin details codex@openai-codex
```

## Before it's usable: authentication (the user's step, never the agent's)

Claude never enters credentials, runs a login flow, or configures API keys —
this step is always manual and always the operator's:

```bash
/codex:setup     # detects whether Codex is ready; can offer to `npm install -g @openai/codex`
!codex login     # or: OPENAI_API_KEY set in the environment
```

Requires a ChatGPT subscription (including Free) or an OpenAI API key, and
Node.js ≥ 18.18 (this machine has v26.4.0 — already satisfied).

## What you get

| Command | What it does | Read-only? |
|---|---|---|
| `/codex:review [--base <ref>]` | Standard Codex review of uncommitted changes or a branch diff | Yes |
| `/codex:adversarial-review` | Steerable challenge review — pressure-tests design choices, not just code details | Yes |
| `/codex:rescue <task>` | Delegates a task to Codex (investigate a bug, try a fix, a cheaper/faster pass) | No — can write code |
| `/codex:transfer` | Hands the current Claude Code session to a persistent Codex thread | N/A (session export) |
| `/codex:status`, `/codex:result`, `/codex:cancel` | Manage background Codex jobs | Yes |

## Security & data-sharing — read this before using it

This is the one thing worth being deliberate about, and it's why installation
went through an explicit confirmation rather than happening automatically:

- **`/codex:review` and `/codex:adversarial-review` send your current
  diff/code to OpenAI's Codex service.** This is a different vendor than
  Claude/Anthropic. Treat it the same as any other third-party code-review
  tool: don't run it on a diff containing secrets, and be aware this repo's
  code leaves the machine to a second AI provider when these commands run.
- **`/codex:transfer` sends your actual Claude Code session transcript**
  (from `~/.claude/projects`) to Codex, converted into a Codex-native thread.
  This carries whatever was discussed in that session — for this project,
  that can include case-prompt content, architecture reasoning, and anything
  else typed into a Claude Code session. Use deliberately, not by default.
- **No StratAgent product data ever flows through this plugin.** The
  dashboard's engagements, case prompts, and reports run entirely through
  StratAgent's own multi-provider chain (`apps/dashboard/backend/app/pipeline`)
  and never touch this plugin. This is a *developer tool*, wired into nothing
  in the shipped product.
- **Installed at user scope, not project scope.** It is available in every
  Claude Code session on this machine, not gated to this repository. If that's
  not desired, `claude plugin uninstall codex@openai-codex` removes it, or
  `claude plugin disable codex` turns it off without removing the marketplace.

## When to use Claude vs. Codex vs. both

| Task class | Use |
|---|---|
| Large mechanical refactors, boilerplate generation, test scaffolding | **Codex** (`/codex:rescue`) — cheaper/faster for well-scoped, low-judgment work |
| Independent second-opinion code review before a PR | **Codex** (`/codex:review` or `/codex:adversarial-review`) — a genuinely different model family catches different things than Claude reviewing its own diff |
| Migrations, dependency bumps, mechanical API-surface changes | **Codex**, Claude verifies the result |
| Consulting-domain reasoning: agent prompt design, framework/knowledge-vault content, engagement lifecycle logic | **Claude only** — this requires deep context on StratAgent's governance model (ADR-005/006/009/010) that a delegated task would have to re-derive from scratch |
| Anything touching the Quant Gate, Ledger Builder, Evidence Store, or any deterministic verification logic (P1/P2/P3) | **Claude only** — these modules exist specifically so arithmetic/structure is never delegated to an LLM's judgment; delegating their *implementation* to a second LLM without the same verification discipline would reintroduce the exact risk this whole architecture exists to remove |
| Business recommendations, quantitative validation, anything the product itself produces | **Neither** — out of scope for a dev-workflow tool entirely; this is what StratAgent's own governed pipeline does, not a code-review assistant |
| A large, well-isolated bug with a reproducible failing test | **Codex** first pass (`/codex:rescue`), Claude reviews the fix against project conventions before merge |
| Anything ambiguous, or touching more than one subsystem's judgment calls | **Claude**, optionally with a Codex adversarial review afterward as a second check |

**Collaboration pattern:** Codex output is never merged un-reviewed. The
default flow is Codex produces a draft/patch/review → Claude (or a human)
verifies it against this project's actual conventions (CLAUDE.md, ADRs, test
suite) before it lands. This mirrors the same principle the product's own
governance gates encode: a proposal from one model is not truth until
something else checks it.

## Failure modes & fallback

- **Codex unavailable / not logged in:** every command degrades to "ask
  Claude directly" — nothing in this repo depends on Codex being present.
  There is no code path, CI job, or product feature that requires it.
- **Codex CLI not installed:** `/codex:setup` offers to install it; if
  declined or npm unavailable, fall back to Claude for the task.
- **A Codex-delegated task produces a bad result:** treat it like a bad PR
  from a contractor — review, request changes, or discard and redo with
  Claude. No auto-merge path exists for Codex output in this project.
- **Rate limits / usage caps:** Codex usage draws from the user's own ChatGPT
  or API quota (`Requirements` above) — a cap hit degrades to "use Claude for
  now," not a project outage.

## Validation status (honest, as of 2026-07-17)

Installation and configuration are verified (`claude plugin list` shows
`codex@openai-codex`, enabled, version 1.0.6). **Live task validation — actually
running `/codex:review`, `/codex:rescue`, etc. against this repo and measuring
quality/speed/correctness — has NOT been performed yet.** It requires
`/codex:setup` + login, which is the user's step by design (Claude never
handles OpenAI credentials). This is stated plainly rather than assumed:
until a real run happens, "Codex works well for X" is a documented
expectation, not a proven result.

## Recommendation (preliminary — pending live validation above)

**Optional, task-scoped — not mandatory.** Reasoning:

- Nothing about StratAgent's architecture or quality bar depends on Codex
  existing; making it mandatory would add an external dependency (OpenAI
  auth, npm global install, a second vendor's uptime) to a workflow that
  currently has none.
- Its highest-confidence value (per the table above) is bounded to
  mechanical/boilerplate/independent-review work — real value, but not
  central to what makes engagements correct (that's ADR-009/010's
  deterministic gates, which stay Claude/code-only by design).
- A firmer recommendation (mandatory for a specific task class, e.g. "every
  PR gets a `/codex:adversarial-review` before merge") is reasonable to revisit
  once real usage data exists — this document should be updated with actual
  measurements at that point, not left as a permanent "preliminary" note.
