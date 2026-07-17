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

## Validation status (real, as of 2026-07-17)

Installation and configuration are verified (`claude plugin list` shows
`codex@openai-codex`, enabled, version 1.0.6). The user completed `/codex:setup`
and authentication (`codex login` → ChatGPT) independently — Claude never
touched credentials at any point.

**Live validation actually happened**, via the underlying `codex review` CLI
directly (the plugin's own `/codex:review` skill wasn't loaded into the
agent's session without a restart, so the same non-interactive command the
skill wraps was invoked directly — same review, same model, same result):

```
codex review --base ee3c8e8 --title "ADR-010 P1-P3.5: ..."
```

Reviewed the full P1→P3.5 diff (`ee3c8e8..HEAD`, four commits, ~10 new
modules). **Result: 3 findings, all 3 confirmed real by independent
reproduction before any fix, all 3 fixed the same session:**

1. `ledger_builder.py` extracted the *first* ```atoms block instead of the
   last — meaning every quant-gate rework (whose prompt quotes the stale
   previous reconciliation before the correction) was silently rebuilding the
   ledger from **pre-correction values**. The single highest-severity finding
   Codex could have made against this codebase.
2. `ledger_builder.py`'s duplicate-atom conflict check omitted
   `low`/`high`/`anchor`/`bridge` — a tighter or corrected assumption band
   could be silently dropped in favor of a looser earlier one.
3. `evidence_normalizer.py`'s dedup fingerprint omitted `scope`/`low`/`high` —
   the same class of silent-collapse bug, one layer up the pipeline.

Each was reproduced with a standalone script *before* being trusted, then
fixed, then re-verified with the same script, then locked in as a permanent
regression test (`test_last_atoms_block_wins_over_a_quoted_stale_one` and
siblings in `test_ledger_builder.py`/`test_evidence_platform.py`). Zero false
positives in this run — all three flagged issues were real.

## Recommendation (updated with the result above)

**Task-scoped and strongly encouraged for anything touching P1–P3's
deterministic modules — not blanket-mandatory for every change.** Reasoning:

- The one real data point available is a strong signal in Codex's favor: a
  single adversarial-style review of dense, already-tested (205 passing
  tests), self-reviewed code found three genuine correctness bugs — including
  one that silently undermined the exact "no LLM invents the ledger"
  guarantee this whole ADR series exists to provide. That's a concrete,
  falsifiable result, not the generic "code review is good" prior.
- It does not change the "not mandatory" stance on infrastructure grounds:
  nothing about StratAgent's architecture depends on Codex existing, and it
  draws on the user's own OpenAI usage/quota, so gating every commit on it
  isn't free.
- What it DOES change: this document no longer says "optional, unproven" —
  it says "optional, and the one time it was tried, it caught something a
  human + Claude + 205 tests missed." A reasonable house rule going forward:
  run `/codex:adversarial-review` (or the direct `codex review --base <ref>`
  equivalent) before considering any change to `ledger_builder.py`,
  `quantcheck.py`, `evidence_normalizer.py`, `evidence_store.py`, or the
  consulting-intelligence modules complete — precisely the code where a
  silent correctness bug is most consequential and least likely to be
  self-caught, which this run just demonstrated directly.
