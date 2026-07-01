"""Shared Pydantic base model for all StratAgent data models.

Per ADR-002, Pydantic models are the canonical source of truth for validation,
serialization, type safety, and JSON-Schema generation. Every domain model
inherits from :class:`StratAgentModel` so these conventions are enforced uniformly.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StratAgentModel(BaseModel):
    """Base model enforcing project-wide conventions.

    - ``extra="forbid"``: unknown fields are rejected (no silent data drift).
    - ``validate_assignment``: assignments are validated, not just construction.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )
