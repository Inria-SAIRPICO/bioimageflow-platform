"""Request-local graph compilation.

Compilation receives the complete graph and storage context explicitly.
The service retains no workflow or graph state between calls.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.services.graph_builder import BuildOutput, build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings


class GraphCompiler:
    """Compile immutable request graphs without process-global graph state."""

    def __init__(self, registry: ToolRegistryService) -> None:
        self._registry = registry

    def compile(
        self,
        graph: GraphState,
        *,
        storage_path: Path | None = None,
        on_progress: Callable[[Any], None] | None = None,
        settings: Settings | None = None,
    ) -> BuildOutput:
        return build_workflow(
            graph,
            self._registry,
            storage_path=storage_path,
            on_progress=on_progress,
            settings=settings,
        )
