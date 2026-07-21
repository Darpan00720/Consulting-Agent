"""Tests for the built-in tool adapters (ADR-013 W5, requirement 4/9).

Graphify, AgentDB, GitHub, Codex CLI, Claude Code CLI, and Local Shell
adapters — placeholder mode, client/runner injection, metadata validation —
plus the plugin registration / dynamic discovery proof.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.tools.adapters import (
    AgentDBToolAdapter,
    ClaudeCodeAdapter,
    CodexCLIAdapter,
    GitHubAdapter,
    GraphifyToolAdapter,
    LocalShellAdapter,
    default_tool_registry,
)
from app.tools.models import (
    OperationClass,
    ToolHealthResult,
    ToolHealthState,
    ToolMetadata,
    ToolRequest,
    ToolResponse,
    ToolType,
)
from app.tools.registry import ToolRegistry
from app.tools.runtime import ToolRuntime
from app.tools.tool import Tool


def _run(coro):
    return asyncio.run(coro)


# ---- Graphify -----------------------------------------------------------


def test_graphify_placeholder_execute():
    adapter = GraphifyToolAdapter()
    result = _run(
        adapter.execute(ToolRequest(operation="query_graph", parameters={"q": "x"}))
    )
    assert result.success is True
    assert "graphify" in str(result.output).lower()


def test_graphify_unsupported_operation():
    adapter = GraphifyToolAdapter()
    result = _run(adapter.execute(ToolRequest(operation="ghost_op")))
    assert result.success is False


def test_graphify_all_operations_are_read_only():
    adapter = GraphifyToolAdapter()
    meta = adapter.metadata()
    assert all(v.value == "read-only" for v in meta.operation_classes.values())


def test_graphify_never_becomes_an_agent_or_dispatch_target():
    """F4, carried into W5: no describe()/can_handle()."""
    adapter = GraphifyToolAdapter()
    assert not hasattr(adapter, "describe")
    assert not hasattr(adapter, "can_handle")


def test_graphify_client_injection():
    @dataclass
    class FakeClient:
        pinged: bool = False

        async def invoke(self, operation, parameters):
            return ToolResponse(success=True, output="real graph data")

        async def ping(self):
            self.pinged = True
            return True

    client = FakeClient()
    adapter = GraphifyToolAdapter(client=client)
    result = _run(adapter.execute(ToolRequest(operation="query_graph")))
    assert result.output == "real graph data"
    health = _run(adapter.health())
    assert health.state is ToolHealthState.HEALTHY
    assert client.pinged is True


# ---- AgentDB ------------------------------------------------------------


def test_agentdb_has_both_read_and_write_operations():
    meta = AgentDBToolAdapter().metadata()
    classes = {op: c.value for op, c in meta.operation_classes.items()}
    assert classes["pattern-search"] == "read-only"
    assert classes["pattern-store"] == "write"


def test_agentdb_placeholder_execute():
    result = _run(AgentDBToolAdapter().execute(ToolRequest(operation="pattern-search")))
    assert result.success is True
    assert "agentdb" in str(result.output).lower()


# ---- GitHub ---------------------------------------------------------------


def test_github_read_operations_vs_write():
    meta = GitHubAdapter().metadata()
    assert meta.operation_classes["list_prs"].value == "read-only"
    assert meta.operation_classes["create_comment"].value == "write"


def test_github_placeholder_execute():
    result = _run(GitHubAdapter().execute(ToolRequest(operation="list_prs")))
    assert result.success is True
    assert "github" in str(result.output).lower()


def test_github_client_injection():
    @dataclass
    class FakeClient:
        async def invoke(self, operation, parameters):
            return ToolResponse(success=True, output=[{"number": 1}])

        async def ping(self):
            return True

    adapter = GitHubAdapter(client=FakeClient())
    result = _run(adapter.execute(ToolRequest(operation="list_prs")))
    assert result.output == [{"number": 1}]


# ---- Codex CLI ------------------------------------------------------------


def test_codex_review_is_read_only_transfer_is_dangerous():
    meta = CodexCLIAdapter().metadata()
    assert meta.operation_classes["review"].value == "read-only"
    assert meta.operation_classes["transfer"].value == "dangerous"


def test_codex_placeholder_execute():
    result = _run(CodexCLIAdapter().execute(ToolRequest(operation="review")))
    assert result.success is True


def test_codex_runner_injection():
    @dataclass
    class FakeRunner:
        async def invoke(self, operation, parameters):
            return ToolResponse(success=True, output="real codex review")

        async def ping(self):
            return True

    adapter = CodexCLIAdapter(runner=FakeRunner())
    result = _run(adapter.execute(ToolRequest(operation="review")))
    assert result.output == "real codex review"


# ---- Claude Code CLI --------------------------------------------------------


def test_claude_code_is_distinct_from_in_process_agent():
    meta = ClaudeCodeAdapter().metadata()
    assert meta.backing_system == "claude-code-cli"
    assert meta.operation_classes["run_command"].value == "write"


def test_claude_code_placeholder_execute():
    result = _run(ClaudeCodeAdapter().execute(ToolRequest(operation="run_command")))
    assert result.success is True


# ---- Local Shell — real subprocess, zero default capability --------------


def test_local_shell_empty_allowlist_denies_everything():
    adapter = LocalShellAdapter()
    result = _run(
        adapter.execute(
            ToolRequest(operation="run", parameters={"command": "echo", "args": ["hi"]})
        )
    )
    assert result.success is False
    assert "allow-list" in result.error


def test_local_shell_allowlisted_command_actually_runs():
    """REAL subprocess execution — proves this adapter is not a placeholder."""
    adapter = LocalShellAdapter(allowed_commands=frozenset({"echo"}))
    result = _run(
        adapter.execute(
            ToolRequest(
                operation="run", parameters={"command": "echo", "args": ["hello-w5"]}
            )
        )
    )
    assert result.success is True
    assert "hello-w5" in result.output


def test_local_shell_unknown_command_reports_not_found():
    adapter = LocalShellAdapter(
        allowed_commands=frozenset({"totally-not-a-real-binary-xyz"})
    )
    result = _run(
        adapter.execute(
            ToolRequest(
                operation="run", parameters={"command": "totally-not-a-real-binary-xyz"}
            )
        )
    )
    assert result.success is False
    assert "not found" in result.error


def test_local_shell_operation_is_always_dangerous():
    """Regardless of the allow-list, the CLASSIFICATION is always DANGEROUS —
    the Runtime's default policy denies it independent of the adapter."""
    adapter = LocalShellAdapter(allowed_commands=frozenset({"echo"}))
    assert adapter.metadata().operation_classes["run"].value == "dangerous"


def test_local_shell_denied_by_default_policy_even_when_allowlisted():
    """End-to-end proof of the two-gate design: allow-listed at the adapter,
    but the Runtime's DEFAULT policy still denies (DANGEROUS -> DENY)."""
    adapter = LocalShellAdapter(allowed_commands=frozenset({"echo"}))
    result = _run(
        ToolRuntime().execute(
            adapter, "run", {"command": "echo", "args": ["hi"]}, trace_id="t"
        )
    )
    assert result.success is False
    assert result.permission_decision.value == "deny"


def test_local_shell_health_reflects_empty_allowlist():
    result = _run(LocalShellAdapter().health())
    assert result.state is ToolHealthState.DEGRADED


# ---- Metadata validation (requirement 11) ----------------------------------


def test_every_builtin_adapter_has_valid_metadata():
    adapters = (
        GraphifyToolAdapter(),
        AgentDBToolAdapter(),
        GitHubAdapter(),
        CodexCLIAdapter(),
        ClaudeCodeAdapter(),
        LocalShellAdapter(),
    )
    for adapter in adapters:
        meta = adapter.metadata()
        assert isinstance(meta, ToolMetadata)
        assert meta.version
        assert meta.author
        assert meta.backing_system
        assert isinstance(meta.tool_type, ToolType)


def test_default_tool_registry_seeds_all_seven():
    reg = default_tool_registry()
    assert {t.id for t in reg.discover()} == {
        "graphify",
        "agentdb",
        "obsidian",
        "github",
        "codex-cli",
        "claude-code",
        "local-shell",
    }


# ---- Plugin registration / dynamic discovery (requirement 9) --------------


@dataclass
class PluginTool:
    """A stand-in for a hypothetical future tool (CrewAI, Gemini CLI, Kimi
    CLI, OpenAI Responses, Neo4j, Pinecone, Weaviate, ...)."""

    id: str = "future-tool"
    name: str = "Future Tool"
    version: str = "0.1.0"
    description: str = "hypothetical third-party tool"
    tool_type: ToolType = ToolType.REST_API
    calls: list = field(default_factory=list)

    @property
    def capabilities(self):
        return ("do_thing",)

    @property
    def type(self):
        return self.tool_type

    async def execute(self, request):
        self.calls.append(request)
        return ToolResponse(success=True, output="plugin handled it")

    async def health(self) -> ToolHealthResult:
        return ToolHealthResult(ToolHealthState.HEALTHY)

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="third-party",
            tool_type=self.tool_type,
            backing_system="future-tool",
            operation_classes={"do_thing": OperationClass.READ_ONLY},
        )


def test_plugin_tool_satisfies_the_protocol():
    assert isinstance(PluginTool(), Tool)


def test_plugin_tool_registers_into_the_production_registry():
    reg = default_tool_registry()
    reg.register(PluginTool())
    assert reg.get("future-tool") is not None
    assert len(reg.discover()) == 8


def test_plugin_tool_dynamically_discoverable_by_capability():
    reg = ToolRegistry()
    reg.register(PluginTool())
    found = reg.find_by_capability("do_thing")
    assert [t.id for t in found] == ["future-tool"]


def test_plugin_tool_executes_through_the_unmodified_runtime():
    plugin = PluginTool()
    result = _run(ToolRuntime().execute(plugin, "do_thing", trace_id="t"))
    assert result.success is True
    assert result.output == "plugin handled it"
    assert result.tool_id == "future-tool"
