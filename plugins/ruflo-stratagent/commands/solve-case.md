---
name: solve-case
description: Run a full management-consulting engagement on a business problem — classify the case, scope it, dispatch specialist consultants, challenge the findings, and produce an executive report.
argument-hint: "<paste the case prompt or describe the business problem>"
---

$ARGUMENTS

Run a complete StratAgent consulting engagement on the problem above.

Follow the engagement lifecycle defined in the **`solve-case` skill** (Phases 0–6: classify → scope → frame → analyze → challenge → synthesize → close out). Dispatch the specialist subagents shipped in this plugin — `case-classifier`, `framework-strategist`, `financial-analyst`, `market-analyst`, `operations-analyst`, `challenger`, `report-writer` — and ground framework selection in the knowledge base under this plugin's `knowledge/frameworks/` directory.

Always run the `challenger` phase before producing the final report. Preserve `[ASSUMPTION]` labels end to end.

If no case text was provided above, ask the user to paste the case prompt or describe the business situation before proceeding.
