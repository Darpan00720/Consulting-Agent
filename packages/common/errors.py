"""Common exception hierarchy.

A single root error type lets callers catch all StratAgent errors uniformly.
Specific error types are added by the milestones that need them.
"""

from __future__ import annotations


class StratAgentError(Exception):
    """Base class for all StratAgent errors."""
