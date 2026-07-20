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
from bioimageflow_server.models.graph import WorkflowNodeState
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.services.graph_translator import (
    graph_state_to_lib_dict,
    graph_requires_wetlands,
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
        engine="wetlands" if graph_requires_wetlands(graph, registry) else "direct",
        execution=translation.lib_dict["config"]["execution"],
        auto_install=False,
    )
    assert isinstance(result, tuple)
    workflow, lib_errors = result

    for library_error in lib_errors:
        translated = lib_validation_error_to_graph_error(library_error)
        duplicate_resolution_error = translated.type in {"missing_tool", "missing_package"} and any(
            error.node == translated.node
            and error.type in {"missing_tool", "missing_package"}
            for error in errors
        )
        if not duplicate_resolution_error:
            errors.append(translated)
    disabled: set[str] = set()

    def collect_disabled(current: GraphState, scope: tuple[str, ...] = ()) -> None:
        for node in current.nodes:
            path = "/".join((*scope, node.id))
            if not node.enabled:
                disabled.add(path)
            if isinstance(node, WorkflowNodeState):
                collect_disabled(node.workflow, (*scope, node.id))

    collect_disabled(graph)

    return BuildOutput(workflow, errors, disabled)
