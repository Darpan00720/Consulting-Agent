"""Append pipeline — orchestration only (M1.7.3-S4, design §5/§6).

Module contract (architectural boundary): composes S1 contracts, S2
arithmetic, S3 decisions, M1.5/M1.7.2 projection, and M1.6 validation. Owns
phase ordering, candidate assembly, the boundary raise, and result
production — nothing else.

**Fixed execution order (architectural contract — never reorder):**
Decision → Allocation → Projection → Validation → Commit.

Ownership matrix: S1 errors · S2 arithmetic · S3 decisions · S4
orchestration · M1.5 projection · M1.6 validation. The pipeline performs no
arithmetic (P17: versions and sequence numbers flow only through S2's
``current_version``/``current_sequence``/``stamp``; it never reads the seq
field off event metadata) and owns no business rules (P19: validation only via
the M1.6 runner; individual rule modules are never imported). It constructs
no ``Committed`` snapshots (P21/P23: that is ``make_committed``'s monopoly).

Commit gate (severity semantics, **not** ``report.valid``): a candidate
commits iff its ERROR count == 0 and FATAL count == 0. INFO and WARNING never
block and are returned in ``AppendResult.warnings``.

Append capability (``append_supported``, invariant P24): the facade owns
provenance, the pipeline owns capability — the flag is always supplied
explicitly at construction and is never inferred from state, version numbers,
or log contents. When it is False, appends raise ``AppendUnsupportedError``
before any phase executes. This restriction is temporary: M1.8 introduces
persisted event logs, M1.9 replay-backed engagements remove this limitation,
and the ``append_supported`` flag exists solely during the transition period —
it is not permanent architecture.
"""

from __future__ import annotations

from collections.abc import Sequence

from state.append.commit import CandidateCommit, Committed, StateUpdater, make_committed
from state.append.errors import AppendUnsupportedError
from state.append.guard import check_append
from state.append.result import AppendResult
from state.append.sequencing import stamp
from state.append.versioning import current_sequence, current_version
from state.events import Event
from state.models import EngagementState
from state.projection import PROJECTION_VERSION, apply
from state.validation import (
    StateValidationError,
    ValidationReport,
    ViolationSeverity,
    validate,
)


def _blocking(report: ValidationReport) -> bool:
    """The commit gate: ERROR/FATAL counts, never ``report.valid``."""
    return (
        report.counts[ViolationSeverity.ERROR] > 0
        or report.counts[ViolationSeverity.FATAL] > 0
    )


class AppendPipeline:
    """Guarded, atomic, all-or-nothing append over a committed snapshot."""

    def __init__(
        self,
        initial_state: EngagementState,
        *,
        log: Sequence[Event] = (),
        append_supported: bool = True,
        updater_cls: type[StateUpdater] = StateUpdater,
    ) -> None:
        self._append_supported = append_supported
        genesis = CandidateCommit(
            log=tuple(log),
            state=initial_state,
            event_ids=frozenset(e.metadata.event_id for e in log),
            validation_report=validate(initial_state),  # recorded, not gated
            events=(),
        )
        self._updater = updater_cls(make_committed(genesis))

    @property
    def updater(self) -> StateUpdater:
        """The commit point (exposed for S5 wiring and test doubles)."""
        return self._updater

    @property
    def append_supported(self) -> bool:
        """Whether appends are currently supported (capability, not provenance)."""
        return self._append_supported

    def committed(self) -> Committed:
        """The current committed snapshot."""
        return self._updater.read()

    def append_event(self, event: Event, *, expected_version: int) -> AppendResult:
        """Append one event (identical contract to a one-event batch)."""
        return self._append([event], expected_version)

    def append_events(
        self, events: Sequence[Event], *, expected_version: int
    ) -> AppendResult:
        """Atomic batch append: one guard pass, one validation, one commit."""
        return self._append(list(events), expected_version)

    def _append(self, events: list[Event], expected_version: int) -> AppendResult:
        # Capability boundary (P24): an unsupported pipeline never enters the
        # phase machine — nothing decided, allocated, folded, judged, committed.
        if not self._append_supported:
            raise AppendUnsupportedError()
        snapshot = self._updater.read()
        # Phase 1 — Decision (S3)
        decision = check_append(
            events,
            engagement_id=snapshot.state.metadata.engagement_id,
            committed_version=snapshot.version,
            committed_event_ids=snapshot.event_ids,
            expected_version=expected_version,
        )
        if not decision.admitted:
            assert decision.error is not None  # G4: rejected => error present
            raise decision.error
        # Phase 2 — Allocation (S2)
        first_seq = current_sequence(snapshot.log)
        stamped = stamp(events, first_seq=first_seq)
        # Phase 3 — Projection (M1.5 / M1.7.2)
        state = snapshot.state
        for event in stamped:
            state = apply(state, event)
        # Phase 4 — Validation (M1.6, runner only)
        report = validate(state)
        if _blocking(report):
            raise StateValidationError(report)
        candidate = CandidateCommit(
            log=snapshot.log + tuple(stamped),
            state=state,
            event_ids=snapshot.event_ids
            | frozenset(e.metadata.event_id for e in stamped),
            validation_report=report,
            events=tuple(stamped),
        )
        # Phase 5 — Commit (the single mutation point)
        committed = self._updater.commit(candidate)
        return AppendResult(
            success=True,
            version=committed.version,
            projection_version=PROJECTION_VERSION,
            first_seq=first_seq,
            last_seq=current_version(committed.log),
            appended=len(events),
            warnings=list(report.violations),
        )
