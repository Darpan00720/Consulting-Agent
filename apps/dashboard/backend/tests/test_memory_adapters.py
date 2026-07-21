"""Tests for the built-in memory adapters (ADR-013 W4, requirement 2/7/8/12).

CheckpointAdapter is exercised against the REAL ``app.db`` (SQLite) store —
save/restore/resume/snapshot/history are genuine reads/writes, not mocked.
GraphifyAdapter and AgentDBAdapter are exercised in their honest placeholder
mode AND with an injected fake ``client`` (the real-wiring seam). The plugin
tests prove — concretely — that a completely novel provider registers,
is discovered, and is queried through the unmodified Service/Registry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from app import config, db
from app.memory.adapters import (
    AgentDBAdapter,
    CheckpointAdapter,
    GraphifyAdapter,
    default_memory_registry,
)
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
from app.memory.provider import MemoryProvider
from app.memory.registry import MemoryRegistry
from app.memory.service import MemoryService


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch, tmp_path):
    """Isolated per-test DB — the ``db.reset_for_tests()`` convention already
    established in ``tests/test_api.py``: it only closes the module-level
    connection, it does NOT wipe the underlying file, so ``DB_PATH`` must be
    repointed to a fresh ``tmp_path`` file first or engagement ids can collide
    with data a PRIOR test run left on the shared default DB path."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "memory-test.db")
    db.reset_for_tests()
    yield


# ---- CheckpointAdapter — real (requirement 7) ------------------------------


def test_checkpoint_save_and_restore_real_db():
    adapter = CheckpointAdapter()
    adapter.save("eng-1", "classify", "classification output")
    adapter.save("eng-1", "planning", "planning output")
    restored = adapter.restore("eng-1")
    assert restored == {
        "classify": "classification output",
        "planning": "planning output",
    }


def test_checkpoint_resume_reflects_whether_work_exists():
    adapter = CheckpointAdapter()
    assert adapter.resume("fresh-engagement") is False
    adapter.save("fresh-engagement", "classify", "output")
    assert adapter.resume("fresh-engagement") is True


def test_checkpoint_snapshot_includes_phases_analysts_and_event_count():
    adapter = CheckpointAdapter()
    db.append_event("eng-2", "phase_completed", {"phase": "classify", "output": "x"})
    db.append_event(
        "eng-2", "analyst_completed", {"agent": "financial-analyst", "output": "y"}
    )
    snap = adapter.snapshot("eng-2")
    assert snap["phases"] == {"classify": "x"}
    assert snap["analysts"] == {"financial-analyst": "y"}
    assert snap["event_count"] == 2


def test_checkpoint_history_returns_raw_events():
    adapter = CheckpointAdapter()
    adapter.save("eng-3", "classify", "output")
    history = adapter.history("eng-3")
    assert len(history) == 1
    assert history[0]["type"] == "phase_completed"


def test_checkpoint_generic_store_maps_to_real_append_event():
    adapter = CheckpointAdapter()
    record = MemoryRecord(
        key="eng-4::classify",
        value="generic store output",
        memory_type=MemoryType.EXECUTION,
    )
    _run(adapter.store(record))
    assert adapter.restore("eng-4") == {"classify": "generic store output"}


def test_checkpoint_generic_retrieve_maps_to_real_restore():
    adapter = CheckpointAdapter()
    adapter.save("eng-5", "classify", "output")
    record = _run(adapter.retrieve("eng-5::classify"))
    assert record is not None
    assert record.value == "output"


def test_checkpoint_retrieve_missing_returns_none():
    adapter = CheckpointAdapter()
    assert _run(adapter.retrieve("eng-6::missing")) is None


def test_checkpoint_search_scoped_by_engagement_id():
    adapter = CheckpointAdapter()
    adapter.save("eng-7", "classify", "a")
    adapter.save("eng-7", "planning", "b")
    records = _run(
        adapter.search(
            MemoryQuery(
                memory_type=MemoryType.EXECUTION,
                metadata_filter={"engagement_id": "eng-7"},
            )
        )
    )
    assert {r.value for r in records} == {"a", "b"}


def test_checkpoint_search_without_engagement_id_filter_is_empty():
    adapter = CheckpointAdapter()
    assert _run(adapter.search(MemoryQuery(text="x"))) == ()


def test_checkpoint_exists():
    adapter = CheckpointAdapter()
    adapter.save("eng-8", "classify", "output")
    assert _run(adapter.exists("eng-8::classify")) is True
    assert _run(adapter.exists("eng-8::ghost")) is False


def test_checkpoint_is_append_only_update_rejected():
    adapter = CheckpointAdapter()
    try:
        _run(adapter.update("eng-9::classify", "new value"))
        raise AssertionError("expected UnsupportedOperation")
    except UnsupportedOperation:
        pass


def test_checkpoint_is_append_only_delete_rejected():
    adapter = CheckpointAdapter()
    try:
        _run(adapter.delete("eng-9::classify"))
        raise AssertionError("expected UnsupportedOperation")
    except UnsupportedOperation:
        pass


def test_checkpoint_health_probes_the_real_db():
    adapter = CheckpointAdapter()
    result = _run(adapter.health())
    assert result.state is MemoryHealthState.HEALTHY


def test_checkpoint_disabled_reports_unavailable_without_probing():
    adapter = CheckpointAdapter(is_available=False)
    result = _run(adapter.health())
    assert result.state is MemoryHealthState.UNAVAILABLE


# ---- GraphifyAdapter (requirement 8) ---------------------------------------


def test_graphify_never_becomes_a_dispatch_target_or_agent():
    """F4, carried into W4: Graphify has no describe()/can_handle() —
    it cannot satisfy the workflow Target or Agent protocols."""
    adapter = GraphifyAdapter()
    assert not hasattr(adapter, "describe")
    assert not hasattr(adapter, "can_handle")


def test_graphify_is_read_only():
    adapter = GraphifyAdapter()
    assert adapter.metadata().read_only is True


def test_graphify_write_operations_are_unsupported():
    adapter = GraphifyAdapter()
    for op in (
        adapter.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.REPOSITORY)
        ),
        adapter.update("k", "v"),
        adapter.delete("k"),
    ):
        try:
            _run(op)
            raise AssertionError("expected UnsupportedOperation")
        except UnsupportedOperation:
            pass


def test_graphify_placeholder_search_returns_graphify_content():
    adapter = GraphifyAdapter()
    records = _run(adapter.search(MemoryQuery(text="dependency graph")))
    assert len(records) == 1
    assert "graphify" in str(records[0].value).lower()


def test_graphify_client_injection_is_the_real_wiring_seam():
    @dataclass
    class FakeGraphifyClient:
        pinged: bool = False

        async def retrieve(self, key):
            return MemoryRecord(
                key=key, value="real graph node", memory_type=MemoryType.REPOSITORY
            )

        async def search(self, query):
            return (
                MemoryRecord(
                    key="n1",
                    value="real search result",
                    memory_type=MemoryType.REPOSITORY,
                ),
            )

        async def store(self, record):
            pass

        async def exists(self, key):
            return True

        async def ping(self):
            self.pinged = True
            return True

    client = FakeGraphifyClient()
    adapter = GraphifyAdapter(client=client)
    result = _run(adapter.retrieve("n1"))
    assert result.value == "real graph node"
    health = _run(adapter.health())
    assert health.state is MemoryHealthState.HEALTHY
    assert client.pinged is True


def test_graphify_health_reports_placeholder_mode_honestly():
    adapter = GraphifyAdapter()  # no client injected
    result = _run(adapter.health())
    assert "placeholder" in result.detail.lower()


# ---- AgentDBAdapter (requirement 2) ----------------------------------------


def test_agentdb_supports_writes_unlike_graphify():
    adapter = AgentDBAdapter()
    record = MemoryRecord(key="k1", value="v1", memory_type=MemoryType.EXECUTION)
    _run(adapter.store(record))
    got = _run(adapter.retrieve("k1"))
    assert got.value == "v1"


def test_agentdb_search_filters_by_type_and_text():
    adapter = AgentDBAdapter()
    _run(
        adapter.store(
            MemoryRecord(key="a", value="apple pie", memory_type=MemoryType.EXECUTION)
        )
    )
    _run(
        adapter.store(
            MemoryRecord(
                key="b", value="banana bread", memory_type=MemoryType.KNOWLEDGE
            )
        )
    )
    results = _run(
        adapter.search(MemoryQuery(text="apple", memory_type=MemoryType.EXECUTION))
    )
    assert len(results) == 1
    assert results[0].key == "a"


def test_agentdb_update_and_delete():
    adapter = AgentDBAdapter()
    _run(
        adapter.store(
            MemoryRecord(key="k", value="v1", memory_type=MemoryType.EXECUTION)
        )
    )
    _run(adapter.update("k", "v2"))
    assert _run(adapter.retrieve("k")).value == "v2"
    _run(adapter.delete("k"))
    assert _run(adapter.retrieve("k")) is None


def test_agentdb_exists():
    adapter = AgentDBAdapter()
    assert _run(adapter.exists("ghost")) is False
    _run(
        adapter.store(
            MemoryRecord(key="k", value="v", memory_type=MemoryType.EXECUTION)
        )
    )
    assert _run(adapter.exists("k")) is True


def test_agentdb_client_injection():
    @dataclass
    class FakeAgentDBClient:
        async def retrieve(self, key):
            return MemoryRecord(
                key=key, value="real agentdb value", memory_type=MemoryType.EXECUTION
            )

        async def search(self, query):
            return ()

        async def store(self, record):
            pass

        async def exists(self, key):
            return True

        async def ping(self):
            return True

    adapter = AgentDBAdapter(client=FakeAgentDBClient())
    result = _run(adapter.retrieve("k"))
    assert result.value == "real agentdb value"


# ---- Metadata validation (requirement 14) ----------------------------------


def test_every_builtin_adapter_has_valid_metadata():
    for adapter in (CheckpointAdapter(), GraphifyAdapter(), AgentDBAdapter()):
        meta = adapter.metadata()
        assert isinstance(meta, ProviderMetadata)
        assert meta.version
        assert meta.author
        assert meta.backing_system
        assert len(meta.supported_types) > 0
        assert len(meta.supported_strategies) > 0


def test_default_memory_registry_seeds_all_three_with_checkpoint_as_default():
    reg = default_memory_registry()
    assert {p.id for p in reg.discover()} == {"checkpoint", "graphify", "agentdb"}
    assert reg.default_provider().id == "checkpoint"


# ---- Plugin registration / dynamic discovery (requirement 12) -------------
#
# A completely NOVEL provider — modeling a future backend (Pinecone, Weaviate,
# Chroma, Neo4j, Redis, Postgres, ...) — registers, is discovered, and is
# queried through the UNMODIFIED Service/Registry. Concrete proof, not a claim.


@dataclass
class PluginMemoryProvider:
    """A stand-in for a hypothetical future vector/graph/kv store this
    package has never seen."""

    id: str = "future-vector-store"
    name: str = "Future Vector Store"
    version: str = "0.1.0"
    calls: list = field(default_factory=list)

    def supported_types(self):
        return (MemoryType.KNOWLEDGE, MemoryType.RESEARCH)

    def supported_strategies(self):
        return (RetrievalStrategy.SEMANTIC,)

    async def store(self, record):
        self.calls.append(("store", record))

    async def retrieve(self, key, memory_type=None):
        return None

    async def search(self, query):
        self.calls.append(("search", query))
        return (
            MemoryRecord(
                key="plugin-result",
                value="plugin handled it",
                memory_type=MemoryType.KNOWLEDGE,
            ),
        )

    async def update(self, key, value, *, memory_type=None):
        pass

    async def delete(self, key, *, memory_type=None):
        pass

    async def exists(self, key, *, memory_type=None):
        return False

    async def health(self) -> MemoryHealthResult:
        return MemoryHealthResult(MemoryHealthState.HEALTHY)

    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            version=self.version,
            author="third-party",
            supported_types=self.supported_types(),
            supported_strategies=self.supported_strategies(),
            backing_system="future-vector-store",
        )


def test_plugin_provider_satisfies_the_protocol_without_subclassing_anything():
    assert isinstance(PluginMemoryProvider(), MemoryProvider)


def test_plugin_provider_registers_into_the_production_registry():
    reg = default_memory_registry()  # the real, built-in-seeded registry
    reg.register(PluginMemoryProvider())
    assert reg.get("future-vector-store") is not None
    assert {p.id for p in reg.discover()} == {
        "checkpoint",
        "graphify",
        "agentdb",
        "future-vector-store",
    }


def test_plugin_provider_is_dynamically_discoverable_by_type():
    reg = MemoryRegistry()
    reg.register(PluginMemoryProvider())
    found = reg.find_by_type(MemoryType.RESEARCH)
    assert [p.id for p in found] == ["future-vector-store"]


def test_plugin_provider_queried_through_the_unmodified_service():
    plugin = PluginMemoryProvider()
    reg = MemoryRegistry()
    reg.register(plugin)
    service = MemoryService(reg)  # the SAME MemoryService class every builtin uses
    result = _run(
        service.search(
            MemoryQuery(
                text="find x",
                memory_type=MemoryType.RESEARCH,
                strategy=RetrievalStrategy.SEMANTIC,
            ),
            trace_id="t",
        )
    )
    assert result.success is True
    assert result.records[0].value == "plugin handled it"
    assert result.provider_used == "future-vector-store"
