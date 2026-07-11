# StratAgent RC1 — Independent Engineering Audit

**Date:** 2026-07-09  
**Reviewer:** Principal Engineer (Independent)  
**Scope:** Full repository, commit `3cb863a` (0.1.0-rc1)  
**Baseline:** 861 tests, ruff clean, mypy strict (72 source files)

---

## Audit Summary

| Dimension | Score | Notes |
|---|---|---|
| Architecture | 9/10 | ADR-based design complete; ADRs still "Proposed" |
| Code Quality | 8/10 | Lint-clean; leaf detection duplicated 3×; one dead code path |
| Agent Design | 8/10 | All 16 agents well-specified; ADR-005 ownership tables incomplete |
| State Management | 9/10 | Frozen Pydantic v2 throughout; transition graph complete |
| Test Coverage | 8/10 | 94–100% per package; 1 flaky test; 1 public API gap |
| Security | 9/10 | `yaml.safe_load` ✓; subprocess list-form ✓; `vault_dir` unconstrained |
| Performance | 9/10 | render_report 22 µs warm; O(N²) MECE acceptable for N < 50 |
| Documentation | 8/10 | QUICKSTART + USER_GUIDE present; no DEVELOPER_GUIDE; agent ownership incomplete |
| **Composite** | **8.5/10** | |

### Verdict

> **PASS WITH MINOR ISSUES**

No Critical or High findings. Five Medium findings should be addressed before the 1.0 GA release. The codebase is production-ready at RC1 quality.

---

## Phase 1 — Architecture Review

**Files read:** ADR-001, ADR-002 (§§1-4), ADR-005 (§§1-4), Architecture-v1.0.md,
`governance/transitions.py`, `state/enums.py` (via imports).

### Findings

**[A-1] Low — ADRs not ratified**  
All five ADRs (`ADR-001` through `ADR-005`) carry `status: Proposed`. No
ratification record exists. For a production system, ADRs should reach
`status: Accepted` with a decision date and decider.

**[A-2] Informational — State machine faithfully implemented**  [Verified]  
The 13-node lifecycle graph in ADR-002 §2 is exactly encoded in
`governance/transitions.py:_ALLOWED` (15 positive edges) plus the
any-non-terminal → FAILED/ABORTED escape hatch. Terminal-lock is enforced
before the positive-edge lookup. No gaps.

**[A-3] Informational — Governance gate layering is clean**  [Verified]  
`planning.preconditions` encodes structural pre-conditions (tree ownership,
analysis presence). `governance.gates` encodes behavioural post-conditions
(reviewer verdict, challenger verdict). The two layers do not call each
other — correctly isolated.

---

## Phase 2 — Code Quality Review

**Files read:** `planning/mece_validator.py`, `planning/preconditions.py`,
`governance/gates.py`, `governance/transitions.py`, `analysis/contracts.py`,
`reporting/renderer.py`, `reporting/validation.py`.

### Findings

**[C-1] Medium — Leaf detection logic duplicated three times**  
The pattern:
```python
parent_ids = {n.parent for n in state.issue_tree if n.parent}
leaves     = [n for n in state.issue_tree if n.id not in parent_ids]
```
appears verbatim at:
- `planning/preconditions.py:66–70` (`check_enter_governance` — checks unowned leaves)
- `planning/preconditions.py:86–89` (`check_enter_analysis` — checks unanswered leaves)
- `governance/gates.py:53–56` (`check_reviewer_can_run` — checks unanswered leaves)

If the leaf-extraction semantics need to change (e.g., to exclude a new
status), three sites must be updated in sync. Extract to a shared utility in
`state.sections.planning` or `planning._util`.

**[C-2] Low — `ASSUMPTION_NO_BREAKEVEN` check is unreachable in normal usage**  
`reporting/validation.py:119` (inside `check_render_ready`) checks:
```python
if assumption.load_bearing and not assumption.breakeven:
```
This branch cannot fire via normal Pydantic construction because the
`Assumption` model already enforces `load_bearing=True` → `breakeven` required
via `@model_validator`. The line shows as uncovered (0% for that branch).
It is harmless defensive code, but it misleads future maintainers who see
the coverage gap and hunt for missing tests. Either add a comment explaining
the invariant or use `model_construct` to test it.

**[C-3] Low — `validate_analysis_block` docstring lists 5 rules; code implements 4**  
`analysis/contracts.py:18–23` documents Rule 4 as "Block status must be COMPLETE
before Reviewer runs." No corresponding check exists in the function body
(that constraint is enforced by `governance.gates`, not this validator). The
docstring creates a false expectation for callers.

**[C-4] Low — `check_reporting_gate` name is misleading**  
`governance/gates.py:check_reporting_gate` internally calls
`check_challenger_can_run`, which in turn checks the reviewer verdict. The
name suggests it only checks challenger, but it also implicitly verifies
reviewer approval. Callers reading only the function signature cannot see
this. Either rename to `check_reporting_preconditions` or document the
transitive check explicitly.

---

## Phase 3 — Agent Design Review (ADR-005 Compliance)

**Files read:** all 16 agent `.md` files.

### Findings

**[AG-1] Medium — ADR-005 state ownership section missing from 15 of 16 agents**  
Only `report-writer.md` carries an explicit "ADR-005 state ownership" table
listing which sections the agent writes to. The remaining 15 agents specify
their output in prose but carry no machine-readable ownership declaration.
For a multi-agent system where ownership isolation is a core invariant
(ADR-005 §3), every agent should declare its write scope in a structured
section to make ownership auditable without reading body prose.

Agents that need sections added (examples of current implicit ownership):
- `reviewer.md` → writes `reviewer_notes`
- `challenger.md` → writes `challenge_notes`
- `financial-analyst.md` → writes `financial_analysis`
- (12 others similarly)

**[AG-2] Informational — Agent preconditions enforced via prose only**  [Verified]  
All agents state preconditions in their system prompt (e.g., `challenger.md`:
"Precondition: `state.reviewer_notes.verdict == approved`. If it is not, stop
immediately…"). There is no runtime enforcement; compliance depends on the LLM
reading and following the instruction. This is an inherent limitation of the
architecture and is acknowledged in ADR-005. The prose is clear and
consistently worded across agents.

---

## Phase 4 — State Management Review

**Files read:** `governance/transitions.py`, `state/enums.py` (via imports),
`state/sections/analysis.py`, `state/sections/governance.py`,
`state/sections/planning.py`.

### Findings

**[S-1] Verified — Frozen models throughout**  
All `EngagementState` sections are frozen Pydantic v2 models. Mutation is done
exclusively via `model_copy(update={...})`. No mutable defaults exist. No
in-place list/dict assignments seen in any package.

**[S-2] Verified — Terminal state lock**  
`is_transition_allowed` returns `False` immediately for any source in
`_TERMINAL = {COMPLETED, FAILED, ABORTED}`. This is checked before the
positive-edge lookup. Correct.

**[S-3] Verified — Rework loops complete**  
Three rework paths are encoded: `REVIEW → ANALYSIS`, `CHALLENGE → REVIEW`,
`CHALLENGE → ANALYSIS`. The integration test suite (`test_engagement_lifecycle.py`)
covers all three with dedicated parametrized cases. Pass.

---

## Phase 5 — Test Coverage Review

**Baseline:** 861 tests passing, ruff + mypy clean.  
**Coverage command:** `uv run pytest --cov=packages`

### Per-package coverage

| Package | Coverage | Notes |
|---|---|---|
| `analysis` | 100% | |
| `common` | 100% | |
| `core` | 100% | |
| `governance` | 96% | 2 missing: verdict=None edge in gates |
| `knowledge` | 94% | 8 missing: retrieval adapter error branches |
| `planning` | 96% | 2 missing: verdict-not-set edge in preconditions |
| `persistence` | 100% | |
| `replay` | 100% | |
| `reporting/__init__` | 86% | `engagement_summary()` uncovered — see [T-1] |
| `reporting/renderer` | 99% | 3 lines: pending-answer branch, counter_case fallback |
| `reporting/validation` | 99% | 1 line: ASSUMPTION_NO_BREAKEVEN (see [C-2]) |
| `state` | 99–100% | |

### Findings

**[T-1] Medium — `engagement_summary()` has zero test coverage**  
`reporting/__init__.py:15` exports `engagement_summary(state) → dict` as part
of the public 8-symbol API. No test exercises this function. It accesses
`state.problem`, `state.classification`, and `state.evidence`, making it a
real code path with conditional branches. Add at minimum one test with a
fully-populated state and one with a minimal state.

**[T-2] Medium — Flaky timing test**  
`tests/knowledge/test_retrieval_perf.py::test_retrieve_multiple_queries_consistent`
asserts `elapsed_ms <= 200` for 10 sequential `retrieve()` calls with no
retry margin and no tolerance. This test has been observed to fail when the
full suite runs under `--cov` (coverage instrumentation adds overhead). It
passes in isolation. The fix is to either raise the wall to 500ms, add a
`±20%` tolerance, or restructure as an observational benchmark (no assertion).

**[T-3] Low — Renderer edge-branch gaps (lines 104–105, 247)**  
`renderer.py:104–105` is the `elif challenge and challenge.counter_case` branch
(reached when `what_would_change` is empty but `counter_case` exists).
`renderer.py:247` is the `"**A:** *Pending*"` path (a finding with `answer=None`
in an active analysis section). Both are valid run-time states; both are
missing from `test_report_generation.py`.

---

## Phase 6 — Security Review

**Files read:** `knowledge/frontmatter_validator.py`, `knowledge/retrieval_adapter.py`,
`knowledge/vault_validator.py`.

### Findings

**[SE-1] Verified — YAML parsing is safe**  
`frontmatter_validator.py:40` uses `yaml.safe_load(block)`. No `yaml.load()` with
an `Loader` argument exists in the codebase. No YAML deserialisation
vulnerability.

**[SE-2] Verified — Subprocess call is injection-safe**  
`retrieval_adapter.py:166` calls:
```python
subprocess.run(["git", "rev-parse", "HEAD"], ...)
```
List form with no `shell=True`. No user input flows into the argument list.
Clean.

**[SE-3] Low — `vault_dir` is not constrained to the repo root**  
`retrieve(query, *, vault_dir=Path("knowledge-vault"))` accepts an arbitrary
path and only validates `vault_dir.is_dir()`. A caller could pass
`vault_dir=Path("/")`, causing `rglob("*.md")` to scan the entire filesystem.
For a CLI tool invoked by the orchestrator (not external users), this risk is
low but worth documenting. Add a check that resolves the path and ensures
it lies within a safe root, or at minimum document the trusted-caller
assumption.

---

## Phase 7 — Performance Review

**Baselines (from `tests/perf/test_m7_bench.py`, measured under `--cov`):**

| Operation | Cold | Warm |
|---|---|---|
| `render_report` (golden state) | ~126 µs | ~22 µs |
| `check_render_ready` | — | ~3 µs |
| `validate_consistency` | — | ~2 µs |

### Findings

**[P-1] Verified — Renderer performance is adequate**  
At 22 µs warm, `render_report` could run 45,000 times per second. No concern
for a consulting engagement tool where this is called once per engagement.

**[P-2] Low — MECE cycle detection is O(N²) worst-case; no documented limit**  
`planning/mece_validator.py:_has_cycle()` uses DFS without a visited set across
all root nodes. For a tree of N nodes, worst-case is O(N²). Acceptable for
the expected consulting use-case (N < 50 per ADR-002 guidance), but that limit
is not documented. Add a comment in `validate_mece()` stating the expected
scale boundary, or add an input guard (`if len(nodes) > 200: raise`).

**[P-3] Informational — Knowledge retrieval rescans vault on every call**  
`retrieve()` calls `vault_dir.rglob("*.md")` and reads/parses every file on
each invocation. For 132 notes this takes ~75 ms (observed in benchmarks).
At 10k notes this would be ~6 s per query. No caching layer exists.
Acceptable for CLI / single-engagement use; would need an in-memory index
at service scale.

---

## Phase 8 — Documentation Review

**Files checked:** `docs/guides/`, `docs/architecture/`, `docs/reviews/`,
`docs/implementation/DEV.md`, `plugins/ruflo-stratagent/README.md`,
`CLAUDE.md`.

### Findings

**[D-1] Low — No DEVELOPER_GUIDE for package contributors**  
`docs/guides/` contains `QUICKSTART.md` (user-facing) and `USER_GUIDE.md`
(user-facing). `docs/implementation/DEV.md` exists but is a short setup
checklist, not an architectural guide. A developer wanting to add a new
analysis package (e.g., `packages/synthesis/`) has no single document
describing the package contract, the import path convention (`pythonpath =
["packages"]`), the required `__init__.py` `__all__` pattern, or how to
write tests that use golden-state fixtures.

**[D-2] Informational — `docs/implementation/` contains milestone-scoped files**  
Design documents (`M3-Design.md`, `M1.7-Design.md`, etc.) serve as historical
ADR supplements. They are well-structured and clearly scoped. No drift or
contradiction with the current codebase was found.

**[D-3] Informational — RC1 release notes are accurate**  
`docs/reviews/RC1-Release-Notes.md` correctly lists all milestones (M1–M9),
cumulative test counts, known limitations (flaky retrieval test, O(N²) MECE),
and upgrade path. Findings [T-2] and [P-2] from this audit confirm those
known-limitations entries.

---

## Findings Summary

### Medium (address before 1.0 GA)

| ID | Location | Finding |
|---|---|---|
| C-1 | `planning/preconditions.py:66,86` · `governance/gates.py:53` | Leaf detection logic duplicated 3× — extract to shared utility |
| T-1 | `reporting/__init__.py:15` | `engagement_summary()` has 0 test coverage |
| T-2 | `tests/knowledge/test_retrieval_perf.py` | Flaky 200ms hard wall — add tolerance or convert to observational |
| AG-1 | All agent `.md` files except `report-writer.md` | ADR-005 state ownership table missing |

### Low (backlog for 1.0 GA)

| ID | Location | Finding |
|---|---|---|
| C-2 | `reporting/validation.py:119` | ASSUMPTION_NO_BREAKEVEN is unreachable via normal Pydantic construction |
| C-3 | `analysis/contracts.py:18` | Docstring lists 5 rules; only 4 implemented |
| C-4 | `governance/gates.py:check_reporting_gate` | Function name does not convey transitive reviewer check |
| T-3 | `reporting/renderer.py:104,247` | Two edge branches untested (counter_case, pending answer) |
| SE-3 | `knowledge/retrieval_adapter.py:195` | vault_dir accepts any filesystem path |
| P-2 | `planning/mece_validator.py` | O(N²) cycle detection limit not documented |
| D-1 | `docs/guides/` | No DEVELOPER_GUIDE for package contributors |
| A-1 | All ADRs | status: Proposed; never ratified |

---

## Recommended Actions Before 1.0 GA

1. **Extract `_leaf_nodes(issue_tree)`** into `planning/_util.py` and replace
   the three duplicate call sites. 15-minute change, eliminates a maintenance
   synchronisation risk. [C-1]

2. **Test `engagement_summary()`** — add one test with a full golden state and
   one with `EngagementState(metadata=...)` minimal state. [T-1]

3. **Fix or guard `test_retrieve_multiple_queries_consistent`** — raise the
   wall to 500ms or split into a hard-timeout smoke test plus an observational
   benchmark. [T-2]

4. **Add ADR-005 ownership sections to remaining 15 agents** — a consistent
   table format per `report-writer.md`. [AG-1]

5. **Write `docs/guides/DEVELOPER_GUIDE.md`** covering: package layout, import
   path convention, `__all__` requirements, golden-state fixture pattern. [D-1]

---

## Production Readiness Verdict

> **PASS WITH MINOR ISSUES**

StratAgent RC1 (`3cb863a`, 0.1.0-rc1) is **production-ready** for the
consulting-engagement use-case. The state machine is complete and enforced,
evidence traceability is structural not aspirational, governance gates are
non-bypassable in code, and the test suite provides 94–100% package-level
coverage. The five Medium findings are all addressable in under a day of
engineering effort and carry no production-breakage risk at current scale.

The system should not be promoted to 1.0 GA without closing C-1, T-1, T-2,
and AG-1. D-1 (developer guide) is a quality-of-life issue for future
contributors, not a production concern.
