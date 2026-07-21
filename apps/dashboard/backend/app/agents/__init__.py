"""Agent Platform & Runtime (ADR-013 W3).

Sits BELOW the Workflow Router / Dispatcher in the request flow but is a
LOWER, independent layer in the import graph: ``app.agents`` never imports
from ``app.workflow`` — ``app.workflow.targets`` imports FROM here (its
``Target.invoke()`` implementations delegate to ``AgentRuntime.execute()``).
This keeps the platform reusable and prevents any circular dependency.

    Dispatcher → Target.invoke() → AgentRuntime.execute() → Agent → Provider Router

See ``agent.py`` (the Agent contract), ``registry.py`` (discovery/lifecycle),
``runtime.py`` (the execution wrapper), and ``builtin.py`` (the four agents
converted from W2's Targets: Claude, Codex, Consulting, Repository Analysis).
"""
