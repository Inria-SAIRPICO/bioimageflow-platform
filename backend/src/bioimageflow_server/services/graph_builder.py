"""Translate a GUI ``GraphState`` into a :class:`bioimageflow.Workflow`.

Thin adapter over :func:`graph_state_to_lib_dict` +
:meth:`bioimageflow.Workflow.from_dict`. The platform is not responsible
for graph semantics — cycle detection, type compatibility, missing
required inputs, and signature hashing all live in the library. See
:mod:`graph_translator` for the wire-format translation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.services.graph_translator import (
    graph_state_to_lib_dict,
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


@dataclass
class GraphBuildResult:
    """Output of :func:`build_workflow`.

    ``workflow`` is the library ``Workflow`` (always present, even when
    partially wired — some nodes may have been skipped). ``node_map``
    maps GUI node IDs to their library ``Node`` objects.
    """

    workflow: Any | None
    node_map: dict[str, Any] = field(default_factory=dict)
    errors: list[GraphValidationError] = field(default_factory=list)
    disabled_node_ids: set[str] = field(default_factory=set)
    tool_classes: dict[str, type] = field(default_factory=dict)
    tool_instances: dict[str, Any] = field(default_factory=dict)
    # Exposed for the validator so error mapping can attribute library
    # errors back to GUI edge UUIDs.
    edge_id_by_key: dict[tuple[str, str, str], str] = field(default_factory=dict)


def build_workflow(
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    on_progress: Callable[[Any], None] | None = None,
) -> GraphBuildResult:
    """Translate ``graph`` into a library :class:`Workflow`.

    Collects structural errors from the translator and node-construction
    errors from :meth:`Workflow.from_dict` into a single error list.
    The returned workflow is best-effort partially wired — nodes whose
    tool class fails to resolve or construct are omitted, but the
    container itself is always non-None so callers can continue to
    drive validation and planning.
    """
    from bioimageflow.workflow import Workflow

    translation = graph_state_to_lib_dict(
        graph, registry, storage_path=storage_path,
    )
    errors: list[GraphValidationError] = list(translation.errors)

    from_dict_result = Workflow.from_dict(
        translation.lib_dict,
        collect_errors=True,
        storage_path_override=storage_path,
        on_progress=on_progress,
        use_wetlands=False,
        auto_install=False,
    )
    # collect_errors=True guarantees a (workflow, errors) tuple
    assert isinstance(from_dict_result, tuple)
    workflow, lib_errors = from_dict_result

    errors.extend(
        lib_validation_error_to_graph_error(e, translation.edge_id_by_key)
        for e in lib_errors
    )

    node_map: dict[str, Any] = dict(workflow._nodes) if workflow is not None else {}
    tool_classes: dict[str, type] = {
        name: type(node.tool) for name, node in node_map.items()
    }
    tool_instances: dict[str, Any] = {
        name: node.tool for name, node in node_map.items()
    }
    disabled = {n.id for n in graph.nodes if not n.enabled}

    return GraphBuildResult(
        workflow=workflow,
        node_map=node_map,
        errors=errors,
        disabled_node_ids=disabled,
        tool_classes=tool_classes,
        tool_instances=tool_instances,
        edge_id_by_key=translation.edge_id_by_key,
    )
