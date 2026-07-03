"""Append pipeline (M1.7.3) — the Engagement State's only mutation path.

Built slice by slice per docs/implementation/M1.7.3-Decomposition.md:
S1 contracts (errors, result); S2 arithmetic (sequence stamping, version
derivation); S3 decisions (concurrency guard); S4 orchestration (commit point
+ pipeline). Internal package until the facade exposes the event API (S5).
"""

from state.append.commit import (
    CandidateCommit,
    Committed,
    StateUpdater,
    make_committed,
)
from state.append.errors import (
    AppendError,
    AppendErrorCode,
    AppendUnsupportedError,
    EventAdmissionError,
    VersionConflictError,
)
from state.append.guard import GuardDecision, check_append
from state.append.pipeline import AppendPipeline
from state.append.result import AppendResult
from state.append.sequencing import stamp
from state.append.versioning import (
    current_sequence,
    current_version,
    next_state_version,
)

__all__ = [
    "AppendError",
    "AppendErrorCode",
    "AppendPipeline",
    "AppendResult",
    "AppendUnsupportedError",
    "CandidateCommit",
    "Committed",
    "EventAdmissionError",
    "GuardDecision",
    "StateUpdater",
    "VersionConflictError",
    "check_append",
    "current_sequence",
    "current_version",
    "make_committed",
    "next_state_version",
    "stamp",
]
