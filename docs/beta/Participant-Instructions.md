# StratAgent Beta — Participant Instructions

Welcome, and thank you for helping validate StratAgent. This is a **supervised
beta**: you will run real consulting engagements and tell us, honestly, where the
system helps and where it falls short. Read this once before you start.

---

## What StratAgent is (and isn't)

StratAgent takes a business problem and runs a full consulting engagement —
classify → scope → frame → analyze → **review → challenge** → report. It produces
an executive-style report with an **Assumptions Ledger** and two governance
verdicts (Reviewer, Challenger).

**It is a drafting and stress-testing partner, not an oracle.**
- Any number it gives you is an **assumption** unless *you* supplied the data.
  The report labels these `[ASSUMPTION]`.
- Re-running the same problem may give a different answer. That's expected.
- **You** own the final recommendation. A qualified human must review every
  number before you act on or share anything.

---

## Setup (one-time)

1. Confirm you can run `/solve-case` in your StratAgent environment (the
   onboarding session covers this).
2. Sign the consent + ethics acknowledgment.
3. Skim the [Ethics & Appropriate Use](Beta-Program-Guide.md#5-ethics--appropriate-use-full)
   section — especially the **prohibited uses**.

---

## Your assignment

Complete **3–5 engagements** over 4 weeks:
- **≥1 guided benchmark case** we assign (so we can compare across participants).
- **≥2 bring-your-own (BYO)** real problems from your work or studies.

For at least one engagement, **supply your own data/facts** in the prompt (real
numbers you have) so we can see how the system does with grounded inputs vs.
assumptions.

---

## How to run one engagement

1. **Write the problem** as you'd brief a consultant: the situation, any real
   numbers you have, the decision to make, constraints. A few sentences is fine.
2. Run `/solve-case <your problem>`.
3. **Do not hand-edit or coach the output mid-run.** Let the real pipeline run.
   We are evaluating the system, not your editing.
4. When the report is produced, **read it the right way** (below).
5. Fill in the [post-engagement form](Evaluation-Forms.md) (~5 minutes) while it's
   fresh.

**Note on time:** an engagement runs a dozen specialist steps and can take
several minutes to tens of minutes. That is normal for this beta.

---

## How to read a StratAgent report

Read these four things first — they are where the value and the risk live:

1. **Executive summary** — the recommendation, the why, and the single biggest
   caveat. Does it answer your real question?
2. **Assumptions Ledger (appendix)** — every `[ASSUMPTION]` with its confidence
   and *breakeven* (the condition under which the recommendation flips). **Check
   each one.** If an assumption is wrong for your situation, note it.
3. **Challenger verdict** — `stands` / `stands_with_caveats` / `needs_rework`,
   plus "what would change the answer." This is the system arguing against itself;
   it is often the most useful part.
4. **Evidence references** — what's a client fact vs. an assumption. Anything not
   backed by data *you* supplied is the model's assumption.

---

## What to record (per engagement)

The [post-engagement form](Evaluation-Forms.md) captures it, but keep rough notes
on:
- Wall-clock time to the first usable recommendation.
- Would you **act** on this (after review)? What would you change first?
- How many numbers did you have to verify or override?
- Anything the analysis **missed** that you, as the domain person, know matters.
- Any point where the workflow was confusing or frustrating.

---

## Do / Don't

**Do:** supply real data when you have it; check every number; use the Challenger
section; report failures bluntly (we want them); try a hard/ambiguous problem.

**Don't:** act on any output without human review; use it for a prohibited case
(regulated finance/legal/medical, live trading, irreversible high-stakes calls);
hand-fix the output before scoring it; treat an assumption as a fact.

---

## Support & cadence

- Weekly 2-minute pulse survey (link provided).
- Optional 30-minute interview if selected (we'll ask).
- Report blocking issues to the beta channel; we log every failure.

Your honest negative feedback is the most valuable thing you can give us.
