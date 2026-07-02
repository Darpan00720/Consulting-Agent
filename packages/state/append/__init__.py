"""Append pipeline (M1.7.3) — the Engagement State's only mutation path.

Built slice by slice per docs/implementation/M1.7.3-Decomposition.md:
S1 contracts (errors, result) — this file's current surface; later slices add
allocation, guarding, and orchestration. Internal package until the facade
exposes the event API (S5).
"""

from state.append.errors import (
    AppendError,
    AppendErrorCode,
    EventAdmissionError,
    VersionConflictError,
)
from state.append.result import AppendResult

__all__ = [
    "AppendError",
    "AppendErrorCode",
    "AppendResult",
    "EventAdmissionError",
    "VersionConflictError",
]
