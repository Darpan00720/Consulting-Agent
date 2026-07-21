"""Tool & Integration Platform (ADR-013 W5).

A PEER of the Memory Platform (``app.memory``), not a dependency of it — both
sit below the Agent layer, reachable independently:

    Agent → Tool Runtime → Tool Registry → Tool Adapter → MCP/CLI/API/Process/Sync
    Agent → Memory Service → Memory Provider → Graphify/AgentDB/Checkpoints  (W4)

``app.tools`` imports nothing from ``app.agents``/``app.workflow``/``app.memory``
at runtime (only ``TYPE_CHECKING`` for annotations) — the same lower-layer
discipline W3/W4 established. "Agents request tools through the runtime;
agents never invoke adapters directly" (requirement 3) is enforced by there
being no other public entry point: adapters are constructed by
``adapters.default_tool_registry()`` and only ever invoked via
``ToolRuntime.execute()``.

See ``tool.py`` (the ``Tool`` contract), ``permissions.py`` (declarative
allow/deny/interactive policy), ``registry.py`` (discovery), ``runtime.py``
(the execution wrapper), and ``adapters.py`` (the seven built-in adapters).
"""
