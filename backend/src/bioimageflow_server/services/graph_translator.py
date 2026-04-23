"""Translator between the platform's ``GraphState`` and the library's
serialization dict format accepted by :meth:`bioimageflow.Workflow.from_dict`.

Pre-translation structural errors (duplicate IDs, dangling edges,
unknown/unresolvable tools) are emitted as
:class:`GraphValidationError` before the dict is handed to the library.
Domain-level checks (cycle, type compatibility, missing required input,
constant validation) are the library's responsibility.
"""

from __future__ import annotations

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


# Key used for positional edges in ``edge_id_by_key``.
POSITIONAL_KEY = "__positional__"


def _serialize_constant(value: Any) -> dict[str, Any]:
    """Tag ``value`` with ``__type__`` metadata for lossless round-trip.

    Mirrors :func:`bioimageflow.workflow._serialize_constant`. Duplicated
    here so the platform does not depend on a private library symbol.
    """
    if isinstance(value, bool):
        return {"__type__": "bool", "value": value}
    if isinstance(value, int):
        return {"__type__": "int", "value": value}
    if isinstance(value, float):
        return {"__type__": "float", "value": value}
    if isinstance(value, (list, tuple)):
        return {"__type__": type(value).__name__, "value": list(value)}
    return {"__type__": "str", "value": str(value)}


@dataclass
class TranslationResult:
    """Output of :func:`graph_state_to_lib_dict`.

    ``lib_dict`` is the serialized dict ready to feed to
    :meth:`bioimageflow.Workflow.from_dict`.

    ``edge_id_by_key`` maps ``(source_node, target_node, field)`` to the
    frontend-generated edge ID. The library's ``ValidationError.edge``
    uses this triple; the platform's :class:`GraphValidationError.edge_id`
    needs the original edge UUID.
    """

    lib_dict: dict[str, Any]
    errors: list[GraphValidationError] = field(default_factory=list)
    edge_id_by_key: dict[tuple[str, str, str], str] = field(default_factory=dict)


def build_edge_id_map(graph: GraphState) -> dict[tuple[str, str, str], str]:
    """Construct the ``(source, target, field) → edge_id`` lookup.

    For positional edges, ``field`` is :data:`POSITIONAL_KEY`. First
    occurrence wins for duplicates (same key, same semantic edge).
    """
    mapping: dict[tuple[str, str, str], str] = {}
    for edge in graph.edges:
        if isinstance(edge, ColumnRefEdge):
            key = (edge.source_node, edge.target_node, edge.target_input)
        else:
            key = (edge.source_node, edge.target_node, POSITIONAL_KEY)
        mapping.setdefault(key, edge.id)
    return mapping


def graph_state_to_lib_dict(
    graph: GraphState,
    registry: ToolRegistryService,
    *,
    storage_path: Path | None = None,
    engine: str = "sequential",
) -> TranslationResult:
    """Translate ``graph`` into the library's serialization dict.

    Detects and records structural errors (duplicate node/edge IDs,
    dangling edge endpoints, unknown/unresolvable tools). Nodes and
    edges that cannot be represented unambiguously are omitted from
    the returned ``lib_dict`` — they are reported via ``errors`` and
    the caller maps them to the HTTP response.
    """
    from bioimageflow.tool_loader import get_tool_package_info

    errors: list[GraphValidationError] = []

    # --- Node IDs: detect duplicates; first occurrence wins. ---
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

    # --- Resolve tools for every unique node (enabled or disabled). ---
    # Disabled nodes still appear in the lib dict so the library can
    # enforce name uniqueness and so downstream references stay valid;
    # their ``enabled`` flag carries the skip semantics.
    tool_info: dict[str, tuple[type, str | None, str | None, str]] = {}
    processed: set[str] = set()
    for node in graph.nodes:
        if node.id in processed:
            continue
        processed.add(node.id)
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
        tool_class = registry.get_tool_class(node.tool_name)
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
        pkg, pkg_ver, canonical_module = get_tool_package_info(tool_class)
        tool_info[node.id] = (tool_class, pkg, pkg_ver, canonical_module)

    # --- Edge IDs: uniqueness and endpoint validity. ---
    seen_edge_ids: set[str] = set()
    valid_node_ids = {n.id for n in graph.nodes} - duplicate_node_ids
    valid_edges: list[ColumnRefEdge | PositionalEdge] = []
    for edge in graph.edges:
        if edge.id in seen_edge_ids:
            errors.append(
                GraphValidationError(
                    type="invalid_edge_id",
                    detail=f"Duplicate edge ID: {edge.id}",
                    edge_id=edge.id,
                )
            )
            continue
        seen_edge_ids.add(edge.id)
        src_known = edge.source_node in valid_node_ids
        dst_known = edge.target_node in valid_node_ids
        if not src_known:
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
        if not dst_known:
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
        if not src_known or not dst_known:
            continue
        # Drop edges whose endpoints are missing from the lib dict
        # (duplicate IDs or unresolved tools).
        if edge.source_node not in tool_info or edge.target_node not in tool_info:
            continue
        valid_edges.append(edge)

    # --- Build the edge-id reverse lookup (covers ALL edges in GraphState,
    #     not just the ones we emit; library errors may reference dropped
    #     edges via the original IDs in the graph). ---
    edge_id_by_key = build_edge_id_map(graph)

    # --- Sort and re-index positional edges per target. ---
    positional_by_target: dict[str, list[PositionalEdge]] = {}
    column_edges: list[ColumnRefEdge] = []
    for edge in valid_edges:
        if isinstance(edge, PositionalEdge):
            positional_by_target.setdefault(edge.target_node, []).append(edge)
        else:
            column_edges.append(edge)
    for target, pos_edges in positional_by_target.items():
        pos_edges.sort(key=lambda e: e.positional_index)

    # --- Emit nodes. ---
    nodes_data: list[dict[str, Any]] = []
    emitted_ids: set[str] = set()
    for node in graph.nodes:
        if node.id in emitted_ids:
            continue
        if node.id not in tool_info:
            continue
        emitted_ids.add(node.id)

        _, pkg, pkg_ver, canonical_module = tool_info[node.id]
        class_name = tool_info[node.id][0].__name__

        node_dict: dict[str, Any] = {
            "name": node.id,
            "tool_class": class_name,
            "tool_module": canonical_module,
            "constants": {},
            "args": [
                e.source_node for e in positional_by_target.get(node.id, [])
            ],
        }
        if pkg and pkg_ver:
            node_dict["tool_package"] = pkg
            node_dict["tool_package_version"] = pkg_ver
        if not node.enabled:
            node_dict["enabled"] = False

        for key, value in node.parameters.items():
            node_dict["constants"][key] = _serialize_constant(value)

        nodes_data.append(node_dict)

    # --- Emit edges. ---
    edges_data: list[dict[str, str]] = []
    # Column-ref edges first, keyed by insertion order in the original graph
    # (use the order we collected them in valid_edges for determinism).
    for edge in column_edges:
        edges_data.append(
            {
                "from": edge.source_node,
                "to": edge.target_node,
                "column": edge.source_output,
                "field": edge.target_input,
            }
        )
    for target in positional_by_target:
        for edge in positional_by_target[target]:
            edges_data.append(
                {
                    "from": edge.source_node,
                    "to": edge.target_node,
                    "column": POSITIONAL_KEY,
                    "field": POSITIONAL_KEY,
                }
            )

    storage_str = str(storage_path) if storage_path is not None else "./bif_data"
    lib_dict: dict[str, Any] = {
        "nodes": nodes_data,
        "edges": edges_data,
        "config": {
            "storage_path": storage_str,
            "engine": engine,
            "max_executions": 0,
            "max_age": None,
        },
    }

    return TranslationResult(
        lib_dict=lib_dict,
        errors=errors,
        edge_id_by_key=edge_id_by_key,
    )


# ---- Library → platform error mapping -------------------------------------


_KIND_TO_TYPE = {
    "cycle": "cycle_detected",
    "type_mismatch": "type_incompatible",
    "column_not_found": "type_incompatible",
    "missing_input": "missing_connection",
    "unknown_input": "parameter_invalid",
    "parameter_invalid": "parameter_invalid",
    "duplicate_name": "invalid_node_id",
    "construction_failed": "parameter_invalid",
    # ``unknown_tool`` handled specially below — message decides
    # ``missing_tool`` vs ``missing_package``.
}


def lib_validation_error_to_graph_error(
    err: Any,
    edge_id_by_key: dict[tuple[str, str, str], str],
) -> GraphValidationError:
    """Map a library :class:`bioimageflow.ValidationError` to the platform shape.

    ``err.edge`` (``(from, to, field)``) is looked up in
    ``edge_id_by_key`` to recover the frontend-generated edge UUID.
    ``err.path`` (sub-workflow scope) is flattened into the detail
    string — the platform's error shape has no ``path`` field.
    """
    kind = err.kind
    detail = err.message

    if err.path:
        scope = "/".join(err.path)
        detail = f"in sub-workflow '{scope}': {detail}"

    if kind == "unknown_tool":
        # Heuristic: if the message mentions the package is not installed
        # / cannot be loaded, surface as ``missing_package``; else
        # ``missing_tool``. Both map to the same user-visible category on
        # the frontend, but preserving the distinction helps debugging.
        lowered = err.message.lower()
        if "package" in lowered or "load" in lowered or "install" in lowered:
            error_type = "missing_package"
        else:
            error_type = "missing_tool"
    else:
        error_type = _KIND_TO_TYPE.get(kind, "parameter_invalid")

    edge_id: str | None = None
    if err.edge is not None:
        edge_id = edge_id_by_key.get(tuple(err.edge))

    return GraphValidationError(
        type=error_type,
        detail=detail,
        node=err.node,
        field=err.field,
        edge_id=edge_id,
    )
