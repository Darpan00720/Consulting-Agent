"""Base class for identifiable, auditable domain objects."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from common.values import Identifier, new_id
from core.base import StratAgentModel


class DomainObject(StratAgentModel):
    """Base for every major domain object.

    Provides an immutable, auto-generated ``id`` — the primary reference target for
    events, replay, and APIs, so references never rely on list ordering — plus
    optional audit metadata. Domain models inherit this so ids and audit fields are
    defined once rather than duplicated.
    """

    id: Identifier = Field(default_factory=new_id, frozen=True)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
