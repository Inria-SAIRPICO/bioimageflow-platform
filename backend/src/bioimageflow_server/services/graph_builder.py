"""Translate a GUI ``GraphState`` into a bioimageflow ``Workflow``.

This service is deliberately narrow: it validates structural integrity
(unique IDs, valid edge endpoints), resolves tool classes from the
registry, instantiates library ``Node`` objects, and wires edges. It
does **not** perform cycle/type/parameter validation — that is the job
of :mod:`graph_validator`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    PositionalEdge,
)
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.services.tool_registry import ToolRegistryService


@dataclass
class GraphBuildResult:
    """Output of :func:`build_workflow`.

    ``workflow`` is the bioimageflow ``Workflow`` container (always built,
    even in the presence of errors, so partial validation can proceed on
    the remaining valid nodes). ``node_map`` maps GUI node IDs to the
    library ``Node`` objects that were successfully created.
    """

    workflow: Any | None
    node_map: dict[str, Any] = field(default_factory=dict)
    errors: list[GraphValidationError] = field(default_factory=list)
    disabled_node_ids: set[str] = field(default_factory=set)
    tool_classes: dict[str, type] = field(default_factory=dict)
    tool_instances: dict[str, Any] = field(default_factory=dict)


def build_workflow(
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    on_progress: Callable[[Any], None] | None = None,
) -> GraphBuildResult:
    """Translate ``graph`` into a bioimageflow ``Workflow``.

    Returns a :class:`GraphBuildResult` containing the workflow, a map
    of GUI node IDs to library ``Node`` objects, any structural errors
    encountered during construction, and the set of disabled node IDs.
    """
    from bioimageflow.node import ColumnRef
    from bioimageflow.workflow import Workflow

    errors: list[GraphValidationError] = []
    disabled: set[str] = set()
    node_map: dict[str, Any] = {}
    tool_classes: dict[str, type] = {}
    tool_instances: dict[str, Any] = {}

    # --- Structural integrity: node ID uniqueness ---
    seen_node_ids: set[str] = set()
    duplicate_node_ids: set[str] = set()
    for node in graph.nodes:
        if node.id in seen_node_ids:
            duplicate_node_ids.add(node.id)
            errors.append(
                GraphValidationError(
                    type="invalid_node_id",
                    detail=f"Duplicate node ID: {node.id}",
                    node=node.id,
                )
            )
        seen_node_ids.add(node.id)

    # --- Structural integrity: edge ID uniqueness and endpoint validity ---
    seen_edge_ids: set[str] = set()
    valid_node_ids = {n.id for n in graph.nodes}
    for edge in graph.edges:
        if edge.id in seen_edge_ids:
            errors.append(
                GraphValidationError(
                    type="invalid_edge_id",
                    detail=f"Duplicate edge ID: {edge.id}",
                    edge_id=edge.id,
                )
            )
        seen_edge_ids.add(edge.id)
        if edge.source_node not in valid_node_ids:
            errors.append(
                GraphValidationError(
                    type="invalid_edge_id",
                    detail=(
                        f"Edge {edge.id} references unknown source node: "
                        f"{edge.source_node}"
                    ),
                    edge_id=edge.id,
                )
            )
        if edge.target_node not in valid_node_ids:
            errors.append(
                GraphValidationError(
                    type="invalid_edge_id",
                    detail=(
                        f"Edge {edge.id} references unknown target node: "
                        f"{edge.target_node}"
                    ),
                    edge_id=edge.id,
                )
            )

    # --- Build the workflow container ---
    storage = Path(storage_path) if storage_path is not None else Path("./bif_data")
    try:
        workflow = Workflow(
            storage_path=storage,
            on_progress=on_progress,
            use_wetlands=False,
        )
    except Exception:  # pragma: no cover — defensive
        workflow = None

    # --- Resolve tool classes and instantiate tools for enabled nodes ---
    for node in graph.nodes:
        if node.id in duplicate_node_ids:
            continue
        if not node.enabled:
            disabled.add(node.id)
            continue
        metadata = registry.get_tool(node.tool_name)
        if metadata is None:
            errors.append(
                GraphValidationError(
                    type="missing_tool",
                    detail=f"Tool '{node.tool_name}' not found in registry",
                    node=node.id,
                )
            )
            continue
        try:
            tool_class = registry.get_tool_class(node.tool_name)
        except Exception as exc:  # pragma: no cover — defensive
            tool_class = None
            errors.append(
                GraphValidationError(
                    type="missing_package",
                    detail=(
                        f"Failed to load package "
                        f"'{metadata.package}=={metadata.package_version}': {exc}"
                    ),
                    node=node.id,
                )
            )
            continue
        if tool_class is None:
            errors.append(
                GraphValidationError(
                    type="missing_package",
                    detail=(
                        f"Package '{metadata.package}=={metadata.package_version}'"
                        f" is not installed"
                    ),
                    node=node.id,
                )
            )
            continue
        tool_classes[node.id] = tool_class
        try:
            tool_instances[node.id] = tool_class()
        except Exception as exc:
            errors.append(
                GraphValidationError(
                    type="missing_tool",
                    detail=f"Failed to instantiate tool '{node.tool_name}': {exc}",
                    node=node.id,
                )
            )
            continue

    # --- Partition edges by kind (and filter to build-ready nodes) ---
    buildable_ids = set(tool_instances.keys())

    positional_by_target: dict[str, list[PositionalEdge]] = {}
    column_edges: list[ColumnRefEdge] = []
    for edge in graph.edges:
        if edge.source_node not in buildable_ids or edge.target_node not in buildable_ids:
            continue
        if isinstance(edge, PositionalEdge):
            positional_by_target.setdefault(edge.target_node, []).append(edge)
        else:
            column_edges.append(edge)

    # --- Determine build order (best-effort; cycles fall back to input order) ---
    from graphlib import CycleError, TopologicalSorter

    dep_graph: dict[str, set[str]] = {nid: set() for nid in buildable_ids}
    for edge in graph.edges:
        if edge.source_node in buildable_ids and edge.target_node in buildable_ids:
            dep_graph[edge.target_node].add(edge.source_node)

    try:
        build_order = list(TopologicalSorter(dep_graph).static_order())
    except CycleError:
        # Cycles will be reported by the validator; for construction we just
        # process nodes in the order they appear and skip edges whose source
        # hasn't been constructed yet.
        build_order = [n.id for n in graph.nodes if n.id in buildable_ids]

    node_states_by_id = {n.id: n for n in graph.nodes}

    # --- Build library Node objects ---
    if workflow is not None:
        with workflow:
            for node_id in build_order:
                node_state = node_states_by_id[node_id]
                tool_instance = tool_instances[node_id]

                kwargs: dict[str, Any] = {}
                positional_args: list[Any] = []

                # Column ref edges: target_input = upstream[source_output]
                for edge in column_edges:
                    if edge.target_node != node_id:
                        continue
                    upstream = node_map.get(edge.source_node)
                    if upstream is None:
                        continue
                    kwargs[edge.target_input] = ColumnRef(
                        node=upstream, column=edge.source_output
                    )

                # Positional edges: sort by index and normalise to 0..N-1
                if node_id in positional_by_target:
                    sorted_edges = sorted(
                        positional_by_target[node_id],
                        key=lambda e: e.positional_index,
                    )
                    for edge in sorted_edges:
                        upstream = node_map.get(edge.source_node)
                        if upstream is not None:
                            positional_args.append(upstream)

                # Constant parameters (do not overwrite connected inputs)
                for key, value in node_state.parameters.items():
                    if key not in kwargs:
                        kwargs[key] = value

                try:
                    lib_node = tool_instance(
                        *positional_args, name=node_state.id, **kwargs
                    )
                    node_map[node_state.id] = lib_node
                except Exception as exc:
                    # Type-mismatch (BindingError) and missing-required-input
                    # errors are raised by the library during node construction.
                    # The validator detects these independently and surfaces
                    # them as ``type_incompatible`` / ``missing_connection`` /
                    # ``parameter_invalid`` errors — no need to duplicate here.
                    from bioimageflow.node import BindingError

                    if isinstance(exc, BindingError):
                        continue
                    errors.append(
                        GraphValidationError(
                            type="parameter_invalid",
                            detail=(
                                f"Failed to construct node '{node_state.id}': {exc}"
                            ),
                            node=node_state.id,
                        )
                    )
                    continue

    return GraphBuildResult(
        workflow=workflow,
        node_map=node_map,
        errors=errors,
        disabled_node_ids=disabled,
        tool_classes=tool_classes,
        tool_instances=tool_instances,
    )
