"""Knowledge versioning (requester's "Knowledge Versioning" section):
deprecation, replacement, backward compatibility, migration, execution
history.

A side ledger, not a mutation of ``FrameworkRegistry`` — ``FrameworkDefinition``
is frozen (a catalog entry is immutable once registered; a content change is
a NEW version, per the requester's own "Knowledge Versioning" framing), so
deprecation/history are tracked here, alongside the registry, the same
relationship ``app.platform.observability.TraceCollector`` has to the 5
platform loggers it observes without modifying.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.knowledge.errors import DeprecatedFrameworkError
from app.knowledge.models import (
    DeprecationInfo,
    ExecutionHistoryEntry,
    FrameworkDefinition,
)
from app.knowledge.registry import FrameworkRegistry


@dataclass
class VersioningLedger:
    _deprecations: dict[tuple[str, str], DeprecationInfo] = field(default_factory=dict)
    _history: dict[str, list[ExecutionHistoryEntry]] = field(
        default_factory=lambda: defaultdict(list)
    )

    # ---- deprecation / replacement -----------------------------------------

    def mark_deprecated(
        self,
        framework_id: str,
        version: str,
        *,
        replaced_by: str | None = None,
        reason: str = "",
    ) -> DeprecationInfo:
        info = DeprecationInfo(
            framework_id=framework_id,
            version=version,
            replaced_by=replaced_by,
            reason=reason,
        )
        self._deprecations[(framework_id, version)] = info
        return info

    def is_deprecated(self, framework_id: str, version: str) -> bool:
        return (framework_id, version) in self._deprecations

    def deprecation_info(
        self, framework_id: str, version: str
    ) -> DeprecationInfo | None:
        return self._deprecations.get((framework_id, version))

    # ---- backward-compatible resolution / migration ------------------------

    def resolve(
        self,
        registry: FrameworkRegistry,
        framework_id: str,
        version: str | None = None,
        *,
        allow_deprecated: bool = True,
    ) -> FrameworkDefinition:
        """Backward-compatible by default: an existing caller pinned to a
        now-deprecated version keeps working (``allow_deprecated=True``,
        the default) — deprecating a framework never silently breaks a
        caller already using it. Set ``allow_deprecated=False`` to opt into
        migration: redirected transparently to ``replaced_by`` if one is
        declared, or a ``DeprecatedFrameworkError`` if none exists (there is
        genuinely nothing safe to fall back to)."""
        framework = registry.get(framework_id, version)
        info = self.deprecation_info(framework.id, framework.version)
        if info is None or allow_deprecated:
            return framework
        if info.replaced_by is not None:
            return registry.get(info.replaced_by)
        raise DeprecatedFrameworkError(
            f"{framework.id} v{framework.version} is deprecated with no "
            f"replacement: {info.reason}"
        )

    # ---- execution history --------------------------------------------------

    def record_execution(self, entry: ExecutionHistoryEntry) -> None:
        self._history[entry.framework_id].append(entry)

    def history_for(self, framework_id: str) -> tuple[ExecutionHistoryEntry, ...]:
        return tuple(self._history.get(framework_id, ()))
