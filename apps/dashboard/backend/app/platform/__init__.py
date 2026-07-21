"""Platform Integration & Operational Readiness (ADR-013 W6).

The COMPOSITION ROOT for StratAgent's five platform layers (Workflow Router
W1, Dispatcher W2, Agent Runtime W3, Memory Platform W4, Tool Platform W5).
This package does not add or move business logic — it constructs each
layer's existing public factory (``default_agent_registry()``,
``default_memory_registry()``, ``default_tool_registry()``,
``providers.build_chain()``, ``targets.default_registry()``,
``AgentRuntime()``, ``ToolRuntime()``, ``MemoryService(registry)``) and wires
the results into one immutable ``Platform`` object.

    bootstrap() → Platform(config, registries, runtimes, provider_chain, ...)

No layer is redesigned; no responsibility moves. See ``bootstrap.py`` for the
single initialization entry point (requirement 1) and
``docs/operations/Platform-Operations.md`` for the operational reference.
"""
