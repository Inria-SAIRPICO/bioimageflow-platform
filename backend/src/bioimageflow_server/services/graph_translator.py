"""Translator between the platform's ``GraphState`` and the library's
serialization dict format accepted by :meth:`bioimageflow.Workflow.from_dict`.

Pre-translation structural errors (duplicate IDs, dangling edges,
unknown/unresolvable tools) are emitted as
:class:`GraphValidationError` before the dict is handed to the library.
Domain-level checks (cycle, type compatibility, missing required input,
constant validation) are the library's responsibility.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from bioimageflow import serialize_constant

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
    PositionalEdge,
)
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.models.workflow import MissingPackage, MissingTool
from bioimageflow_server.services.tool_registry import ToolRegistryService

try:
    from bioimageflow.validation import deserialize_constant as _lib_deserialize_constant
except ImportError:  # pragma: no cover - depends on library version
    _lib_deserialize_constant = None

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings


# Key used for positional edges in the library wire format.
POSITIONAL_KEY = "__positional__"

# Library has no native "no limit" for max_executions; map the GUI's
# ``None`` (unlimited) to a very large integer at translation time.
# Documented in plan §"Cross-Plan Notes #8".
_UNLIMITED_MAX_EXECUTIONS = 2**31 - 1


@dataclass
class TranslationResult:
    """Output of :func:`graph_state_to_lib_dict`.

    ``lib_dict`` is the serialized dict ready to feed to
    :meth:`bioimageflow.Workflow.from_dict`.
    """

    lib_dict: dict[str, Any]
    errors: list[GraphValidationError] = field(default_factory=list)


def _deserialize_constant_envelope(value: Any) -> Any:
    """Reverse the library constant envelope when the current library supports it."""
    if _lib_deserialize_constant is not None:
        try:
            return _lib_deserialize_constant(value)
        except Exception:
            pass

    if not isinstance(value, dict):
        return value

    for key in ("value", "data"):
        if key in value and len(value) <= 3:
            return value[key]

    return value


def _extract_gui_section(graph: GraphState) -> dict[str, Any]:
    return {
        "nodes": {
            node.id: {
                "position": list(node.position),
                "collapsed": node.collapsed,
                "resources": node.resources,
                "output_templates": node.output_templates,
            }
            for node in graph.nodes
        }
    }


def _gui_node(gui_data: dict[str, Any] | None, node_id: str) -> dict[str, Any]:
    if not isinstance(gui_data, dict):
        return {}
    nodes = gui_data.get("nodes", {})
    if not isinstance(nodes, dict):
        return {}
    value = nodes.get(node_id, {})
    return value if isinstance(value, dict) else {}


def graph_state_to_persisted_sections(
    graph: GraphState,
    registry: ToolRegistryService,
    *,
    storage_path: Path | None = None,
    engine: str = "sequential",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[GraphValidationError]]:
    """Return canonical graph, derived workflow, GUI section, and translation errors."""
    result = graph_state_to_lib_dict(
        graph,
        registry,
        storage_path=storage_path,
        engine=engine,
    )
    return (
        graph.model_dump(mode="json"),
        result.lib_dict,
        _extract_gui_section(graph),
        result.errors,
    )


def lib_dict_to_graph_state(
    workflow_data: dict[str, Any],
    gui_data: dict[str, Any] | None = None,
) -> GraphState:
    """Convert a persisted library workflow dict into frontend ``GraphState``."""
    nodes: list[NodeState] = []
    node_names: set[str] = set()
    for raw_node in workflow_data.get("nodes", []):
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get("name") or raw_node.get("id") or "")
        if not node_id:
            continue
        node_names.add(node_id)
        gui_node = _gui_node(gui_data, node_id)
        raw_position = gui_node.get("position", (0, 0))
        if isinstance(raw_position, (list, tuple)) and len(raw_position) >= 2:
            position = (float(raw_position[0]), float(raw_position[1]))
        else:
            position = (0.0, 0.0)
        constants = raw_node.get("constants", {})
        parameters = {
            str(key): _deserialize_constant_envelope(value)
            for key, value in constants.items()
        } if isinstance(constants, dict) else {}
        nodes.append(
            NodeState(
                id=node_id,
                name=str(raw_node.get("display_name") or node_id),
                tool_name=str(raw_node.get("tool_class") or raw_node.get("tool_name") or node_id),
                position=position,
                parameters=parameters,
                resources=cast(dict[str, Any], gui_node.get("resources", {})),
                output_templates=cast(
                    dict[str, str],
                    gui_node.get("output_templates", {}),
                ),
                enabled=bool(raw_node.get("enabled", True)),
                collapsed=bool(gui_node.get("collapsed", False)),
            )
        )

    edges: list[ColumnRefEdge | PositionalEdge] = []
    positional_pairs: set[tuple[str, str, int]] = set()
    positional_index_by_target: dict[str, int] = {}
    for index, raw_edge in enumerate(workflow_data.get("edges", [])):
        if not isinstance(raw_edge, dict):
            continue
        source = str(raw_edge.get("from") or raw_edge.get("source_node") or "")
        target = str(raw_edge.get("to") or raw_edge.get("target_node") or "")
        if not source or not target:
            continue
        edge_id = str(raw_edge.get("id") or f"edge_{index}")
        column = raw_edge.get("column")
        field_name = raw_edge.get("field")
        if column == POSITIONAL_KEY and field_name == POSITIONAL_KEY:
            positional_index = positional_index_by_target.get(target, 0)
            positional_index_by_target[target] = positional_index + 1
            positional_pairs.add((source, target, positional_index))
            edges.append(
                PositionalEdge(
                    id=edge_id,
                    source_node=source,
                    target_node=target,
                    positional_index=positional_index,
                )
            )
        else:
            edges.append(
                ColumnRefEdge(
                    id=edge_id,
                    source_node=source,
                    target_node=target,
                    source_output=str(column or ""),
                    target_input=str(field_name or ""),
                )
            )

    # Older library dicts can carry positional inputs only in node["args"].
    for raw_node in workflow_data.get("nodes", []):
        if not isinstance(raw_node, dict):
            continue
        target = str(raw_node.get("name") or "")
        args = raw_node.get("args", [])
        if not target or not isinstance(args, list):
            continue
        for positional_index, source_raw in enumerate(args):
            source = str(source_raw)
            if (
                not source
                or source not in node_names
                or (source, target, positional_index) in positional_pairs
            ):
                continue
            edges.append(
                PositionalEdge(
                    id=f"{source}__to__{target}__pos_{positional_index}",
                    source_node=source,
                    target_node=target,
                    positional_index=positional_index,
                )
            )

    return GraphState(nodes=nodes, edges=edges)


def rebind_lib_dict_versions(
    workflow_data: dict[str, Any],
    registry: ToolRegistryService,
) -> dict[str, Any]:
    """Return a copy whose tool package versions match the active registry."""
    rebound = deepcopy(workflow_data)
    for node in rebound.get("nodes", []):
        if not isinstance(node, dict):
            continue
        tool_name = str(node.get("tool_class") or node.get("tool_name") or "")
        metadata = registry.get_tool(tool_name) if tool_name else None
        package_name = str(node.get("tool_package") or (metadata.package if metadata else ""))
        if not package_name:
            continue
        package = registry.get_package(package_name)
        version = (
            package.active_version
            if package is not None and package.active_version is not None
            else metadata.package_version if metadata is not None
            else None
        )
        if version is None:
            continue
        node["tool_package"] = package_name
        node["tool_package_version"] = version
    return rebound


def _detect_missing_packages(
    workflow_data: dict[str, Any],
    registry: ToolRegistryService,
) -> list[MissingPackage]:
    missing: dict[tuple[str, str], MissingPackage] = {}
    for node in workflow_data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        package_name = node.get("tool_package")
        required_version = node.get("tool_package_version")
        node_id = str(node.get("name") or "")
        if not isinstance(package_name, str) or not isinstance(required_version, str):
            continue
        package = registry.get_package(package_name)
        installed_versions = package.installed_versions if package is not None else []
        if required_version in installed_versions:
            continue
        key = (package_name, required_version)
        item = missing.setdefault(
            key,
            MissingPackage(
                package_name=package_name,
                required_version=required_version,
                installed_versions=list(installed_versions),
            ),
        )
        if node_id:
            item.affected_nodes.append(node_id)
    return list(missing.values())


def _detect_missing_tools(
    workflow_data: dict[str, Any],
    registry: ToolRegistryService,
) -> list[MissingTool]:
    missing: list[MissingTool] = []
    for node in workflow_data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("name") or "")
        tool_name = str(node.get("tool_class") or node.get("tool_name") or "")
        if not node_id or not tool_name:
            continue
        package_name = node.get("tool_package")
        required_version = node.get("tool_package_version")
        package = registry.get_package(package_name) if isinstance(package_name, str) else None
        installed_versions = package.installed_versions if package is not None else []
        metadata = registry.get_tool(tool_name)
        version_has_tool = True
        if package is not None and isinstance(required_version, str):
            version_has_tool = tool_name in package.tools.get(required_version, [])
        if metadata is not None and version_has_tool:
            continue
        missing.append(
            MissingTool(
                node_id=node_id,
                tool_name=tool_name,
                package_name=package_name if isinstance(package_name, str) else None,
                required_version=(
                    required_version if isinstance(required_version, str) else None
                ),
                installed_versions=list(installed_versions),
            )
        )
    return missing


def graph_state_to_lib_dict(
    graph: GraphState,
    registry: ToolRegistryService,
    *,
    storage_path: Path | None = None,
    engine: str = "sequential",
    settings: "Settings | None" = None,
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

    # Fields that already receive their value from a column_ref edge must
    # not be re-emitted as constants — the library's engine merges
    # constants on top of column bindings, so a leftover constant
    # (commonly a None placeholder kept by the frontend on the disabled
    # parameter widget) would clobber the upstream value.
    connected_inputs_by_target: dict[str, set[str]] = {}
    for edge in column_edges:
        connected_inputs_by_target.setdefault(edge.target_node, set()).add(
            edge.target_input
        )

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

        connected_inputs = connected_inputs_by_target.get(node.id, set())
        for key, value in node.parameters.items():
            if key in connected_inputs:
                continue
            node_dict["constants"][key] = serialize_constant(value)

        nodes_data.append(node_dict)

    # --- Emit edges. ---
    edges_data: list[dict[str, str]] = []
    # Column-ref edges first, keyed by insertion order in the original graph
    # (use the order we collected them in valid_edges for determinism).
    for edge in column_edges:
        edges_data.append(
            {
                "id": edge.id,
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
                    "id": edge.id,
                    "from": edge.source_node,
                    "to": edge.target_node,
                    "column": POSITIONAL_KEY,
                    "field": POSITIONAL_KEY,
                }
            )

    storage_str = str(storage_path) if storage_path is not None else "./bif_data"

    # Cache config: derived from Settings when supplied; otherwise the legacy
    # defaults so callers that don't yet thread Settings through (validators,
    # tests) keep working.
    if settings is not None:
        resolved_engine = settings.execution_engine
        resolved_max_executions = (
            _UNLIMITED_MAX_EXECUTIONS
            if settings.cache_max_executions is None
            else settings.cache_max_executions
        )
        resolved_max_age = settings.cache_max_age
    else:
        resolved_engine = engine
        resolved_max_executions = 0
        resolved_max_age = None

    lib_dict: dict[str, Any] = {
        "nodes": nodes_data,
        "edges": edges_data,
        "config": {
            "storage_path": storage_str,
            "engine": resolved_engine,
            "max_executions": resolved_max_executions,
            "max_age": resolved_max_age,
        },
    }

    return TranslationResult(
        lib_dict=lib_dict,
        errors=errors,
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
    "source_tool_upstream": "source_tool_upstream",
    # ``unknown_tool`` handled specially below — message decides
    # ``missing_tool`` vs ``missing_package``.
}


def lib_validation_error_to_graph_error(
    err: Any,
) -> GraphValidationError:
    """Map a library :class:`bioimageflow.ValidationError` to the platform shape.

    ``err.edge_id`` is read directly — the library now round-trips the
    platform-supplied edge ID through ``from_dict`` / ``to_dict`` and
    copies it onto every ``ValidationError``.
    ``err.path`` (sub-workflow scope) is flattened into the detail
    string — the platform's error shape has no ``path`` field.
    """
    kind = err.kind
    detail = err.message

    if err.path:
        scope = "/".join(err.path)
        detail = f"in sub-workflow '{scope}': {detail}"

    error_type: Literal[
        "cycle_detected",
        "type_incompatible",
        "parameter_invalid",
        "missing_tool",
        "missing_connection",
        "missing_package",
        "invalid_node_id",
        "invalid_edge_id",
        "source_tool_upstream",
    ]
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
        error_type = cast(
            Literal[
                "cycle_detected",
                "type_incompatible",
                "parameter_invalid",
                "missing_tool",
                "missing_connection",
                "missing_package",
                "invalid_node_id",
                "invalid_edge_id",
                "source_tool_upstream",
            ],
            _KIND_TO_TYPE.get(kind, "parameter_invalid"),
        )

    return GraphValidationError(
        type=error_type,
        detail=detail,
        node=err.node,
        field=err.field,
        edge_id=getattr(err, "edge_id", None),
    )
