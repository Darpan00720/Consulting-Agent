"""Built-in memory provider adapters (requirement 2).

**CheckpointAdapter is REAL** — it wraps ``app.db.append_event``/``list_events``
(the event-sourced store ``app/pipeline/engine.py`` already uses for
resume-after-rate-limit), unmodified. This backend process genuinely owns that
SQLite store, so the adapter makes real calls, not a placeholder.

**GraphifyAdapter and AgentDBAdapter are honest placeholders behind an
injectable ``client``** — Graphify and AgentDB are real systems, but reachable
today only as MCP tool surfaces external to this Python process (verified:
no importable Graphify/AgentDB Python library exists in this repo). Having
generic memory-access code silently call out to an external MCP session as a
side effect of a memory lookup is a live-integration decision beyond "build
the platform," so both ship deterministic, side-effect-free default bodies —
the exact same pattern already established for Codex/Consulting in
``app.agents.builtin`` (W2/W3). Real wiring plugs into ``client`` later
without touching ``MemoryService`` or the registry.

Per requirement: none of these reimplement or modify their backing system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.memory.errors import UnsupportedOperation
from app.memory.models import (
    MemoryHealthResult,
    MemoryHealthState,
    MemoryQuery,
    MemoryRecord,
    MemoryType,
    ProviderMetadata,
    RetrievalStrategy,
)
from app.memory.registry import MemoryRegistry

_T = MemoryType
_S = RetrievalStrategy


class ExternalMemoryClient(Protocol):
    """What a REAL Graphify/AgentDB client would implement — the injection
    point ``client=`` plugs into. Not implemented here (requirement 12: ensure
    compatibility, don't build the integration)."""

    async def retrieve(self, key: str) -> MemoryRecord | None: ...
    async def search(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]: ...
    async def store(self, record: MemoryRecord) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def ping(self) -> bool: ...


# ---- CheckpointAdapter — real, wraps app.db (requirement 7) ---------------


@dataclass
class CheckpointAdapter:
    """Wraps the existing event-sourced checkpoint store (``app.db``). Keys
    are ``"{engagement_id}::{phase_or_agent_name}"``. Read/write of individual
    phase outputs maps onto the generic ``MemoryProvider`` contract; the
    domain-specific save/restore/resume/snapshot/history vocabulary
    (requirement 7) lives here as additional methods, since it's specific to
    this one provider's backing shape (event log), not generic across memory
    providers — the same "backend-specific logic stays in the adapter"
    discipline requirement 1 states for the generic interface.
    """

    id: str = "checkpoint"
    name: str = "Checkpoint Store"
    version: str = "1.0.0"
    is_available: bool = True

    def supported_types(self) -> tuple[MemoryType, ...]:
        return (_T.EXECUTION, _T.SESSION, _T.CONVERSATION)

    def supported_strategies(self) -> tuple[RetrievalStrategy, ...]:
        return (_S.EXACT, _S.METADATA)

    async def health(self) -> MemoryHealthResult:
        if not self.is_available:
            return MemoryHealthResult(MemoryHealthState.UNAVAILABLE, detail="disabled")
        try:
            from app import db

            db.connect()  # a cheap real reachability probe
            return MemoryHealthResult(MemoryHealthState.HEALTHY)
        except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE, not a crash
            return MemoryHealthResult(
                MemoryHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
            )

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            version=self.version,
            author="StratAgent",
            supported_types=self.supported_types(),
            supported_strategies=self.supported_strategies(),
            backing_system="sqlite-events",
            read_only=False,
        )

    @staticmethod
    def _split_key(key: str) -> tuple[str, str]:
        engagement_id, _, name = key.partition("::")
        return engagement_id, name

    async def store(self, record: MemoryRecord) -> None:
        from app import db

        engagement_id, name = self._split_key(record.key)
        event_type = record.metadata.get("event_type", "phase_completed")
        payload_key = "phase" if event_type == "phase_completed" else "agent"
        db.append_event(
            engagement_id, event_type, {payload_key: name, "output": record.value}
        )

    async def retrieve(
        self, key: str, memory_type: MemoryType | None = None
    ) -> MemoryRecord | None:
        engagement_id, name = self._split_key(key)
        outputs = self.restore(engagement_id)
        if name not in outputs:
            return None
        return MemoryRecord(
            key=key,
            value=outputs[name],
            memory_type=memory_type or _T.EXECUTION,
            metadata={"engagement_id": engagement_id},
        )

    async def search(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        engagement_id = query.metadata_filter.get("engagement_id")
        if not engagement_id:
            return ()
        outputs = self.restore(engagement_id)
        records = tuple(
            MemoryRecord(
                key=f"{engagement_id}::{name}",
                value=output,
                memory_type=query.memory_type or _T.EXECUTION,
                metadata={"engagement_id": engagement_id},
            )
            for name, output in outputs.items()
        )
        return records[: query.limit]

    async def update(
        self, key: str, value: Any, *, memory_type: MemoryType | None = None
    ) -> None:
        # Event-sourced and append-only BY DESIGN — mutating a past checkpoint
        # would break the resume guarantee (`_completed_phase_outputs` trusts
        # the FIRST/only completion event). A caller wanting a new value
        # appends a new completion event via `store`, never edits history.
        raise UnsupportedOperation(
            "checkpoint history is append-only; store() a new completion instead"
        )

    async def delete(self, key: str, *, memory_type: MemoryType | None = None) -> None:
        raise UnsupportedOperation(
            "checkpoint history is append-only; deletion unsupported"
        )

    async def exists(self, key: str, *, memory_type: MemoryType | None = None) -> bool:
        engagement_id, name = self._split_key(key)
        return name in self.restore(engagement_id)

    # ---- checkpoint-domain vocabulary (requirement 7) --------------------

    def save(self, engagement_id: str, phase: str, output: str) -> None:
        """Persist a phase's completion — the real write path engine.py uses."""
        from app import db

        db.append_event(
            engagement_id, "phase_completed", {"phase": phase, "output": output}
        )

    def restore(self, engagement_id: str) -> dict[str, str]:
        """Reconstruct completed phase outputs — same logic as
        ``engine._completed_phase_outputs`` (that function is private to
        engine.py; this is the Memory Platform's own real read of the same
        public ``db.list_events`` events, not a call into engine internals)."""
        from app import db

        out: dict[str, str] = {}
        for event in db.list_events(engagement_id):
            if event["type"] == "phase_completed":
                payload = event["payload"]
                if "output" in payload:
                    out[payload["phase"]] = payload["output"]
        return out

    def resume(self, engagement_id: str) -> bool:
        """Whether this engagement has any checkpointed work to resume from."""
        return bool(self.restore(engagement_id))

    def snapshot(self, engagement_id: str) -> dict[str, Any]:
        """A full point-in-time reconstruction: phases, analysts, event count."""
        from app import db

        events = db.list_events(engagement_id)
        analysts: dict[str, str] = {}
        for event in events:
            if event["type"] == "analyst_completed":
                payload = event["payload"]
                if payload.get("output") is not None:
                    analysts[payload["agent"]] = payload["output"]
        return {
            "phases": self.restore(engagement_id),
            "analysts": analysts,
            "event_count": len(events),
        }

    def history(self, engagement_id: str) -> list[dict[str, Any]]:
        """Raw event history — the full audit trail behind every checkpoint."""
        from app import db

        return db.list_events(engagement_id)


# ---- GraphifyAdapter — placeholder + injectable client (requirement 8) ----


@dataclass
class GraphifyAdapter:
    """Graphify remains an EXTERNAL provider — never an agent, never a
    dispatch target (F4, carried into W4). Read-only structural graph data:
    ``store``/``update``/``delete`` are unsupported by design, not omission."""

    id: str = "graphify"
    name: str = "Graphify"
    version: str = "1.0.0"
    is_available: bool = True
    client: ExternalMemoryClient | None = None

    def supported_types(self) -> tuple[MemoryType, ...]:
        return (_T.REPOSITORY, _T.KNOWLEDGE)

    def supported_strategies(self) -> tuple[RetrievalStrategy, ...]:
        return (_S.PROVIDER_NATIVE, _S.EXACT, _S.METADATA)

    async def health(self) -> MemoryHealthResult:
        if self.client is not None:
            try:
                ok = await self.client.ping()
                return MemoryHealthResult(
                    MemoryHealthState.HEALTHY if ok else MemoryHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return MemoryHealthResult(
                    MemoryHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return MemoryHealthResult(
            MemoryHealthState.HEALTHY
            if self.is_available
            else MemoryHealthState.UNAVAILABLE,
            detail="placeholder client — no real Graphify MCP wiring injected",
        )

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            version=self.version,
            author="Graphify (external MCP)",
            supported_types=self.supported_types(),
            supported_strategies=self.supported_strategies(),
            backing_system="graphify",
            read_only=True,
        )

    async def store(self, record: MemoryRecord) -> None:
        raise UnsupportedOperation("Graphify is a read-only structural graph provider")

    async def update(
        self, key: str, value: Any, *, memory_type: MemoryType | None = None
    ) -> None:
        raise UnsupportedOperation("Graphify is a read-only structural graph provider")

    async def delete(self, key: str, *, memory_type: MemoryType | None = None) -> None:
        raise UnsupportedOperation("Graphify is a read-only structural graph provider")

    async def retrieve(
        self, key: str, memory_type: MemoryType | None = None
    ) -> MemoryRecord | None:
        if self.client is not None:
            return await self.client.retrieve(key)
        return MemoryRecord(
            key=key,
            value=f"[graphify placeholder] node info for {key!r}",
            memory_type=memory_type or _T.REPOSITORY,
            metadata={"source": "graphify"},
        )

    async def search(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        if self.client is not None:
            return await self.client.search(query)
        record = MemoryRecord(
            key=f"graphify:{query.text}",
            value=f"[graphify placeholder] query_graph result for {query.text!r}",
            memory_type=query.memory_type or _T.REPOSITORY,
            metadata={"source": "graphify"},
        )
        return (record,)

    async def exists(self, key: str, *, memory_type: MemoryType | None = None) -> bool:
        if self.client is not None:
            return await self.client.exists(key)
        return True  # placeholder: assume the graph can answer any query


# ---- AgentDBAdapter — placeholder + injectable client (requirement 2) -----


@dataclass
class AgentDBAdapter:
    """AgentDB (the Claude Flow ``agentdb_*`` MCP surface) — same honest
    placeholder-with-injectable-client boundary as Graphify (module
    docstring). Unlike Graphify, AgentDB genuinely supports writes, so
    ``store``/``update``/``delete`` are implemented (placeholder bodies), not
    rejected."""

    id: str = "agentdb"
    name: str = "AgentDB"
    version: str = "1.0.0"
    is_available: bool = True
    client: ExternalMemoryClient | None = None
    _store: dict[str, MemoryRecord] = field(
        default_factory=dict
    )  # placeholder-mode only

    def supported_types(self) -> tuple[MemoryType, ...]:
        return (_T.EXECUTION, _T.KNOWLEDGE, _T.CONVERSATION, _T.CACHE)

    def supported_strategies(self) -> tuple[RetrievalStrategy, ...]:
        return (_S.SEMANTIC, _S.HYBRID, _S.EXACT, _S.METADATA, _S.PROVIDER_NATIVE)

    async def health(self) -> MemoryHealthResult:
        if self.client is not None:
            try:
                ok = await self.client.ping()
                return MemoryHealthResult(
                    MemoryHealthState.HEALTHY if ok else MemoryHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return MemoryHealthResult(
                    MemoryHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return MemoryHealthResult(
            MemoryHealthState.HEALTHY
            if self.is_available
            else MemoryHealthState.UNAVAILABLE,
            detail="placeholder client — no real AgentDB MCP wiring injected",
        )

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            version=self.version,
            author="Claude Flow (external MCP)",
            supported_types=self.supported_types(),
            supported_strategies=self.supported_strategies(),
            backing_system="agentdb",
            read_only=False,
        )

    async def store(self, record: MemoryRecord) -> None:
        if self.client is not None:
            await self.client.store(record)
            return
        self._store[record.key] = record  # placeholder: in-memory only

    async def retrieve(
        self, key: str, memory_type: MemoryType | None = None
    ) -> MemoryRecord | None:
        if self.client is not None:
            return await self.client.retrieve(key)
        return self._store.get(key)

    async def search(self, query: MemoryQuery) -> tuple[MemoryRecord, ...]:
        if self.client is not None:
            return await self.client.search(query)
        matches = [
            r
            for r in self._store.values()
            if (query.memory_type is None or r.memory_type == query.memory_type)
            and (not query.text or query.text.lower() in str(r.value).lower())
        ]
        return tuple(matches[: query.limit])

    async def update(
        self, key: str, value: Any, *, memory_type: MemoryType | None = None
    ) -> None:
        if self.client is not None:
            await self.client.store(
                MemoryRecord(
                    key=key, value=value, memory_type=memory_type or _T.EXECUTION
                )
            )
            return
        existing = self._store.get(key)
        self._store[key] = MemoryRecord(
            key=key,
            value=value,
            memory_type=memory_type
            or (existing.memory_type if existing else _T.EXECUTION),
        )

    async def delete(self, key: str, *, memory_type: MemoryType | None = None) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str, *, memory_type: MemoryType | None = None) -> bool:
        if self.client is not None:
            return await self.client.exists(key)
        return key in self._store


def default_memory_registry() -> MemoryRegistry:
    """The production registry: Checkpoint (real, highest priority, default),
    then Graphify, then AgentDB — mirrors ``builtin.default_agent_registry()``
    (W3)."""
    registry = MemoryRegistry()
    registry.register(CheckpointAdapter(), priority=10, default=True)
    registry.register(GraphifyAdapter(), priority=20)
    registry.register(AgentDBAdapter(), priority=30)
    return registry
