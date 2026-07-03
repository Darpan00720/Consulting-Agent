"""Append error contracts (M1.7.3-S1, design §3).

Every append failure carries a stable, machine-readable ``error_code`` for
programmatic handling — messages stay human-readable and are never a contract.
Codes are a frozen namespace (the validation rule-id discipline): once
introduced, a code is never reused or renamed.
"""

from __future__ import annotations

from enum import StrEnum

from common.errors import StratAgentError


class AppendErrorCode(StrEnum):
    """Stable machine-readable codes for append failures.

    The namespace grows (e.g. replay integrity arrives with M1.7.4) but
    existing values are frozen.
    """

    VERSION_CONFLICT = "version_conflict"
    EVENT_ADMISSION = "event_admission"
    APPEND_UNSUPPORTED = "append_unsupported"


class AppendError(StratAgentError):
    """Base for all append failures; always carries an ``error_code``."""

    def __init__(self, message: str, *, error_code: AppendErrorCode) -> None:
        self.error_code = error_code
        super().__init__(message)


class VersionConflictError(AppendError):
    """The writer's ``expected_version`` does not match the committed version.

    Raised for stale writers (``expected < actual``) and for writers claiming a
    version that has never existed (``expected > actual``) alike.
    """

    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"version conflict: expected {expected}, actual {actual}",
            error_code=AppendErrorCode.VERSION_CONFLICT,
        )


class EventAdmissionError(AppendError):
    """An event failed admission checks (before any sequence allocation)."""

    def __init__(self, reason: str, *, event_id: str | None = None) -> None:
        self.reason = reason
        self.event_id = event_id
        suffix = f" (event {event_id!r})" if event_id is not None else ""
        super().__init__(
            f"event not admitted: {reason}{suffix}",
            error_code=AppendErrorCode.EVENT_ADMISSION,
        )


class AppendUnsupportedError(AppendError):
    """This engagement does not currently support appends (no event log).

    Raised by read-only adoptions (``from_state``/``from_json``): the
    candidates may be flawless — the engagement lacks the capability. This
    restriction is temporary: M1.8 introduces persisted event logs and M1.9
    replay-backed engagements remove the limitation.
    """

    def __init__(self) -> None:
        super().__init__(
            "append requires an event log: engagements adopted via "
            "from_state()/from_json() are read-only until persisted logs "
            "(M1.8) and replay (M1.9) exist",
            error_code=AppendErrorCode.APPEND_UNSUPPORTED,
        )
