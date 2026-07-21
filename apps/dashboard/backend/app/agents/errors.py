"""Agent error model (requirement 11).

The Runtime maps every failure — a raised exception, a business-logic
``AgentResponse(success=False)``, a timeout, a cancellation — into one of
these. A raw exception never escapes ``AgentRuntime.execute()``; callers only
ever see an ``ExecutionResult`` with ``error``/``error_type`` set, or one of
these types if they call runtime internals directly.
"""

from __future__ import annotations


class AgentError(Exception):
    """Base class for every Agent Platform error."""


class AgentUnavailable(AgentError):
    """The agent is not currently usable (lifecycle/health state)."""


class CapabilityMismatch(AgentError):
    """The caller required a capability this agent does not declare."""


class ExecutionFailure(AgentError):
    """The agent's own business logic failed (raised or reported)."""


class Timeout(AgentError):
    """Execution did not complete within its budget."""


class Cancelled(AgentError):
    """Execution was cancelled via a CancellationToken."""


class ConfigurationError(AgentError):
    """The agent/registry/runtime is misconfigured (e.g. an illegal lifecycle
    transition, a duplicate/unknown agent lookup)."""


class UnsupportedWorkflow(AgentError):
    """The workflow category is not in the agent's ``supported_workflows``."""
