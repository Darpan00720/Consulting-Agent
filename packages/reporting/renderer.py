"""Consulting report renderer — Markdown from EngagementState (M7).

``render_report`` is a *pure function*: same state → same report string,
no filesystem access, no randomness.  Every claim it emits either cites an
evidence record, is labeled ``[ASSUMPTION: ...]``, or is drawn verbatim from
the client brief.

Section order (consulting convention):
  Executive Summary · Situation · Framework & Approach · Issue Tree ·
  Analysis · Recommendation · Risks & Caveats · Implementation Roadmap ·
  Appendix A (Assumptions) · Appendix B (Evidence) ·
  Appendix C (Confidence) · Appendix D (Knowledge References)
"""

from __future__ import annotations

from datetime import UTC, datetime

from state.models import EngagementState
from state.sections.analysis import AnalysisBlock
from state.sections.enums import IssueNodeStatus
from state.sections.planning import IssueNode

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_report(state: EngagementState) -> str:
    """Return a complete consulting report as a Markdown string.

    Does not raise if optional sections (recommendations, analysis blocks)
    are missing — renders each section as "Pending" / omitted gracefully.
    """
    parts: list[str] = [
        _header(state),
        _executive_summary(state),
        _situation(state),
        _frameworks(state),
        _issue_tree(state),
        _analysis(state),
        _recommendation(state),
        _risks(state),
        _roadmap(state),
        _appendix_assumptions(state),
        _appendix_evidence(state),
        _appendix_confidence(state),
        _appendix_knowledge(state),
        _footer(state),
    ]
    return "\n\n---\n\n".join(p for p in parts if p.strip())


# ---------------------------------------------------------------------------
# Section renderers (private, pure functions of state)
# ---------------------------------------------------------------------------


def _header(state: EngagementState) -> str:
    slug = state.metadata.slug
    now = datetime.now(UTC).strftime("%Y-%m-%d")
    archetype = (
        state.classification.primary_archetype.value.replace("_", " ").title()
        if state.classification
        else "Unknown"
    )
    lines = [
        f"# Consulting Report: {slug}",
        "",
        f"**Engagement ID:** `{state.metadata.engagement_id}`  ",
        f"**Generated:** {now}  ",
        f"**Case Archetype:** {archetype}  ",
        f"**Status:** {state.status.value.replace('_', ' ').title()}  ",
    ]
    return "\n".join(lines)


def _executive_summary(state: EngagementState) -> str:
    rec = state.recommendations
    challenge = state.challenge_notes

    lines = ["## Executive Summary"]

    if rec and rec.decision:
        lines.append("")
        lines.append(f"**Recommendation:** {rec.decision}")
        if rec.rationale:
            lines.append("")
            lines.append(rec.rationale)
    else:
        lines.append("")
        lines.append("*Recommendation pending — engagement analysis not yet complete.*")

    # Biggest caveat from challenger
    if challenge and challenge.what_would_change:
        lines.append("")
        lines.append("**Key caveat:** " + challenge.what_would_change[0])
    elif challenge and challenge.counter_case:
        lines.append("")
        lines.append(f"**Key caveat:** {challenge.counter_case}")

    return "\n".join(lines)


def _situation(state: EngagementState) -> str:
    lines = ["## Situation Assessment"]

    if state.problem and state.problem.real_question:
        lines.append("")
        lines.append(f"**The real question:** {state.problem.real_question}")

    if state.problem and state.problem.raw_input:
        lines.append("")
        lines.append("**Original brief:**")
        lines.append("")
        # Indent the brief as a blockquote
        for line in state.problem.raw_input.strip().splitlines():
            lines.append(f"> {line}")

    if state.objectives:
        lines.append("")
        lines.append("**Objectives:**")
        for obj in state.objectives:
            priority = f" (P{obj.priority})" if obj.priority is not None else ""
            metric = f" — metric: {obj.metric}" if obj.metric else ""
            lines.append(f"- {obj.statement}{priority}{metric}")

    if state.constraints:
        lines.append("")
        lines.append("**Constraints:**")
        for c in state.constraints:
            hard = " [HARD]" if c.hard else ""
            lines.append(f"- {c.statement} *(type: {c.type.value}){hard}*")

    if state.stakeholders:
        lines.append("")
        lines.append("**Key stakeholders:**")
        for s in state.stakeholders:
            interest = f" — {s.interest}" if s.interest else ""
            lines.append(f"- {s.name_or_role} ({s.relationship.value}){interest}")

    return "\n".join(lines)


def _frameworks(state: EngagementState) -> str:
    if not state.frameworks:
        return ""

    lines = ["## Framework & Analytical Approach"]
    for fw in state.frameworks:
        lines.append("")
        lines.append(f"### {fw.name}")
        if fw.archetype:
            lines.append(f"*Archetype:* {fw.archetype.value.replace('_', ' ')}")
        if fw.rationale:
            lines.append("")
            lines.append(fw.rationale)
        if fw.adaptation:
            lines.append("")
            lines.append(f"**Adaptation:** {fw.adaptation}")
        if fw.source_ref:
            lines.append("")
            lines.append(f"*Source:* `{fw.source_ref}`")

    return "\n".join(lines)


def _issue_tree(state: EngagementState) -> str:
    if not state.issue_tree:
        return ""

    lines = ["## Issue Tree"]
    lines.append("")

    children: dict[str, list[IssueNode]] = {}
    roots: list[IssueNode] = []
    for node in state.issue_tree:
        if node.parent is None:
            roots.append(node)
        else:
            children.setdefault(node.parent, []).append(node)

    def _render_node(node: IssueNode, depth: int) -> None:
        indent = "  " * depth
        status_icon = (
            "✓"
            if node.status == IssueNodeStatus.ANSWERED
            else "○" if node.status == IssueNodeStatus.OPEN else "⋯"
        )
        owner = f" *[{node.owner}]*" if node.owner else ""
        conf = ""
        if node.confidence is not None:
            conf = f" (confidence: {node.confidence:.0%})"
        lines.append(f"{indent}- {status_icon} **{node.question}**{owner}{conf}")
        if node.answer:
            lines.append(f"{indent}  > {node.answer}")
        for child in children.get(node.id, []):
            _render_node(child, depth + 1)

    for root in roots:
        _render_node(root, 0)

    return "\n".join(lines)


def _analysis(state: EngagementState) -> str:
    _SECTIONS: list[tuple[str, AnalysisBlock | None]] = [
        ("Financial Analysis", state.financial_analysis),
        ("Market Analysis", state.market_analysis),
        ("Operations Analysis", state.operations_analysis),
        ("Strategic Analysis", state.strategy_analysis),
        ("Risk Assessment", state.risk_analysis),
    ]

    active = [(label, block) for label, block in _SECTIONS if block is not None]
    if not active:
        return ""

    lines = ["## Analysis"]

    for label, block in active:
        lines.append("")
        lines.append(f"### {label}")
        if block.owner:
            lines.append(f"*Analyst: {block.owner}*")
        for finding in block.findings:
            lines.append("")
            lines.append(f"**Q:** {finding.question}")
            if finding.answer:
                # Label if assumption-only
                is_assumed = bool(finding.assumption_refs) and not bool(
                    finding.evidence_refs
                )
                prefix = "[ASSUMPTION: " if is_assumed else ""
                suffix = "]" if is_assumed else ""
                lines.append(f"**A:** {prefix}{finding.answer}{suffix}")
            else:
                lines.append("**A:** *Pending*")
            if finding.method:
                lines.append(f"*Method: {finding.method}*")
            if finding.evidence_refs:
                refs = ", ".join(f"`{r}`" for r in finding.evidence_refs)
                lines.append(f"*Evidence: {refs}*")
            if finding.assumption_refs:
                refs = ", ".join(f"`{r}`" for r in finding.assumption_refs)
                lines.append(f"*Assumptions: {refs}*")
            if finding.confidence is not None:
                lines.append(f"*Confidence: {finding.confidence:.0%}*")
        if block.sensitivity:
            lines.append("")
            lines.append("**Sensitivity analysis:**")
            for sc in block.sensitivity:
                lines.append(
                    f"- {sc.driver}: base={sc.base or 'N/A'},"
                    f" stress={sc.stress or 'N/A'} → {sc.effect or 'N/A'}"
                )

    return "\n".join(lines)


def _recommendation(state: EngagementState) -> str:
    rec = state.recommendations
    lines = ["## Recommendation"]

    if not rec or not rec.decision:
        lines.append("")
        lines.append("*Recommendation pending.*")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"**Decision:** {rec.decision}")

    if rec.rationale:
        lines.append("")
        lines.append(rec.rationale)

    if rec.next_steps:
        lines.append("")
        lines.append("**Next steps:**")
        sorted_steps = sorted(
            rec.next_steps, key=lambda s: s.sequence if s.sequence is not None else 999
        )
        for i, step in enumerate(sorted_steps, 1):
            deps = ""
            if step.depends_on:
                deps = f" *(after: {', '.join(step.depends_on)})*"
            lines.append(f"{i}. {step.step}{deps}")

    if rec.alternatives_rejected:
        lines.append("")
        lines.append("**Alternatives considered and rejected:**")
        for alt in rec.alternatives_rejected:
            reason = f" — {alt.why_not}" if alt.why_not else ""
            lines.append(f"- {alt.option}{reason}")

    return "\n".join(lines)


def _risks(state: EngagementState) -> str:
    challenge = state.challenge_notes
    if not challenge:
        return ""

    lines = ["## Risks & What Would Change the Answer"]

    if challenge.loadbearing_test:
        lines.append("")
        lines.append("### Load-Bearing Assumption Test")
        lines.append("")
        lines.append(challenge.loadbearing_test)

    if challenge.counter_case:
        lines.append("")
        lines.append("### Strongest Counter-Case")
        lines.append("")
        lines.append(challenge.counter_case)

    if challenge.what_would_change:
        lines.append("")
        lines.append("### What Would Change the Answer")
        for item in challenge.what_would_change:
            lines.append(f"- {item}")

    verdict = challenge.verdict
    if verdict:
        lines.append("")
        lines.append(
            f"**Challenger verdict:** `{verdict.value}` "
            f"— {_CHALLENGE_VERDICT_LABELS.get(verdict.value, verdict.value)}"
        )

    return "\n".join(lines)


_CHALLENGE_VERDICT_LABELS: dict[str, str] = {
    "stands": "recommendation survives all checks.",
    "stands_with_caveats": "recommendation holds with the caveats noted above.",
    "needs_rework": "recommendation requires revision before use.",
}


def _roadmap(state: EngagementState) -> str:
    rec = state.recommendations
    if not rec or not rec.next_steps:
        return ""

    lines = ["## Implementation Roadmap"]
    lines.append("")
    sorted_steps = sorted(
        rec.next_steps, key=lambda s: s.sequence if s.sequence is not None else 999
    )
    for i, step in enumerate(sorted_steps, 1):
        deps = ""
        if step.depends_on:
            deps = f" *(depends on: {', '.join(step.depends_on)})*"
        lines.append(f"{i}. {step.step}{deps}")

    return "\n".join(lines)


def _appendix_assumptions(state: EngagementState) -> str:
    if not state.assumptions:
        return ""

    lines = [
        "## Appendix A: Assumptions Ledger",
        "",
        "Every `[ASSUMPTION: ...]` used in this engagement is recorded here "
        "with its owner, confidence, and breakeven threshold.",
        "",
        "| ID | Statement | Value | Owner | Conf. | Load-Bearing | Breakeven |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in state.assumptions:
        lb = "✓" if a.load_bearing else ""
        be = a.breakeven or ""
        conf = f"{a.confidence:.0%}"
        # Truncate for table readability
        stmt = a.statement[:60] + ("…" if len(a.statement) > 60 else "")
        val = a.value[:40] + ("…" if len(a.value) > 40 else "")
        lines.append(
            f"| `{a.id[:8]}` | {stmt} | {val} | {a.owner} | {conf} | {lb} | {be} |"
        )

    return "\n".join(lines)


def _appendix_evidence(state: EngagementState) -> str:
    if not state.evidence:
        return ""

    lines = [
        "## Appendix B: Evidence References",
        "",
        "| ID | Claim | Type | Source / Method | Conf. | Validated |",
        "|---|---|---|---|---|---|",
    ]
    for ev in state.evidence:
        source = ev.source or ev.method or ""
        conf = f"{ev.confidence:.0%}"
        validated = "✓" if ev.validated else ""
        claim = ev.claim[:60] + ("…" if len(ev.claim) > 60 else "")
        source_short = source[:40] + ("…" if len(source) > 40 else "")
        lines.append(
            f"| `{ev.id[:8]}` | {claim} | {ev.type.value} |"
            f" {source_short} | {conf} | {validated} |"
        )

    return "\n".join(lines)


def _appendix_confidence(state: EngagementState) -> str:
    conf = state.confidence
    if not conf:
        return ""

    lines = ["## Appendix C: Confidence Scores"]
    if conf.overall is not None:
        lines.append("")
        lines.append(f"**Overall:** {conf.overall:.0%}")
    if conf.method:
        lines.append(f"*Method: {conf.method}*")
    if conf.by_section:
        lines.append("")
        lines.append("| Section | Score |")
        lines.append("|---|---|")
        for section, score in sorted(conf.by_section.items()):
            lines.append(f"| {section} | {score:.0%} |")
    if conf.drivers:
        lines.append("")
        lines.append("**Confidence drivers:**")
        for d in conf.drivers:
            lines.append(f"- {d}")

    return "\n".join(lines)


def _appendix_knowledge(state: EngagementState) -> str:
    if not state.knowledge_references:
        return ""

    lines = [
        "## Appendix D: Knowledge References",
        "",
        "| Kind | Vault Path | Query | Relevance |",
        "|---|---|---|---|",
    ]
    for kr in state.knowledge_references:
        path = kr.vault_path or ""
        query = (kr.query or "")[:40]
        rel = f"{kr.relevance:.0%}" if kr.relevance is not None else ""
        lines.append(f"| {kr.kind.value} | {path} | {query} | {rel} |")

    return "\n".join(lines)


def _footer(state: EngagementState) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    reviewer_v = (
        state.reviewer_notes.verdict.value
        if state.reviewer_notes and state.reviewer_notes.verdict
        else "not run"
    )
    challenge_v = (
        state.challenge_notes.verdict.value
        if state.challenge_notes and state.challenge_notes.verdict
        else "not run"
    )
    gates = f"Reviewer: {reviewer_v} | Challenger: {challenge_v}"
    return (
        f"---\n\n"
        f"*Generated by StratAgent RC1 at {now}.*  \n"
        f"*Governance gates — {gates}.*  \n"
        f"*All `[ASSUMPTION: ...]` labels from the analysis are preserved verbatim.*"
    )
