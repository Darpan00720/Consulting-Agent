"""Reusable value objects and identifier helpers (shared across capabilities).

Centralizes validation that would otherwise be duplicated across models:
- ``ConfidenceScore`` — a float constrained to [0, 1].
- ``Identifier`` / ``Reference`` — semantic aliases for an object's own id and for
  a reference to another object's id (referential integrity is enforced later, M1.6).
- ``new_id`` — factory for immutable, order-independent identifiers.
"""

from __future__ import annotations

import uuid
from typing import Annotated, TypeAlias

from pydantic import Field

# PEP 695 `type` aliases (UP040) are deferred (BACKLOG TD-012): converting
# ConfidenceScore to a lazy `type` alias risks pydantic's resolution of the
# Annotated Field constraint, and this milestone (M1.7.8) makes no runtime
# behaviour change. Revisit when adopting PEP 695 syntax repo-wide.
Identifier: TypeAlias = str  # noqa: UP040
Reference: TypeAlias = str  # noqa: UP040
ConfidenceScore: TypeAlias = Annotated[float, Field(ge=0.0, le=1.0)]  # noqa: UP040


def new_id() -> str:
    """Generate a unique, immutable identifier (not derived from ordering)."""
    return uuid.uuid4().hex
