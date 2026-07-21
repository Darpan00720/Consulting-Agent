"""The MemoryProvider abstraction (requirement 1).

Every memory backend implements this Protocol. Structural typing (like
``Target``/``Agent`` in ADR-013 §4a/W3) — no ABC, no required inheritance, so
a future provider (Pinecone, Weaviate, Chroma, Neo4j, Redis, Postgres, ...)
can satisfy it without importing anything from this package (requirement 12's
forward compatibility).

No backend-specific logic lives in ``MemoryService`` or ``MemoryRegistry``
beyond this interface — every method here is exactly what those two need,
nothing more. Each concrete adapter (``adapters.py``) is where a backend's
real shape (Graphify's graph queries, AgentDB's vector/graph store, SQLite
event rows) gets translated into this uniform contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.memory.models import (
    MemoryHealthResult,
    MemoryQuery,
    MemoryRecord,
    MemoryType,
    ProviderMetadata,
    RetrievalStrategy,
)


@runtime_checkable
class MemoryProvider(Protocol):
    """The minimum contract every memory backend satisfies (requirement 1)."""

    id: str
    name: str
    version: str

    def supported_types(self) -> tuple[MemoryType, ...]: ...
    def supported_strategies(self) -> tuple[RetrievalStrategy, ...]: ...

    async def store(self, record: MemoryRecord) -> None: ...
    async def retrieve(
        self, key: str, memory_type: MemoryType | None = None
    ) -> MemoryRecord | None: ...
    async def search(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]: ...
    async def update(
        self, key: str, value: Any, *, memory_type: MemoryType | None = None
    ) -> None: ...
    async def delete(
        self, key: str, *, memory_type: MemoryType | None = None
    ) -> None: ...
    async def exists(
        self, key: str, *, memory_type: MemoryType | None = None
    ) -> bool: ...
    async def health(self) -> MemoryHealthResult: ...
    def metadata(self) -> ProviderMetadata: ...
