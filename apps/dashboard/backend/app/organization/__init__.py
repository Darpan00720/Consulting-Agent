"""Organization Layer — the typed role/RACI/allocation model (25 roles),
approved for integration into ``app.pipeline`` under ADR-014 Phase 2.

The re-exports below are exactly the symbols ADR-014 §7.2 names as the
sanctioned integration surface — a future ``app.pipeline`` adapter should
need nothing beyond this package-level import to turn its existing
free-text staffing suggestions into typed role assignments. Calling
``app.organization.governance``/``review`` (W9's own approval workflow) is
explicitly out of scope for this integration per ADR-014 §7.2, and reaching
into a submodule or a private symbol is prohibited by ADR-014 §7.4.
"""

from __future__ import annotations

from app.organization.allocation import allocate_team
from app.organization.registry import (
    OrganizationRegistry,
    default_organization_registry,
)

__all__ = [
    "OrganizationRegistry",
    "default_organization_registry",
    "allocate_team",
]
