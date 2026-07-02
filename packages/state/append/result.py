"""AppendResult — the result contract of the append API (M1.7.3-S1, design §3).

Part of the public append contract once the facade exposes it (S5): frozen,
JSON-serializable both ways, and self-describing — ``projection_version``
records which projection semantics produced the resulting state, so callers
never need to consult global constants.
"""

from __future__ import annotations

from pydantic import ConfigDict

from core.base import StratAgentModel
from state.validation import Violation


class AppendResult(StratAgentModel):
    """Outcome of a committed append."""

    model_config = ConfigDict(frozen=True)

    success: bool
    version: int
    projection_version: int
    first_seq: int
    last_seq: int
    appended: int
    warnings: list[Violation] = []
