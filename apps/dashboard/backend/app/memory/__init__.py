"""Memory & Knowledge Platform (ADR-013 W4).

Sits BELOW the Agent Runtime in the request flow but is a LOWER, independent
layer in the import graph — the same pattern W3 established for
``app.agents``: ``app.memory`` never imports from ``app.agents`` or
``app.workflow`` at runtime; ``app.agents`` imports FROM here (opt-in, lazily)
to inject memory into an execution.

    Agent → MemoryService → MemoryProvider → Graphify / AgentDB / Checkpoints / …

See ``provider.py`` (the ``MemoryProvider`` contract), ``registry.py``
(discovery/priority/default), ``service.py`` (retrieval-strategy selection +
caching + telemetry + error-mapping), and ``adapters.py`` (the three built-in
providers).
"""
