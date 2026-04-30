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
from bioimageflow_server.models.workflow import (
    LocalToolReference,
    MissingPackage,
    MissingTool,
    RequiredPackage,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

try:
    from bioimageflow.validation import deserialize_constant as _lib_deserialize_constant
except ImportError:  # pragma: no cover - depends on library version
    _lib_deserialize_constant = None

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings


# Key used for positional edges in the library wire format.
POSITIONAL_KEY = "__positional__"
SUB_WORKFLOW_TOOL_NAME = "__sub_workflow__"

# Library has no native "no limit" for max_executions; map the GUI's
# ``None`` (unlimited) to a very large integer at translation time.
# Documented in plan §"Cross-Plan Notes #8".
_UNLIMITED_MAX_EXECUTIONS = 2**31 - 1
_SUB_WORKFLOW_TOOL_NAMES = {"__sub_workflow__"}


@dataclass
class TranslationResult:
    """Output of :func:`graph_state_to_lib_dict`.

    ``lib_dict`` is the serialized dict ready to feed to
    :meth:`bioimageflow.Workflow.from_dict`.
    """

    lib_dict: dict[str, Any]
    errors: list[GraphValidationError] = field(default_factory=list)


def _scoped_node_id(scope: tuple[str, ...], node_id: str) -> str:
    return "/".join((*scope, node_id)) if scope else node_id


def _is_editable_sub_workflow(node: NodeState) -> bool:
    return node.tool_name == SUB_WORKFLOW_TOOL_NAME and node.sub_workflow is not None


def _ensure_sub_workflow_proxy_validation_compat() -> None:
    """Patch older library proxy tools so config sub-workflows validate cleanly."""
    try:
        from bioimageflow.sub_workflow import _ProxyTool
        from bioimageflow_core.tool import IOModel
    except ImportError:  # pragma: no cover - depends on library version
        return

    if not hasattr(_ProxyTool, "Inputs"):
        _ProxyTool.Inputs = IOModel


def _schema_for_config(schema: dict[str, Any] | None, default: Any = None) -> dict[str, Any]:
    config = dict(schema or {})
    if "type" not in config:
        # The library config model requires a concrete type. GUI-created pins
        # should carry schema snapshots; this fallback keeps older drafts
        # loadable until the publish UI backfills richer schemas.
        config["type"] = "str"
    if default is not None and "default" not in config:
        config["default"] = default
    return config


def _detect_duplicate_names(
    values: list[str],
) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


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


def _graph_state_from_sub_workflow_config(
    config: dict[str, Any],
) -> tuple[GraphState, list[Any], list[Any]]:
    from bioimageflow_server.models.graph import PublishedInput, PublishedOutput

    published_inputs: list[PublishedInput] = []
    published_outputs: list[PublishedOutput] = []

    input_refs: dict[str, tuple[str, str]] = {}
    nodes: list[NodeState] = []
    edges: list[ColumnRefEdge | PositionalEdge] = []
    edge_index = 0

    for raw_node in config.get("nodes", []):
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get("name") or raw_node.get("id") or "")
        if not node_id:
            continue
        raw_inputs = raw_node.get("inputs", {})
        inputs = raw_inputs if isinstance(raw_inputs, dict) else {}
        parameters: dict[str, Any] = {}
        for input_field, value in inputs.items():
            if isinstance(value, dict) and "from_input" in value:
                input_refs[str(value["from_input"])] = (node_id, str(input_field))
                continue
            if isinstance(value, dict) and "from_node" in value:
                edges.append(
                    ColumnRefEdge(
                        id=(
                            f"{value['from_node']}__to__"
                            f"{node_id}__{input_field}_{edge_index}"
                        ),
                        source_node=str(value["from_node"]),
                        target_node=node_id,
                        source_output=str(value.get("column", "")),
                        target_input=str(input_field),
                    )
                )
                edge_index += 1
                continue
            parameters[str(input_field)] = value

        if raw_node.get("type") == "sub_workflow" and isinstance(
            raw_node.get("config"), dict
        ):
            nested_graph, nested_inputs, nested_outputs = (
                _graph_state_from_sub_workflow_config(raw_node["config"])
            )
            nodes.append(
                NodeState(
                    id=node_id,
                    name=str(raw_node.get("display_name") or node_id),
                    tool_name=SUB_WORKFLOW_TOOL_NAME,
                    position=(0, 0),
                    parameters=parameters,
                    sub_workflow=nested_graph,
                    published_inputs=nested_inputs,
                    published_outputs=nested_outputs,
                    enabled=bool(raw_node.get("enabled", True)),
                )
            )
        else:
            nodes.append(
                NodeState(
                    id=node_id,
                    name=str(raw_node.get("display_name") or node_id),
                    tool_name=str(
                        raw_node.get("tool_class")
                        or raw_node.get("tool_name")
                        or node_id
                    ),
                    position=(0, 0),
                    parameters=parameters,
                    output_templates=cast(
                        dict[str, str], raw_node.get("output_templates", {})
                    ),
                    enabled=bool(raw_node.get("enabled", True)),
                )
            )

    inputs_config = config.get("inputs", {})
    if isinstance(inputs_config, dict):
        for name, schema in inputs_config.items():
            field_schema = schema if isinstance(schema, dict) else {}
            internal_node_id, internal_field = input_refs.get(str(name), ("", str(name)))
            published_inputs.append(
                PublishedInput(
                    name=str(name),
                    internal_node_id=internal_node_id,
                    internal_field=internal_field,
                    kind="input",
                    schema=cast(dict[str, Any], field_schema),
                    default=field_schema.get("default"),
                )
            )

    outputs_config = config.get("outputs", {})
    output_mapping = config.get("output_mapping", {})
    if isinstance(outputs_config, dict):
        for name, schema in outputs_config.items():
            field_schema = schema if isinstance(schema, dict) else {}
            raw_mapping = (
                output_mapping.get(name, {}) if isinstance(output_mapping, dict) else {}
            )
            mapping = raw_mapping if isinstance(raw_mapping, dict) else {}
            published_outputs.append(
                PublishedOutput(
                    name=str(name),
                    internal_node_id=str(mapping.get("from_node") or ""),
                    internal_output=str(mapping.get("column") or name),
                    schema=cast(dict[str, Any], field_schema),
                )
            )

    return GraphState(nodes=nodes, edges=edges), published_inputs, published_outputs


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
        parameters = (
            {str(key): _deserialize_constant_envelope(value) for key, value in constants.items()}
            if isinstance(constants, dict)
            else {}
        )

        sub_workflow = None
        published_inputs: list[Any] = []
        published_outputs: list[Any] = []
        readonly_reason = None
        tool_name = str(raw_node.get("tool_class") or raw_node.get("tool_name") or node_id)
        if raw_node.get("type") == "sub_workflow":
            tool_name = SUB_WORKFLOW_TOOL_NAME
            config = raw_node.get("config")
            if raw_node.get("sub_workflow_type") == "config" and isinstance(config, dict):
                sub_workflow, published_inputs, published_outputs = (
                    _graph_state_from_sub_workflow_config(config)
                )
            else:
                readonly_reason = (
                    "Class-based sub-workflow has no editable nested GraphState."
                )
                from bioimageflow_server.models.graph import (
                    PublishedInput,
                    PublishedOutput,
                )
                raw_inputs = raw_node.get("inputs", {})
                if isinstance(raw_inputs, dict):
                    published_inputs = [
                        PublishedInput(
                            name=str(name),
                            internal_node_id="",
                            internal_field=str(name),
                            kind="input",
                            schema=cast(dict[str, Any], schema)
                            if isinstance(schema, dict)
                            else None,
                        )
                        for name, schema in raw_inputs.items()
                    ]
                raw_outputs = raw_node.get("outputs", {})
                if isinstance(raw_outputs, dict):
                    published_outputs = [
                        PublishedOutput(
                            name=str(name),
                            internal_node_id="",
                            internal_output=str(name),
                            schema=cast(dict[str, Any], schema)
                            if isinstance(schema, dict)
                            else None,
                        )
                        for name, schema in raw_outputs.items()
                    ]
        nodes.append(
            NodeState(
                id=node_id,
                name=str(raw_node.get("display_name") or node_id),
                tool_name=tool_name,
                position=position,
                parameters=parameters,
                resources=cast(dict[str, Any], gui_node.get("resources", {})),
                output_templates=cast(
                    dict[str, str],
                    gui_node.get(
                        "output_templates",
                        raw_node.get("output_templates", {}),
                    ),
                ),
                enabled=bool(raw_node.get("enabled", True)),
                collapsed=bool(gui_node.get("collapsed", False)),
                sub_workflow=sub_workflow,
                published_inputs=published_inputs,
                published_outputs=published_outputs,
                sub_workflow_readonly_reason=readonly_reason,
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
            else metadata.package_version
            if metadata is not None
            else None
        )
        if version is None:
            continue
        node["tool_package"] = package_name
        node["tool_package_version"] = version
    return rebound


def _iter_workflow_nodes(workflow_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return workflow nodes, including tolerant nested sub-workflow payloads."""
    nodes: list[dict[str, Any]] = []
    seen_containers: set[int] = set()

    def visit(container: dict[str, Any]) -> None:
        container_id = id(container)
        if container_id in seen_containers:
            return
        seen_containers.add(container_id)
        raw_nodes = container.get("nodes", [])
        if isinstance(raw_nodes, list):
            for raw_node in raw_nodes:
                if not isinstance(raw_node, dict):
                    continue
                nodes.append(raw_node)
                for key in ("sub_workflow", "workflow", "library", "config"):
                    nested = raw_node.get(key)
                    if isinstance(nested, dict):
                        visit(nested)
                for nested in raw_node.values():
                    if (
                        isinstance(nested, dict)
                        and nested.get("nodes") is not raw_nodes
                        and isinstance(nested.get("nodes"), list)
                    ):
                        visit(nested)

        for key in ("sub_workflow", "workflow", "library", "config"):
            nested = container.get(key)
            if isinstance(nested, dict):
                visit(nested)

    visit(workflow_data)
    return nodes


def collect_required_packages(
    workflow_data: dict[str, Any],
    registry: ToolRegistryService,
) -> tuple[list[RequiredPackage], list[LocalToolReference]]:
    """Collect package requirements and non-portable local tool references."""
    packages: dict[tuple[str, str], RequiredPackage] = {}
    local_tools: dict[str, list[str]] = {}

    for node in _iter_workflow_nodes(workflow_data):
        tool_name = str(node.get("tool_class") or node.get("tool_name") or "")
        node_id = str(node.get("id") or node.get("name") or "")
        package_name = node.get("tool_package")
        package_version = node.get("tool_package_version")

        if isinstance(package_name, str) and isinstance(package_version, str):
            packages.setdefault(
                (package_name, package_version),
                RequiredPackage(name=package_name, version=package_version),
            )
            continue

        metadata = registry.get_tool(tool_name) if tool_name else None
        if metadata is not None:
            packages.setdefault(
                (metadata.package, metadata.package_version),
                RequiredPackage(
                    name=metadata.package,
                    version=metadata.package_version,
                ),
            )
            continue

        if tool_name and tool_name not in _SUB_WORKFLOW_TOOL_NAMES:
            local_tools.setdefault(tool_name, [])
            if node_id:
                local_tools[tool_name].append(node_id)

    return (
        [packages[key] for key in sorted(packages)],
        [
            LocalToolReference(tool_name=tool_name, node_ids=node_ids)
            for tool_name, node_ids in sorted(local_tools.items())
        ],
    )


def _detect_missing_packages(
    workflow_data: dict[str, Any],
    registry: ToolRegistryService,
) -> list[MissingPackage]:
    missing: dict[tuple[str, str], MissingPackage] = {}
    for node in _iter_workflow_nodes(workflow_data):
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
    for node in _iter_workflow_nodes(workflow_data):
        node_id = str(node.get("name") or "")
        tool_name = str(node.get("tool_class") or node.get("tool_name") or "")
        if not node_id or not tool_name:
            continue
        if tool_name in _SUB_WORKFLOW_TOOL_NAMES:
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
                required_version=(required_version if isinstance(required_version, str) else None),
                installed_versions=list(installed_versions),
            )
        )
    return missing


def _resolve_graph_nodes(
    graph: GraphState,
    registry: ToolRegistryService,
    errors: list[GraphValidationError],
    *,
    scope: tuple[str, ...] = (),
) -> tuple[
    dict[str, tuple[type, str | None, str | None, str]],
    set[str],
]:
    """Resolve non-sub-workflow tools and report duplicate node IDs."""
    from bioimageflow.tool_loader import get_tool_package_info

    seen_node_ids: set[str] = set()
    duplicate_node_ids: set[str] = set()
    for node in graph.nodes:
        if node.id in seen_node_ids:
            duplicate_node_ids.add(node.id)
            errors.append(
                GraphValidationError(
                    type="invalid_node_id",
                    detail=f"Duplicate node ID: {_scoped_node_id(scope, node.id)}",
                    node=_scoped_node_id(scope, node.id),
                )
            )
        seen_node_ids.add(node.id)

    tool_info: dict[str, tuple[type, str | None, str | None, str]] = {}
    processed: set[str] = set()
    for node in graph.nodes:
        if node.id in processed:
            continue
        processed.add(node.id)
        if _is_editable_sub_workflow(node):
            continue
        metadata = registry.get_tool(node.tool_name)
        if metadata is None:
            errors.append(
                GraphValidationError(
                    type="missing_tool",
                    detail=f"Tool '{node.tool_name}' not found in registry",
                    node=_scoped_node_id(scope, node.id),
                )
            )
            continue
        tool_class = registry.get_tool_class(node.tool_name)
        if tool_class is None:
            errors.append(
                GraphValidationError(
                    type="missing_package",
                    detail=(
                        f"Package '{metadata.package}=={metadata.package_version}' is not installed"
                    ),
                    node=_scoped_node_id(scope, node.id),
                )
            )
            continue
        pkg, pkg_ver, canonical_module = get_tool_package_info(tool_class)
        tool_info[node.id] = (tool_class, pkg, pkg_ver, canonical_module)

    return tool_info, duplicate_node_ids


def _valid_graph_edges(
    graph: GraphState,
    errors: list[GraphValidationError],
    translatable_node_ids: set[str],
    duplicate_node_ids: set[str],
    *,
    scope: tuple[str, ...] = (),
) -> list[ColumnRefEdge | PositionalEdge]:
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
                        f"{_scoped_node_id(scope, edge.source_node)}"
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
                        f"{_scoped_node_id(scope, edge.target_node)}"
                    ),
                    edge_id=edge.id,
                )
            )
        if not src_known or not dst_known:
            continue
        if (
            edge.source_node not in translatable_node_ids
            or edge.target_node not in translatable_node_ids
        ):
            continue
        valid_edges.append(edge)
    return valid_edges


def _split_edges(
    valid_edges: list[ColumnRefEdge | PositionalEdge],
) -> tuple[dict[str, list[PositionalEdge]], list[ColumnRefEdge]]:
    positional_by_target: dict[str, list[PositionalEdge]] = {}
    column_edges: list[ColumnRefEdge] = []
    for edge in valid_edges:
        if isinstance(edge, PositionalEdge):
            positional_by_target.setdefault(edge.target_node, []).append(edge)
        else:
            column_edges.append(edge)
    for pos_edges in positional_by_target.values():
        pos_edges.sort(key=lambda e: e.positional_index)
    return positional_by_target, column_edges


def _ordered_sub_workflow_nodes(
    graph: GraphState,
    column_edges: list[ColumnRefEdge],
    translatable_node_ids: set[str],
) -> list[NodeState]:
    """Return internal nodes in dependency order, falling back to graph order on cycles."""
    first_by_id: dict[str, NodeState] = {}
    original_order: list[str] = []
    for node in graph.nodes:
        if node.id in first_by_id or node.id not in translatable_node_ids:
            continue
        first_by_id[node.id] = node
        original_order.append(node.id)

    dependencies: dict[str, set[str]] = {node_id: set() for node_id in original_order}
    dependents: dict[str, set[str]] = {node_id: set() for node_id in original_order}
    for edge in column_edges:
        if edge.source_node not in dependencies or edge.target_node not in dependencies:
            continue
        dependencies[edge.target_node].add(edge.source_node)
        dependents[edge.source_node].add(edge.target_node)

    ready = [node_id for node_id in original_order if not dependencies[node_id]]
    ordered_ids: list[str] = []
    while ready:
        node_id = ready.pop(0)
        ordered_ids.append(node_id)
        for dependent in original_order:
            if dependent not in dependents[node_id]:
                continue
            dependencies[dependent].discard(node_id)
            if not dependencies[dependent] and dependent not in ordered_ids and dependent not in ready:
                ready.append(dependent)

    if len(ordered_ids) != len(original_order):
        return [first_by_id[node_id] for node_id in original_order]
    return [first_by_id[node_id] for node_id in ordered_ids]


def _sub_workflow_config(
    node: NodeState,
    registry: ToolRegistryService,
    errors: list[GraphValidationError],
    *,
    scope: tuple[str, ...],
) -> dict[str, Any]:
    if node.sub_workflow is None:
        return {
            "name": node.id,
            "inputs": {},
            "outputs": {},
            "nodes": [],
            "output_mapping": {},
        }

    names = [published.name for published in node.published_inputs]
    names.extend(published.name for published in node.published_outputs)
    for duplicate in _detect_duplicate_names(names):
        errors.append(
            GraphValidationError(
                type="parameter_invalid",
                detail=f"Duplicate published pin name: {duplicate}",
                node=_scoped_node_id(scope[:-1], node.id),
                field=duplicate,
            )
        )

    internal_node_ids = {inner.id for inner in node.sub_workflow.nodes}
    for published in node.published_outputs:
        if published.internal_node_id not in internal_node_ids:
            errors.append(
                GraphValidationError(
                    type="parameter_invalid",
                    detail=(
                        f"Published output '{published.name}' targets unknown "
                        f"internal node '{published.internal_node_id}'"
                    ),
                    node=_scoped_node_id(scope[:-1], node.id),
                    field=published.name,
                )
            )

    return {
        "name": node.id,
        "inputs": {
            published.name: _schema_for_config(published.schema_, published.default)
            for published in node.published_inputs
        },
        "outputs": {
            published.name: _schema_for_config(published.schema_)
            for published in node.published_outputs
        },
        "nodes": _graph_state_to_sub_workflow_config_nodes(
            node.sub_workflow,
            registry,
            errors,
            scope=scope,
            published_inputs=node.published_inputs,
        ),
        "output_mapping": {
            published.name: {
                "from_node": published.internal_node_id,
                "column": published.internal_output,
            }
            for published in node.published_outputs
        },
    }


def _graph_state_to_sub_workflow_config_nodes(
    graph: GraphState,
    registry: ToolRegistryService,
    errors: list[GraphValidationError],
    *,
    scope: tuple[str, ...],
    published_inputs: list[Any],
) -> list[dict[str, Any]]:
    tool_info, duplicate_node_ids = _resolve_graph_nodes(
        graph, registry, errors, scope=scope
    )
    sub_workflow_ids = {n.id for n in graph.nodes if _is_editable_sub_workflow(n)}
    translatable_node_ids = set(tool_info) | sub_workflow_ids
    valid_edges = _valid_graph_edges(
        graph,
        errors,
        translatable_node_ids,
        duplicate_node_ids,
        scope=scope,
    )
    positional_by_target, column_edges = _split_edges(valid_edges)
    for pos_edges in positional_by_target.values():
        for edge in pos_edges:
            errors.append(
                GraphValidationError(
                    type="parameter_invalid",
                    detail=(
                        "Positional edges inside sub-workflows cannot be "
                        "represented in library config inputs"
                    ),
                    node=_scoped_node_id(scope, edge.target_node),
                    edge_id=edge.id,
                )
            )

    connected_inputs_by_target: dict[str, set[str]] = {}
    refs_by_target: dict[str, dict[str, dict[str, str]]] = {}
    for edge in column_edges:
        connected_inputs_by_target.setdefault(edge.target_node, set()).add(
            edge.target_input
        )
        refs_by_target.setdefault(edge.target_node, {})[edge.target_input] = {
            "from_node": edge.source_node,
            "column": edge.source_output,
        }

    published_by_target: dict[str, dict[str, str]] = {}
    for published in published_inputs:
        if published.internal_node_id not in translatable_node_ids:
            errors.append(
                GraphValidationError(
                    type="parameter_invalid",
                    detail=(
                        f"Published input '{published.name}' targets unknown "
                        f"internal node '{published.internal_node_id}'"
                    ),
                    node=_scoped_node_id(scope[:-1], scope[-1]) if scope else None,
                    field=published.name,
                )
            )
            continue
        published_by_target.setdefault(published.internal_node_id, {})[
            published.internal_field
        ] = published.name

    nodes_data: list[dict[str, Any]] = []
    emitted_ids: set[str] = set()
    for inner in _ordered_sub_workflow_nodes(graph, column_edges, translatable_node_ids):
        if inner.id in emitted_ids:
            continue
        if inner.id not in translatable_node_ids:
            continue
        emitted_ids.add(inner.id)

        inputs: dict[str, Any] = {}
        connected_inputs = connected_inputs_by_target.get(inner.id, set())
        published_fields = set(published_by_target.get(inner.id, {}))
        for key, value in inner.parameters.items():
            if key in connected_inputs or key in published_fields:
                continue
            inputs[key] = value
        inputs.update(refs_by_target.get(inner.id, {}))
        for input_field, published_name in published_by_target.get(inner.id, {}).items():
            inputs[input_field] = {"from_input": published_name}

        if _is_editable_sub_workflow(inner):
            node_dict = {
                "name": inner.id,
                "type": "sub_workflow",
                "sub_workflow_type": "config",
                "config": _sub_workflow_config(
                    inner,
                    registry,
                    errors,
                    scope=(*scope, inner.id),
                ),
                "inputs": inputs,
            }
        else:
            _, pkg, pkg_ver, canonical_module = tool_info[inner.id]
            node_dict = {
                "name": inner.id,
                "tool_class": tool_info[inner.id][0].__name__,
                "tool_module": canonical_module,
                "inputs": inputs,
            }
            if pkg and pkg_ver:
                node_dict["tool_package"] = pkg
                node_dict["tool_package_version"] = pkg_ver
        if not inner.enabled:
            node_dict["enabled"] = False
        nodes_data.append(node_dict)

    return nodes_data


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
    _ensure_sub_workflow_proxy_validation_compat()
    errors: list[GraphValidationError] = []
    tool_info, duplicate_node_ids = _resolve_graph_nodes(graph, registry, errors)
    sub_workflow_ids = {n.id for n in graph.nodes if _is_editable_sub_workflow(n)}
    translatable_node_ids = set(tool_info) | sub_workflow_ids
    valid_edges = _valid_graph_edges(
        graph,
        errors,
        translatable_node_ids,
        duplicate_node_ids,
    )
    positional_by_target, column_edges = _split_edges(valid_edges)

    # Fields that already receive their value from a column_ref edge must
    # not be re-emitted as constants — the library's engine merges
    # constants on top of column bindings, so a leftover constant
    # (commonly a None placeholder kept by the frontend on the disabled
    # parameter widget) would clobber the upstream value.
    connected_inputs_by_target: dict[str, set[str]] = {}
    for edge in column_edges:
        connected_inputs_by_target.setdefault(edge.target_node, set()).add(edge.target_input)

    # --- Emit nodes. ---
    nodes_data: list[dict[str, Any]] = []
    emitted_ids: set[str] = set()
    for node in graph.nodes:
        if node.id in emitted_ids:
            continue
        if node.id not in translatable_node_ids:
            continue
        emitted_ids.add(node.id)

        if _is_editable_sub_workflow(node):
            node_dict = {
                "name": node.id,
                "type": "sub_workflow",
                "sub_workflow_type": "config",
                "config": _sub_workflow_config(
                    node,
                    registry,
                    errors,
                    scope=(node.id,),
                ),
                "constants": {},
                "args": [
                    e.source_node for e in positional_by_target.get(node.id, [])
                ],
            }
        else:
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
        if node.output_templates:
            node_dict["output_templates"] = dict(node.output_templates)

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

    node = err.node
    if err.path:
        scope = "/".join(str(part) for part in err.path)
        detail = f"in sub-workflow '{scope}': {detail}"
        if node:
            node_str = str(node)
            node = node_str if node_str == scope or node_str.startswith(f"{scope}/") else f"{scope}/{node_str}"
        else:
            node = scope

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
        node=node,
        field=err.field,
        edge_id=getattr(err, "edge_id", None),
    )
