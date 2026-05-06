"""Translate a GUI ``GraphState`` into a :class:`bioimageflow.Workflow`.

Thin adapter over :func:`graph_state_to_lib_dict` +
:meth:`bioimageflow.Workflow.from_dict`. The platform is not responsible
for graph semantics -- cycle detection, type compatibility, missing
required inputs, and signature hashing all live in the library. See
:mod:`graph_translator` for the wire-format translation.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.services.graph_translator import (
    graph_state_to_lib_dict,
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings


class BuildOutput(NamedTuple):
    """Return type of :func:`build_workflow`."""

    workflow: Any
    errors: list[GraphValidationError]
    disabled_node_ids: set[str]


def build_workflow(
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    on_progress: Callable[[Any], None] | None = None,
    settings: "Settings | None" = None,
) -> BuildOutput:
    """Translate ``graph`` into a library :class:`Workflow`.

    Returns a ``(workflow, errors, disabled_node_ids)`` tuple. The
    workflow is always non-None (``validate_only=True, partial=True``).
    """
    from bioimageflow.workflow import Workflow

    translation = graph_state_to_lib_dict(
        graph, registry, storage_path=storage_path, settings=settings,
    )
    errors: list[GraphValidationError] = list(translation.errors)

    result = Workflow.from_dict(
        translation.lib_dict,
        validate_only=True,
        partial=True,
        storage_path_override=storage_path,
        on_progress=on_progress,
        use_wetlands=graph_requires_wetlands(graph, registry),
        auto_install=False,
    )
    assert isinstance(result, tuple)
    workflow, lib_errors = result

    errors.extend(lib_validation_error_to_graph_error(e) for e in lib_errors)
    disabled = {n.id for n in graph.nodes if not n.enabled}

    return BuildOutput(workflow, errors, disabled)


def graph_requires_wetlands(
    graph: GraphState,
    registry: ToolRegistryService,
) -> bool:
    """Return True when an enabled graph node needs ProcessingTool execution."""
    from bioimageflow_core.tool import ProcessingTool

    for node in graph.nodes:
        if not node.enabled:
            continue

        if node.sub_workflow is not None:
            if graph_requires_wetlands(node.sub_workflow, registry):
                return True
            continue

        tool_class = registry.get_tool_class(node.tool_name)
        if tool_class is None:
            # The graph will surface a missing-tool/package error later.
            # Default to the stricter execution mode for malformed graphs.
            return True
        if issubclass(tool_class, ProcessingTool):
            return True
    return False
