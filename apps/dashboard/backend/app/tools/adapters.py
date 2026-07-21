"""Built-in tool adapters (requirement 4).

**ObsidianSyncAdapter and LocalShellAdapter are REAL.** The vault
(``knowledge-vault/``) is plain files on disk — no import, no external
process needed — so scan/parse/change-detection are genuine filesystem
operations. Local shell execution is something THIS Python process can
genuinely do via ``asyncio.create_subprocess_exec`` — but it ships with an
EMPTY default command allow-list AND a DANGEROUS operation class (denied by
the default permission policy), so it is real infrastructure with zero
default capability, not a live risk by construction.

**GraphifyToolAdapter, AgentDBToolAdapter, GitHubAdapter, CodexCLIAdapter, and
ClaudeCodeAdapter are honest placeholders behind an injectable ``client``.**
Verified: none of Graphify, AgentDB, the GitHub API/CLI, the Codex CLI, or a
standalone Claude Code CLI process is importable as a Python library into this
backend — all are external MCP/CLI/API surfaces. The same boundary
established for Codex/Consulting (W2/W3) and Graphify/AgentDB (W4) applies
here: generic tool-execution code must not silently shell out to a real
external process/API as a side effect of a request. Real wiring plugs into
``client``/``runner`` later without touching ``ToolRuntime`` or the registry.

Per requirement: none of these reimplement or modify their backing system —
Graphify, AgentDB, and Obsidian's own file format are used exactly as they are.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.tools.errors import Timeout
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

_RO = OperationClass.READ_ONLY
_WR = OperationClass.WRITE
_DG = OperationClass.DANGEROUS


class ExternalToolClient(Protocol):
    """What a REAL Graphify/AgentDB/GitHub/Codex/Claude-Code client would
    implement — the injection point ``client=``/``runner=`` plugs into. Not
    implemented here (requirement 9: ensure compatibility, don't build the
    integration)."""

    async def invoke(
        self, operation: str, parameters: dict[str, Any]
    ) -> ToolResponse: ...
    async def ping(self) -> bool: ...


# ---- GraphifyToolAdapter (requirement 4) -----------------------------------


@dataclass
class GraphifyToolAdapter:
    """Graphify as a generic TOOL (distinct from ``app.memory.adapters.
    GraphifyAdapter``'s memory-shaped access, W4 — same backing system, two
    deliberately different interfaces: memory retrieve/search vs. arbitrary
    tool invocation with typed operations, e.g. ``get_pr_impact``,
    ``triage_prs``). Graphify remains external — never an agent, never a
    dispatch target (F4, carried forward)."""

    id: str = "graphify"
    name: str = "Graphify"
    version: str = "1.0.0"
    description: str = "Codebase structural graph queries (external MCP)."
    type: ToolType = ToolType.MCP
    is_available: bool = True
    client: ExternalToolClient | None = None

    @property
    def capabilities(self) -> tuple[str, ...]:
        return (
            "query_graph",
            "get_neighbors",
            "get_node",
            "shortest_path",
            "god_nodes",
            "graph_stats",
            "get_community",
            "list_prs",
            "triage_prs",
            "get_pr_impact",
        )

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self.client is not None:
            return await self.client.invoke(request.operation, request.parameters)
        if request.operation not in self.capabilities:
            return ToolResponse(
                success=False, error=f"unsupported operation: {request.operation}"
            )
        return ToolResponse(
            success=True,
            output=(
                f"[graphify placeholder] {request.operation}"
                f"({dict(request.parameters)})"
            ),
        )

    async def health(self) -> ToolHealthResult:
        if self.client is not None:
            try:
                ok = await self.client.ping()
                return ToolHealthResult(
                    ToolHealthState.HEALTHY if ok else ToolHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return ToolHealthResult(
                    ToolHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return ToolHealthResult(
            ToolHealthState.HEALTHY
            if self.is_available
            else ToolHealthState.UNAVAILABLE,
            detail="placeholder client — no real Graphify MCP wiring injected",
        )

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="Graphify (external MCP)",
            tool_type=self.type,
            backing_system="graphify",
            operation_classes={
                op: _RO for op in self.capabilities
            },  # every graph query is read-only
            required_mcps=("graphify",),
        )


# ---- AgentDBToolAdapter (requirement 4) ------------------------------------


@dataclass
class AgentDBToolAdapter:
    """AgentDB (Claude Flow ``agentdb_*`` MCP) as a generic tool — same
    placeholder-with-injectable-client boundary as Graphify. Unlike Graphify,
    genuinely supports writes."""

    id: str = "agentdb"
    name: str = "AgentDB"
    version: str = "1.0.0"
    description: str = "Pattern/context store and semantic routing (external MCP)."
    type: ToolType = ToolType.MCP
    is_available: bool = True
    client: ExternalToolClient | None = None

    @property
    def capabilities(self) -> tuple[str, ...]:
        return (
            "pattern-search",
            "pattern-store",
            "hierarchical-recall",
            "hierarchical-store",
            "context-synthesize",
            "consolidate",
            "feedback",
        )

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self.client is not None:
            return await self.client.invoke(request.operation, request.parameters)
        if request.operation not in self.capabilities:
            return ToolResponse(
                success=False, error=f"unsupported operation: {request.operation}"
            )
        return ToolResponse(
            success=True,
            output=(
                f"[agentdb placeholder] {request.operation}({dict(request.parameters)})"
            ),
        )

    async def health(self) -> ToolHealthResult:
        if self.client is not None:
            try:
                ok = await self.client.ping()
                return ToolHealthResult(
                    ToolHealthState.HEALTHY if ok else ToolHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return ToolHealthResult(
                    ToolHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return ToolHealthResult(
            ToolHealthState.HEALTHY
            if self.is_available
            else ToolHealthState.UNAVAILABLE,
            detail="placeholder client — no real AgentDB MCP wiring injected",
        )

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="Claude Flow (external MCP)",
            tool_type=self.type,
            backing_system="agentdb",
            operation_classes={
                "pattern-search": _RO,
                "hierarchical-recall": _RO,
                "context-synthesize": _RO,
                "pattern-store": _WR,
                "hierarchical-store": _WR,
                "consolidate": _WR,
                "feedback": _WR,
            },
            required_mcps=("agentdb",),
        )


# ---- ObsidianSyncAdapter — REAL (requirement 8) ----------------------------


@dataclass(frozen=True)
class VaultNote:
    """One parsed Markdown note: frontmatter + body."""

    path: str
    frontmatter: dict[str, str]
    body: str
    mtime: float


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Minimal, REAL frontmatter parser: ``---\\nkey: value\\n---\\nbody``.

    Deliberately simple (flat ``key: value`` pairs only, no lists/nesting) —
    this backend has no YAML dependency (``pyproject.toml`` confirmed: no
    pyyaml), and the vault's actual frontmatter shape
    (``packages/knowledge/vault_validator.py``'s ``CommonHeader``) is flat
    key/value. Not a reimplementation of that validator — a smaller, honest,
    real parser scoped to what THIS adapter needs (scan/detect-change), not
    full schema validation.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_text, body = parts[1], parts[2]
    frontmatter: dict[str, str] = {}
    for line in fm_text.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip().strip("\"'")
    return frontmatter, body.lstrip("\n")


@dataclass
class ObsidianSyncAdapter:
    """Obsidian is a HUMAN knowledge workspace (a Markdown vault) — NOT a
    runtime memory provider (requirement 8's own framing; contrast with
    ``app.memory``'s providers, which ARE runtime memory). This adapter's job
    is sync mechanics: scan, parse, detect changes, and hand changed notes to
    an indexing hook. It does not answer retrieval queries itself — that is
    Graphify's (or the knowledge-vault's own retrieval_adapter's) job,
    unchanged and unmodified.

    ``sync()`` is pull-direction only (vault → our knowledge of it).
    "Future bidirectional sync should be possible" (requirement 8) —
    ``index_note`` is the one seam a push-direction (writing FROM an external
    source back INTO the vault) would extend; scan/parse/detect_changes stay
    read-only primitives either way, so adding a write path later does not
    require redesigning them.
    """

    id: str = "obsidian"
    name: str = "Obsidian Knowledge Sync"
    version: str = "1.0.0"
    description: str = "Human knowledge workspace (Markdown vault) sync."
    type: ToolType = ToolType.KNOWLEDGE_SYNC
    vault_dir: Path = field(default_factory=lambda: Path("knowledge-vault"))
    graphify_indexer: ExternalToolClient | None = None
    _known_mtimes: dict[str, float] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # A caller naturally supplies a plain string (a config value, an env
        # var) — coerce it here rather than crashing on the first .exists()/
        # .rglob() call. Found by a real test passing vault_dir as str.
        if not isinstance(self.vault_dir, Path):
            self.vault_dir = Path(self.vault_dir)

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("scan_vault", "parse_note", "detect_changes", "sync", "index_note")

    def scan_vault(self) -> tuple[str, ...]:
        """REAL: every ``.md`` file under ``vault_dir``, relative, sorted."""
        if not self.vault_dir.exists():
            return ()
        return tuple(
            str(p.relative_to(self.vault_dir))
            for p in sorted(self.vault_dir.rglob("*.md"))
        )

    def parse_note(self, rel_path: str) -> VaultNote:
        """REAL: read one note from disk and split frontmatter/body."""
        full = self.vault_dir / rel_path
        text = full.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(text)
        return VaultNote(
            path=rel_path,
            frontmatter=frontmatter,
            body=body,
            mtime=full.stat().st_mtime,
        )

    def detect_changes(self) -> tuple[str, ...]:
        """REAL: mtime diff against the last known ``sync()`` baseline. New or
        modified notes only — deletion detection is a future bidirectional-
        sync concern, out of this phase's scope per requirement 8's own text."""
        changed = []
        for rel in self.scan_vault():
            mtime = (self.vault_dir / rel).stat().st_mtime
            if self._known_mtimes.get(rel) != mtime:
                changed.append(rel)
        return tuple(changed)

    def sync(self) -> tuple[VaultNote, ...]:
        """REAL sync pipeline: scan → detect changes → parse changed notes →
        advance the baseline. Does NOT index — that is the separate,
        explicit ``index_note`` step, so a caller can inspect changes before
        committing them to the graph."""
        changed_paths = self.detect_changes()
        notes = tuple(self.parse_note(p) for p in changed_paths)
        for note in notes:
            self._known_mtimes[note.path] = (self.vault_dir / note.path).stat().st_mtime
        return notes

    async def index_note(self, note: VaultNote) -> ToolResponse:
        """Graphify indexing hook (requirement 8) — PLACEHOLDER: Graphify
        itself remains external/MCP-only (unchanged since W4); real indexing
        plugs into ``graphify_indexer`` without touching sync mechanics."""
        if self.graphify_indexer is not None:
            return await self.graphify_indexer.invoke(
                "index_note", {"path": note.path, "frontmatter": note.frontmatter}
            )
        return ToolResponse(
            success=True, output=f"[graphify placeholder] would index {note.path!r}"
        )

    async def execute(self, request: ToolRequest) -> ToolResponse:
        op = request.operation
        try:
            if op == "scan_vault":
                return ToolResponse(success=True, output=self.scan_vault())
            if op == "parse_note":
                return ToolResponse(
                    success=True, output=self.parse_note(request.parameters["path"])
                )
            if op == "detect_changes":
                return ToolResponse(success=True, output=self.detect_changes())
            if op == "sync":
                return ToolResponse(success=True, output=self.sync())
            if op == "index_note":
                note = request.parameters.get("note") or self.parse_note(
                    request.parameters["path"]
                )
                return await self.index_note(note)
        except FileNotFoundError as exc:
            return ToolResponse(success=False, error=f"vault path not found: {exc}")
        return ToolResponse(success=False, error=f"unsupported operation: {op}")

    async def health(self) -> ToolHealthResult:
        if not self.vault_dir.exists():
            return ToolHealthResult(
                ToolHealthState.UNAVAILABLE,
                detail=f"vault dir not found: {self.vault_dir}",
            )
        return ToolHealthResult(ToolHealthState.HEALTHY)

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="StratAgent",
            tool_type=self.type,
            backing_system="obsidian",
            operation_classes={
                "scan_vault": _RO,
                "parse_note": _RO,
                "detect_changes": _RO,
                "sync": _RO,
                "index_note": _WR,
            },
        )


# ---- GitHubAdapter (requirement 4) -----------------------------------------


@dataclass
class GitHubAdapter:
    """GitHub repo/PR/issue access — placeholder + injectable client (module
    docstring). Distinct from ADR-012's "GitHub Models" (an LLM provider in
    ``providers.py``'s chain) — this is repository/PR/issue access, a
    genuinely new capability this backend never had."""

    id: str = "github"
    name: str = "GitHub"
    version: str = "1.0.0"
    description: str = "Repository, PR, and issue access."
    type: ToolType = ToolType.REST_API
    is_available: bool = True
    client: ExternalToolClient | None = None

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("list_prs", "get_pr", "list_issues", "get_file", "create_comment")

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self.client is not None:
            return await self.client.invoke(request.operation, request.parameters)
        if request.operation not in self.capabilities:
            return ToolResponse(
                success=False, error=f"unsupported operation: {request.operation}"
            )
        return ToolResponse(
            success=True,
            output=(
                f"[github placeholder] {request.operation}({dict(request.parameters)})"
            ),
        )

    async def health(self) -> ToolHealthResult:
        if self.client is not None:
            try:
                ok = await self.client.ping()
                return ToolHealthResult(
                    ToolHealthState.HEALTHY if ok else ToolHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return ToolHealthResult(
                    ToolHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return ToolHealthResult(
            ToolHealthState.HEALTHY
            if self.is_available
            else ToolHealthState.UNAVAILABLE,
            detail="placeholder client — no real GitHub API/CLI wiring injected",
        )

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="GitHub (external REST API)",
            tool_type=self.type,
            backing_system="github",
            operation_classes={
                "list_prs": _RO,
                "get_pr": _RO,
                "list_issues": _RO,
                "get_file": _RO,
                "create_comment": _WR,
            },
        )


# ---- CodexCLIAdapter (requirement 4) ---------------------------------------


@dataclass
class CodexCLIAdapter:
    """The Codex CLI plugin as a tool — placeholder + injectable runner
    (module docstring). Mirrors ``app.agents.builtin.CodexAgent`` (W3) at the
    Tool-Platform layer; ``transfer`` is classified DANGEROUS (denied by
    default) because it sends real session transcripts externally — the same
    data-sharing concern ADR-010 §6c flags explicitly for that command."""

    id: str = "codex-cli"
    name: str = "Codex CLI"
    version: str = "1.0.0"
    description: str = "OpenAI Codex — independent code review and mechanical work."
    type: ToolType = ToolType.CLI
    is_available: bool = True
    runner: ExternalToolClient | None = None

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("review", "adversarial_review", "rescue", "transfer")

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self.runner is not None:
            return await self.runner.invoke(request.operation, request.parameters)
        if request.operation not in self.capabilities:
            return ToolResponse(
                success=False, error=f"unsupported operation: {request.operation}"
            )
        return ToolResponse(
            success=True,
            output=f"[codex-cli placeholder] would run {request.operation}",
        )

    async def health(self) -> ToolHealthResult:
        if self.runner is not None:
            try:
                ok = await self.runner.ping()
                return ToolHealthResult(
                    ToolHealthState.HEALTHY if ok else ToolHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return ToolHealthResult(
                    ToolHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return ToolHealthResult(
            ToolHealthState.HEALTHY
            if self.is_available
            else ToolHealthState.UNAVAILABLE,
            detail="placeholder runner — no real Codex CLI wiring injected",
        )

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="OpenAI (Codex CLI, external)",
            tool_type=self.type,
            backing_system="codex-cli",
            operation_classes={
                "review": _RO,
                "adversarial_review": _RO,
                "rescue": _WR,
                "transfer": _DG,
            },
            required_tools=("codex-cli",),
        )


# ---- ClaudeCodeAdapter (requirement 4) -------------------------------------


@dataclass
class ClaudeCodeAdapter:
    """A separate Claude Code CLI PROCESS as a tool — placeholder + injectable
    runner. Distinct from ``app.agents.builtin.ClaudeAgent`` (W3), which calls
    the Provider Router IN-PROCESS: this represents shelling out to an
    external ``claude`` CLI session (e.g. spawning an independent sub-agent
    process), a genuinely different mechanism this backend doesn't itself
    have wired up."""

    id: str = "claude-code"
    name: str = "Claude Code CLI"
    version: str = "1.0.0"
    description: str = (
        "An external Claude Code CLI process (distinct from the in-process agent)."
    )
    type: ToolType = ToolType.CLI
    is_available: bool = True
    runner: ExternalToolClient | None = None

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("run_command", "spawn_subagent")

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if self.runner is not None:
            return await self.runner.invoke(request.operation, request.parameters)
        if request.operation not in self.capabilities:
            return ToolResponse(
                success=False, error=f"unsupported operation: {request.operation}"
            )
        return ToolResponse(
            success=True,
            output=f"[claude-code placeholder] would run {request.operation}",
        )

    async def health(self) -> ToolHealthResult:
        if self.runner is not None:
            try:
                ok = await self.runner.ping()
                return ToolHealthResult(
                    ToolHealthState.HEALTHY if ok else ToolHealthState.UNAVAILABLE
                )
            except Exception as exc:  # noqa: BLE001 — a broken probe is UNAVAILABLE
                return ToolHealthResult(
                    ToolHealthState.UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"
                )
        return ToolHealthResult(
            ToolHealthState.HEALTHY
            if self.is_available
            else ToolHealthState.UNAVAILABLE,
            detail="placeholder runner — no real Claude Code CLI wiring injected",
        )

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="Anthropic (Claude Code CLI, external process)",
            tool_type=self.type,
            backing_system="claude-code-cli",
            operation_classes={"run_command": _WR, "spawn_subagent": _WR},
            required_tools=("claude",),
        )


# ---- LocalShellAdapter — REAL, zero default capability (requirement 4) ----


@dataclass
class LocalShellAdapter:
    """REAL local process execution via ``asyncio.create_subprocess_exec`` —
    unlike the MCP/CLI adapters above, this backend genuinely can run a local
    command. Safe by construction, not by policy alone: TWO independent gates
    must both open before anything runs — (1) the command must be in
    ``allowed_commands`` (EMPTY by default — nothing is allow-listed out of
    the box), AND (2) the ``run`` operation is classified DANGEROUS, which the
    default ``PermissionPolicy`` denies outright. A caller must deliberately
    relax both to execute anything."""

    id: str = "local-shell"
    name: str = "Local Shell"
    version: str = "1.0.0"
    description: str = "Local process execution — empty command allow-list by default."
    type: ToolType = ToolType.LOCAL_PROCESS
    allowed_commands: frozenset[str] = field(default_factory=frozenset)
    proc_timeout_s: float = 10.0

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("run",)

    async def execute(self, request: ToolRequest) -> ToolResponse:
        if request.operation != "run":
            return ToolResponse(
                success=False, error=f"unsupported operation: {request.operation}"
            )
        command = request.parameters.get("command")
        args = list(request.parameters.get("args", ()))
        if command not in self.allowed_commands:
            return ToolResponse(
                success=False,
                error=f"'{command}' is not in the allow-list (empty by default)",
            )
        try:
            proc = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.proc_timeout_s
                )
            except TimeoutError as exc:
                proc.kill()
                await proc.wait()
                raise Timeout(
                    f"local process '{command}' exceeded {self.proc_timeout_s}s"
                ) from exc
        except FileNotFoundError:
            return ToolResponse(success=False, error=f"command not found: {command}")
        if proc.returncode != 0:
            return ToolResponse(
                success=False,
                error=stderr.decode(errors="replace") or f"exit code {proc.returncode}",
            )
        return ToolResponse(success=True, output=stdout.decode(errors="replace"))

    async def health(self) -> ToolHealthResult:
        if not self.allowed_commands:
            return ToolHealthResult(
                ToolHealthState.DEGRADED, detail="no commands allow-listed"
            )
        return ToolHealthResult(ToolHealthState.HEALTHY)

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            version=self.version,
            author="StratAgent",
            tool_type=self.type,
            backing_system="local-shell",
            operation_classes={"run": _DG},  # always DANGEROUS regardless of allow-list
        )


def default_tool_registry() -> ToolRegistry:
    """The production registry, seeded with all seven built-in adapters
    (mirrors ``app.agents.builtin.default_agent_registry()``, W3)."""
    registry = ToolRegistry()
    for tool in (
        GraphifyToolAdapter(),
        AgentDBToolAdapter(),
        ObsidianSyncAdapter(),
        GitHubAdapter(),
        CodexCLIAdapter(),
        ClaudeCodeAdapter(),
        LocalShellAdapter(),
    ):
        registry.register(tool)
    return registry
