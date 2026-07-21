"""Collaboration model (requester's "Collaboration Model" section) — the
ONLY channel through which one role reaches another. ``CollaborationLog``
holds immutable ``CollaborationRequest`` records; responding replaces a
record with a new one (via ``dataclasses.replace``), it never mutates
another role's actual deliverable. That is the concrete enforcement of "no
role should directly modify another role's work": there is no API here that
lets one role edit an ``EngagementState`` field another role owns — only
request/respond records, all traceable by id, from-role, to-role, and
timestamp.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field

from app.organization.errors import UnknownRequestError
from app.organization.models import (
    CollaborationRequest,
    RequestKind,
    RequestStatus,
    new_request_id,
)


@dataclass
class CollaborationLog:
    _requests: dict[str, CollaborationRequest] = field(default_factory=dict)

    def create_request(
        self,
        kind: RequestKind,
        from_role: str,
        to_role: str,
        subject: str,
        content: str,
    ) -> CollaborationRequest:
        request = CollaborationRequest(
            id=new_request_id(),
            kind=kind,
            from_role=from_role,
            to_role=to_role,
            subject=subject,
            content=content,
        )
        self._requests[request.id] = request
        return request

    def respond(
        self, request_id: str, response: str, *, close: bool = True
    ) -> CollaborationRequest:
        if request_id not in self._requests:
            raise UnknownRequestError(f"no collaboration request {request_id!r}")
        current = self._requests[request_id]
        updated = dataclasses.replace(
            current,
            response=response,
            status=RequestStatus.CLOSED if close else RequestStatus.RESPONDED,
            responded_at=time.time(),
        )
        self._requests[request_id] = updated
        return updated

    def get(self, request_id: str) -> CollaborationRequest:
        if request_id not in self._requests:
            raise UnknownRequestError(f"no collaboration request {request_id!r}")
        return self._requests[request_id]

    def requests_for_role(self, role_id: str) -> tuple[CollaborationRequest, ...]:
        """Requests ADDRESSED TO this role — its inbox."""
        return tuple(r for r in self._requests.values() if r.to_role == role_id)

    def requests_from_role(self, role_id: str) -> tuple[CollaborationRequest, ...]:
        """Requests this role SENT — its outbox."""
        return tuple(r for r in self._requests.values() if r.from_role == role_id)

    def open_requests(self) -> tuple[CollaborationRequest, ...]:
        return tuple(
            r for r in self._requests.values() if r.status is RequestStatus.OPEN
        )

    def all_requests(self) -> tuple[CollaborationRequest, ...]:
        return tuple(self._requests.values())
