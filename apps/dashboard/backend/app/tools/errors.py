"""Tool error model (requirement 10).

``ToolRuntime`` maps every failure — a permission denial, a raised exception,
a timeout, a cancellation — into one of these. A raw adapter exception never
escapes the Runtime; callers only ever see a ``ToolResult`` with
``error``/``error_type`` set (or one of these types if calling a ``Tool``
adapter directly).
"""

from __future__ import annotations


class ToolError(Exception):
    """Base class for every Tool Platform error."""


class ToolUnavailable(ToolError):
    """The resolved tool is not currently usable (health/registration state)."""


class PermissionDenied(ToolError):
    """The permission policy denied this operation, or it needs interactive
    approval that was never supplied."""


class ExecutionFailure(ToolError):
    """The adapter's own business logic failed (raised or reported)."""


class Timeout(ToolError):
    """The operation did not complete within its budget."""


class Cancelled(ToolError):
    """Execution was cancelled via a CancellationToken.

    Not in requirement 10's example list, but required by requirement 3's
    cancellation support — the same taxonomy extension Agent Runtime (W3)
    made for the identical reason: "no raw exceptions escape" needs SOME
    typed representation for a cancelled execution.
    """


class ConfigurationError(ToolError):
    """The tool/registry/runtime is misconfigured."""


class UnsupportedCapability(ToolError):
    """The resolved tool does not declare the requested operation/capability."""
