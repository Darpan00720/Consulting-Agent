"""In-memory pub/sub bus for live engagement events (SSE fan-out).

Events are also persisted in SQLite (`db.append_event`), so a subscriber that
connects late replays history from the DB and then tails the bus.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(
            list
        )
        self._lock = asyncio.Lock()

    async def subscribe(self, engagement_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._subscribers[engagement_id].append(queue)
        return queue

    async def unsubscribe(
        self, engagement_id: str, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        async with self._lock:
            with contextlib.suppress(ValueError):
                self._subscribers[engagement_id].remove(queue)

    async def publish(self, engagement_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers[engagement_id])
        for queue in queues:
            queue.put_nowait(event)


bus = EventBus()
