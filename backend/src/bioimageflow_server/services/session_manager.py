"""Per-graph :class:`WorkflowSession` lifecycle manager.

The platform supports one active graph at a time. The session manager
holds a single :class:`WorkflowSession` that is rebuilt on every
``PUT /graph`` (full replace) and mutated in place on
``PATCH /node/{id}/parameters`` (keystroke-rate constant edits).

The session caches a :class:`Workflow` across non-structural edits so
that constant changes never trigger tool re-resolution — the
load-bearing contract documented in the library's
``PLATFORM_MIGRATION.md`` section 10.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.services.graph_translator import graph_state_to_lib_dict
from bioimageflow_server.services.tool_registry import ToolRegistryService

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the active :class:`WorkflowSession` for the platform.

    Singleton-like: one instance is created at startup and injected into
    routers. There is at most one active session at any time.
    """

    def __init__(self) -> None:
        self._session: Any | None = None
        self._storage_path: Path | None = None
        self._translation_errors: list[GraphValidationError] = []
        self._disabled_node_ids: set[str] = set()

    # -- Lifecycle -----------------------------------------------------------

    def load(
        self,
        graph: GraphState,
        registry: ToolRegistryService,
        *,
        storage_path: Path | None = None,
        settings: "Settings | None" = None,
    ) -> list[GraphValidationError]:
        """Replace the active session with a new one derived from ``graph``.

        Translates ``GraphState`` into the library dict via the existing
        translator (structural checks, tool resolution, edge validation),
        then wraps the result in a ``WorkflowSession``.

        Returns the translation-level errors (duplicate IDs, missing
        tools, etc.) so the caller can include them alongside the
        library's own validation errors.
        """
        from bioimageflow import WorkflowSession

        translation = graph_state_to_lib_dict(
            graph, registry, storage_path=storage_path, settings=settings,
        )
        self._translation_errors = list(translation.errors)
        self._disabled_node_ids = {n.id for n in graph.nodes if not n.enabled}

        storage_str = (
            str(storage_path) if storage_path is not None else None
        )
        self._storage_path = Path(storage_path) if storage_path is not None else None
        self._session = WorkflowSession(
            translation.lib_dict,
            storage_path=storage_str,
        )
        return list(self._translation_errors)

    @property
    def session(self) -> Any | None:
        """The active :class:`WorkflowSession`, or ``None``."""
        return self._session

    @property
    def translation_errors(self) -> list[GraphValidationError]:
        """Structural errors from the last :meth:`load` call."""
        return list(self._translation_errors)

    @property
    def storage_path(self) -> Path | None:
        """Storage path used to build the active session, if explicit."""
        return self._storage_path

    @property
    def disabled_node_ids(self) -> set[str]:
        """Node IDs that were disabled in the last loaded graph."""
        return set(self._disabled_node_ids)

    def clear(self) -> None:
        """Drop the active session."""
        self._session = None
        self._storage_path = None
        self._translation_errors = []
        self._disabled_node_ids = set()
