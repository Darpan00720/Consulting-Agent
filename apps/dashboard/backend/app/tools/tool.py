"""The Tool abstraction (requirement 1).

Every external capability (MCP, CLI, REST API, local process, knowledge sync)
implements this Protocol. Structural typing (like ``Target``/``Agent``/
``MemoryProvider`` in ADR-013 §4a/W3/W4) — no ABC, no required inheritance, so
a future tool (CrewAI, Gemini CLI, Kimi CLI, OpenAI Responses, Neo4j, Pinecone,
Weaviate, ...) can satisfy it without importing anything from this package
(requirement 9's forward compatibility).

No adapter-specific logic lives in ``ToolRuntime`` or ``ToolRegistry`` beyond
this interface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.tools.models import (
    ToolHealthResult,
    ToolMetadata,
    ToolRequest,
    ToolResponse,
    ToolType,
)


@runtime_checkable
class Tool(Protocol):
    """The minimum contract every tool adapter satisfies (requirement 1)."""

    id: str
    name: str
    version: str
    description: str
    capabilities: tuple[str, ...]
    type: ToolType

    async def execute(self, request: ToolRequest) -> ToolResponse: ...
    async def health(self) -> ToolHealthResult: ...
    def metadata(self) -> ToolMetadata: ...
