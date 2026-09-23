"""Mechanical translation between platform graphs and BioImageFlow graphs."""

from __future__ import annotations

import heapq
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from bioimageflow import deserialize_constant, serialize_constant

from bioimageflow_server.models.graph import (
    ColumnEdge,
    GraphState,
    NodeResourceOverrides,
    ToolNodeState,
    WorkflowNodeState,
)
from bioimageflow_server.models.validation import GraphValidationError
from bioimageflow_server.models.workflow import (
    LocalToolReference,
    MissingPackage,
    MissingTool,
    RequiredPackage,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService

@dataclass
class TranslationResult:
    """A recursive library graph and any tool-resolution errors."""

    lib_dict: dict[str, Any]
    errors: list[GraphValidationError] = field(default_factory=list)


def _scoped(scope: tuple[str, ...], node_id: str) -> str:
    return "/".join((*scope, node_id))


def _tool_library_identity(
    node: ToolNodeState,
    registry: ToolRegistryService,
    errors: list[GraphValidationError],
    scope: tuple[str, ...],
) -> tuple[str, str, str | None, str | None]:
    """Resolve one tool without inspecting private library state."""

    if node.source_module is not None and node.tool_module and node.tool_class:
        # Owned source identity takes precedence over a same-named live tool.
        return (
            node.tool_module,
            node.tool_class,
            node.tool_package,
            node.tool_package_version,
        )

    metadata = registry.get_tool(node.tool_name)
    tool_class = registry.get_tool_class(node.tool_name)
    if tool_class is not None:
        from bioimageflow.tool_loader import get_tool_package_info

        package, version, module = get_tool_package_info(tool_class)
        return module, tool_class.__name__, package, version

    if node.tool_module and node.tool_class:
        # Portable imports can carry a fully specified tool that is not in the
        # live registry yet.  The library's public loader reports the precise
        # missing package/source error during validation.
        return (
            node.tool_module,
            node.tool_class,
            node.tool_package,
            node.tool_package_version,
        )

    error_type: Literal["missing_tool", "missing_package"] = (
        "missing_package" if metadata is not None else "missing_tool"
    )
    detail = (
        f"Package '{metadata.package}=={metadata.package_version}' is not installed"
        if metadata is not None
        else f"Tool '{node.tool_name}' not found in registry"
    )
    errors.append(
        GraphValidationError(
            type=error_type,
            detail=detail,
            node=_scoped(scope, node.id),
        )
    )
    return node.tool_module or node.tool_name, node.tool_class or node.tool_name, None, None


def _interface_dict(graph: GraphState) -> dict[str, Any]:
    return graph.interface.model_dump(mode="json", by_alias=True, exclude_none=True)


def _graph_to_library(
    graph: GraphState,
    registry: ToolRegistryService,
    errors: list[GraphValidationError],
    *,
    scope: tuple[str, ...] = (),
    root_engine: str | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    for node in graph.nodes:
        if isinstance(node, WorkflowNodeState):
            item: dict[str, Any] = {
                "name": node.id,
                "type": "workflow",
                "workflow": _graph_to_library(
                    node.workflow,
                    registry,
                    errors,
                    scope=(*scope, node.id),
                ),
                "bindings": {
                    port_id: value.model_dump(mode="json", by_alias=True)
                    for port_id, value in node.bindings.items()
                },
            }
        else:
            module, class_name, package, version = _tool_library_identity(
                node, registry, errors, scope
            )
            connected_fields = {
                edge.target_input
                for edge in graph.edges
                if isinstance(edge, ColumnEdge) and edge.target_node == node.id
            }
            exposed_fields = {
                target.port.name
                for port in graph.interface.inputs
                for target in port.targets
                if target.node == node.id and target.port.kind == "field"
            }
            item = {
                "name": node.id,
                "type": "tool",
                "tool_module": module,
                "tool_class": class_name,
                "tool_package": package,
                "tool_package_version": version,
                "constants": {
                    key: serialize_constant(value)
                    for key, value in node.parameters.items()
                    if key not in connected_fields or key in exposed_fields
                },
            }
            if node.source_module is not None:
                item["source_module"] = node.source_module
            if node.output_templates:
                item["output_templates"] = dict(node.output_templates)
            if node.resources.has_overrides():
                from bioimageflow_core.tool import ProcessingTool

                tool_class = registry.get_tool_class(node.tool_name)
                if tool_class is not None and not issubclass(tool_class, ProcessingTool):
                    errors.append(
                        GraphValidationError(
                            type="parameter_invalid",
                            detail="Worker resource overrides apply only to ProcessingTool nodes",
                            node=_scoped(scope, node.id),
                            field="resources",
                        )
                    )
                else:
                    resource_overrides = node.resources.to_library_dict()
                    if tool_class is not None:
                        import importlib

                        library_value = importlib.import_module(
                            "bioimageflow"
                        ).NodeResourceOverrides.from_dict(resource_overrides)
                        try:
                            library_value.effective(getattr(tool_class, "resources", None))
                        except (TypeError, ValueError) as exc:
                            errors.append(
                                GraphValidationError(
                                    type="parameter_invalid",
                                    detail=str(exc),
                                    node=_scoped(scope, node.id),
                                    field="resources",
                                )
                            )
                            resource_overrides = None
                    if resource_overrides is not None:
                        item["resource_overrides"] = resource_overrides
        if node.viewer_additions:
            item["viewer_additions"] = {
                output: viewer.model_dump(mode="json", by_alias=True)
                for output, viewer in sorted(node.viewer_additions.items())
            }
        if not node.enabled:
            item["enabled"] = False
        nodes.append(item)

    config = graph.config.model_dump(mode="json", by_alias=True, exclude_none=True)
    if root_engine is not None:
        config["engine"] = root_engine
    return {
        "schema_version": 2,
        "name": graph.name,
        "display_name": graph.display_name,
        "interface": _interface_dict(graph),
        "nodes": nodes,
        "edges": [
            edge.model_dump(mode="json", by_alias=True, exclude_none=True)
            for edge in graph.edges
        ],
        "config": config,
    }


def graph_requires_wetlands(
    graph: GraphState,
    registry: ToolRegistryService,
) -> bool:
    """Return whether any enabled recursive node requires worker execution."""

    from bioimageflow_core.tool import ProcessingTool

    for node in graph.nodes:
        if not node.enabled:
            continue
        if isinstance(node, WorkflowNodeState):
            if graph_requires_wetlands(node.workflow, registry):
                return True
            continue
        # Owned source bytes are resolved during compilation, not by the global
        # catalog. Use the worker-capable engine rather than a same-named class.
        if node.source_module:
            return True
        tool_class = registry.get_tool_class(node.tool_name)
        if tool_class is None or issubclass(tool_class, ProcessingTool):
            return True
    return False


def graph_state_to_lib_dict(
    graph: GraphState,
    registry: ToolRegistryService,
) -> TranslationResult:
    """Translate the accepted recursive graph through one code path."""

    errors: list[GraphValidationError] = []
    resolved_engine = (
        "wetlands" if graph_requires_wetlands(graph, registry) else "direct"
    )
    return TranslationResult(
        lib_dict=_graph_to_library(
            graph,
            registry,
            errors,
            root_engine=resolved_engine,
        ),
        errors=errors,
    )


_LAYOUT_COLUMN_GAP = 320.0
_LAYOUT_ROW_GAP = 220.0


def _default_positions(graph_data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Derive one deterministic layout for a position-less library graph.

    Longest-path ranks make dependencies flow left to right. Nodes in a rank
    retain a stable order, refined by their predecessors' average rows to avoid
    simple crossings. Weakly disconnected components are stacked below the
    largest component. Cyclic remnants share a final column so the semantic
    validator can still report the cycle without layout becoming another error.
    """

    raw_nodes = graph_data.get("nodes")
    if not isinstance(raw_nodes, list):
        return {}
    node_ids = [
        str(node.get("name") or "")
        for node in raw_nodes
        if isinstance(node, dict)
    ]
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    successors: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    predecessors: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    neighbours: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    raw_edges = graph_data.get("edges")
    if isinstance(raw_edges, list):
        for edge in raw_edges:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source_node")
            target = edge.get("target_node")
            if (
                not isinstance(source, str)
                or not isinstance(target, str)
                or source == target
                or source not in order
                or target not in order
            ):
                continue
            successors[source].add(target)
            predecessors[target].add(source)
            neighbours[source].add(target)
            neighbours[target].add(source)

    components: list[list[str]] = []
    unseen = set(node_ids)
    while unseen:
        seed = min(unseen, key=order.__getitem__)
        stack = [seed]
        component: list[str] = []
        unseen.remove(seed)
        while stack:
            node_id = stack.pop()
            component.append(node_id)
            for neighbour in sorted(
                neighbours[node_id], key=order.__getitem__, reverse=True
            ):
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
        component.sort(key=order.__getitem__)
        components.append(component)
    components.sort(key=lambda item: (-len(item), min(order[node_id] for node_id in item)))

    positions: dict[str, tuple[float, float]] = {}
    component_top = 0.0
    for component in components:
        component_set = set(component)
        indegree = {
            node_id: len(predecessors[node_id] & component_set)
            for node_id in component
        }
        ranks = {node_id: 0 for node_id in component}
        ready = [
            (order[node_id], node_id)
            for node_id in component
            if indegree[node_id] == 0
        ]
        heapq.heapify(ready)
        processed: set[str] = set()
        while ready:
            _index, node_id = heapq.heappop(ready)
            processed.add(node_id)
            for target in sorted(successors[node_id], key=order.__getitem__):
                if target not in component_set:
                    continue
                ranks[target] = max(ranks[target], ranks[node_id] + 1)
                indegree[target] -= 1
                if indegree[target] == 0:
                    heapq.heappush(ready, (order[target], target))

        unresolved = [node_id for node_id in component if node_id not in processed]
        if unresolved:
            fallback_rank = max(
                (ranks[node_id] for node_id in processed), default=-1
            ) + 1
            for node_id in unresolved:
                ranks[node_id] = fallback_rank

        layers: dict[int, list[str]] = {}
        for node_id in component:
            layers.setdefault(ranks[node_id], []).append(node_id)
        row_orders: dict[str, int] = {}
        for rank in sorted(layers):
            layer = layers[rank]

            def layer_order(node_id: str) -> tuple[float, int]:
                upstream_rows = [
                    row_orders[source]
                    for source in predecessors[node_id]
                    if source in row_orders
                ]
                barycenter = (
                    sum(upstream_rows) / len(upstream_rows)
                    if upstream_rows
                    else float(order[node_id])
                )
                return barycenter, order[node_id]

            layer.sort(key=layer_order)
            row_orders.update(
                {node_id: row for row, node_id in enumerate(layer)}
            )

        widest_layer = max((len(layer) for layer in layers.values()), default=1)
        for rank, layer in layers.items():
            layer_top = component_top + (
                (widest_layer - len(layer)) * _LAYOUT_ROW_GAP / 2
            )
            for row, node_id in enumerate(layer):
                positions[node_id] = (
                    rank * _LAYOUT_COLUMN_GAP,
                    layer_top + row * _LAYOUT_ROW_GAP,
                )
        component_top += (widest_layer + 1) * _LAYOUT_ROW_GAP
    return positions


def _validate_library_wire_shape(value: dict[str, Any]) -> dict[str, Any]:
    """Reject every field that this GUI projection would otherwise discard."""

    from bioimageflow import Workflow

    archive_version = value.get("archive_version")
    if archive_version in {1, 2}:
        expected = {"archive_version", "workflow", "custom_sources"}
        if archive_version == 2:
            expected.add("viewing_requirements")
        if set(value) != expected:
            raise ValueError(
                f"Workflow archive fields must be exactly {sorted(expected)}"
            )
        if archive_version == 2:
            Workflow.inspect_viewing_requirements(deepcopy(value))
        graph = value.get("workflow")
    elif "archive_version" in value:
        raise ValueError("Only workflow archive_version 1 and 2 are supported")
    else:
        graph = value
    if not isinstance(graph, dict):
        raise ValueError("Library workflow graph must be an object")
    graph_fields = {
        "schema_version",
        "name",
        "display_name",
        "interface",
        "nodes",
        "edges",
        "config",
    }
    if set(graph) != graph_fields:
        raise ValueError(
            f"Workflow graph fields must be exactly {sorted(graph_fields)}"
        )
    version = graph.get("schema_version")
    if version not in {1, 2}:
        raise ValueError("Only workflow schema_version 1 and 2 are supported")
    config = graph.get("config")
    if not isinstance(config, dict) or not set(config) <= {
        "engine",
        "execution",
        "output_view",
    }:
        raise ValueError("Unknown workflow config field")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Library workflow nodes must be an array")
    for raw in nodes:
        if not isinstance(raw, dict):
            raise ValueError("Library workflow node must be an object")
        common = {"name", "type", "enabled"}
        if version == 2:
            common.add("viewer_additions")
        node_type = raw.get("type")
        if node_type == "workflow":
            allowed = common | {"workflow", "bindings"}
            required = {"name", "type", "workflow", "bindings"}
            child = raw.get("workflow")
            if isinstance(child, dict):
                _validate_library_wire_shape(child)
        elif node_type == "tool":
            allowed = common | {
                "tool_module",
                "tool_class",
                "tool_package",
                "tool_package_version",
                "source_module",
                "constants",
                "output_templates",
                "resource_overrides",
            }
            required = {
                "name",
                "type",
                "tool_module",
                "tool_class",
                "tool_package",
                "tool_package_version",
                "constants",
            }
        else:
            raise ValueError("Unknown or malformed workflow node variant")
        if not required <= set(raw) or not set(raw) <= allowed:
            raise ValueError(f"Malformed or unknown fields on node {raw.get('name')!r}")
    return graph


def lib_dict_to_graph_state(workflow_data: dict[str, Any]) -> GraphState:
    """Materialize an editable platform graph from the strict library grammar."""

    # Prove the complete payload through the frozen library's public strict
    # loader before projecting GUI-owned fields. This prevents this adapter
    # from becoming an accidental unknown-field sink.
    from bioimageflow import Workflow

    graph_data = _validate_library_wire_shape(workflow_data)
    _, structural_errors = Workflow.from_dict(
        deepcopy(workflow_data),
        storage_path=".",
        validate_only=True,
        partial=True,
        auto_install=False,
    )
    construction_errors = [
        error
        for error in structural_errors
        if getattr(error, "kind", None) == "construction_failed"
    ]
    structural_markers = (
        "fields must be exactly",
        "Unknown workflow",
        "unknown fields",
        "Malformed",
        "schema_version",
        "viewer metadata",
        "viewer additions",
    )
    if construction_errors and any(
        marker in str(getattr(error, "message", error))
        for error in construction_errors
        for marker in structural_markers
    ):
        raise ValueError(str(construction_errors[0]))

    raw_nodes = graph_data.get("nodes")
    if not isinstance(raw_nodes, list):
        raise ValueError("Library workflow nodes must be an array")
    positions = _default_positions(graph_data)
    nodes: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise ValueError("Library workflow node must be an object")
        node_type = raw.get("type")
        node_id = str(raw.get("name") or "")
        if node_type == "workflow":
            child = lib_dict_to_graph_state(cast(dict[str, Any], raw["workflow"]))
            nodes.append(
                {
                    "type": "workflow",
                    "id": node_id,
                    "name": child.display_name or child.name,
                    "workflow": child.model_dump(mode="json", by_alias=True),
                    "bindings": raw.get("bindings", {}),
                    "position": positions.get(
                        node_id, (float(index) * _LAYOUT_COLUMN_GAP, 0.0)
                    ),
                    "enabled": raw.get("enabled", True),
                    **(
                        {"viewer_additions": raw["viewer_additions"]}
                        if "viewer_additions" in raw
                        else {}
                    ),
                }
            )
            continue
        if node_type != "tool":
            raise ValueError(f"Unknown library workflow node discriminator: {node_type!r}")
        constants = raw.get("constants", {})
        nodes.append(
            {
                "type": "tool",
                "id": node_id,
                "name": node_id,
                "tool_name": str(raw.get("tool_class") or ""),
                "position": positions.get(
                    node_id, (float(index) * _LAYOUT_COLUMN_GAP, 0.0)
                ),
                "parameters": {
                    str(key): deserialize_constant(value)
                    for key, value in constants.items()
                },
                "output_templates": raw.get("output_templates", {}),
                "enabled": raw.get("enabled", True),
                "tool_module": raw.get("tool_module"),
                "tool_class": raw.get("tool_class"),
                "tool_package": raw.get("tool_package"),
                "tool_package_version": raw.get("tool_package_version"),
                "source_module": raw.get("source_module"),
                "resources": (
                    NodeResourceOverrides.from_library_dict(raw["resource_overrides"]).model_dump(
                        mode="json", exclude_none=True
                    )
                    if "resource_overrides" in raw
                    else {}
                ),
                **(
                    {"viewer_additions": raw["viewer_additions"]}
                    if "viewer_additions" in raw
                    else {}
                ),
            }
        )

    raw_config = graph_data.get("config")
    config = (
        {
            key: value
            for key, value in raw_config.items()
            if key in {"engine", "execution", "output_view"}
        }
        if isinstance(raw_config, dict)
        else raw_config
    )
    return GraphState.model_validate(
        {
            "schema_version": 2,
            "name": graph_data.get("name"),
            "display_name": graph_data.get("display_name"),
            "nodes": nodes,
            "edges": graph_data.get("edges"),
            "interface": graph_data.get("interface"),
            "config": config,
        }
    )


def _walk_library_nodes(workflow_data: dict[str, Any], scope: tuple[str, ...] = ()):
    graph = workflow_data.get("workflow") if "archive_version" in workflow_data else workflow_data
    if not isinstance(graph, dict):
        return
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("name") or "")
        yield (*scope, node_id), node
        if node.get("type") == "workflow" and isinstance(node.get("workflow"), dict):
            yield from _walk_library_nodes(node["workflow"], (*scope, node_id))


def _is_local_tool_reference(
    node: dict[str, Any],
    metadata: Any = None,
) -> bool:
    """Return whether a tool is workflow-local rather than installable."""

    return (
        node.get("tool_package") == "__custom__"
        or isinstance(node.get("source_module"), str)
        or getattr(metadata, "source_kind", None) == "custom"
    )


def _has_embedded_tool_source(node: dict[str, Any]) -> bool:
    """Return whether the workflow carries the tool's source module."""

    return isinstance(node.get("source_module"), str)


def collect_required_packages(
    workflow_data: dict[str, Any],
    registry: ToolRegistryService,
) -> tuple[list[RequiredPackage], list[LocalToolReference]]:
    """Collect package/source requirements recursively by scoped node path."""

    packages: dict[tuple[str, str], RequiredPackage] = {}
    local: dict[str, list[str]] = {}
    for path, node in _walk_library_nodes(workflow_data):
        if node.get("type") != "tool":
            continue
        tool_name = str(node.get("tool_class") or "")
        package = node.get("tool_package")
        version = node.get("tool_package_version")
        metadata = registry.get_tool(tool_name)
        if _is_local_tool_reference(node, metadata):
            if tool_name:
                local.setdefault(tool_name, []).append("/".join(path))
            continue
        if not isinstance(package, str) or not isinstance(version, str):
            if metadata is not None:
                package, version = metadata.package, metadata.package_version
        if isinstance(package, str) and isinstance(version, str):
            packages.setdefault(
                (package, version), RequiredPackage(name=package, version=version)
            )
        elif tool_name:
            local.setdefault(tool_name, []).append("/".join(path))
    return (
        [packages[key] for key in sorted(packages)],
        [
            LocalToolReference(tool_name=name, node_ids=paths)
            for name, paths in sorted(local.items())
        ],
    )


def _detect_missing_packages(
    workflow_data: dict[str, Any], registry: ToolRegistryService
) -> list[MissingPackage]:
    missing: dict[tuple[str, str], MissingPackage] = {}
    for path, node in _walk_library_nodes(workflow_data):
        package = node.get("tool_package")
        version = node.get("tool_package_version")
        if (
            node.get("type") != "tool"
            or _is_local_tool_reference(node)
            or not isinstance(package, str)
            or not isinstance(version, str)
        ):
            continue
        info = registry.get_package(package)
        installed = info.installed_versions if info is not None else []
        if version in installed:
            continue
        item = missing.setdefault(
            (package, version),
            MissingPackage(
                package_name=package,
                required_version=version,
                installed_versions=list(installed),
            ),
        )
        item.affected_nodes.append("/".join(path))
    return list(missing.values())


def _detect_missing_tools(
    workflow_data: dict[str, Any], registry: ToolRegistryService
) -> list[MissingTool]:
    missing: list[MissingTool] = []
    for path, node in _walk_library_nodes(workflow_data):
        if node.get("type") != "tool":
            continue
        if _has_embedded_tool_source(node):
            continue
        tool_name = str(node.get("tool_class") or "")
        if not tool_name or registry.get_tool(tool_name) is not None:
            continue
        package = node.get("tool_package")
        version = node.get("tool_package_version")
        if _is_local_tool_reference(node):
            package = None
            version = None
        info = registry.get_package(package) if isinstance(package, str) else None
        missing.append(
            MissingTool(
                node_id="/".join(path),
                tool_name=tool_name,
                package_name=package if isinstance(package, str) else None,
                required_version=version if isinstance(version, str) else None,
                installed_versions=list(info.installed_versions) if info else [],
            )
        )
    return missing


def rebind_lib_dict_versions(
    workflow_data: dict[str, Any], registry: ToolRegistryService
) -> dict[str, Any]:
    """Rebind installed-package versions recursively."""

    rebound = deepcopy(workflow_data)
    for _, node in _walk_library_nodes(rebound):
        if node.get("type") != "tool":
            continue
        tool_name = str(node.get("tool_class") or "")
        metadata = registry.get_tool(tool_name)
        if _is_local_tool_reference(node, metadata):
            continue
        package_name = str(node.get("tool_package") or (metadata.package if metadata else ""))
        package = registry.get_package(package_name) if package_name else None
        version = package.active_version if package and package.active_version else None
        if version is None and metadata is not None:
            version = metadata.package_version
        if package_name and version:
            node["tool_package"] = package_name
            node["tool_package_version"] = version
    return rebound


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
    "environment_incompatible": "environment_incompatible",
}


def lib_validation_error_to_graph_error(err: Any) -> GraphValidationError:
    """Preserve library scope paths in platform validation errors."""

    kind = err.kind
    node = err.node
    detail = err.message
    if err.path:
        scope = "/".join(str(part) for part in err.path)
        detail = f"in workflow '{scope}': {detail}"
        if node and not str(node).startswith(f"{scope}/") and str(node) != scope:
            node = f"{scope}/{node}"
        elif not node:
            node = scope
    if kind == "unknown_tool":
        lowered = detail.lower()
        error_type = "missing_package" if "package" in lowered or "load" in lowered else "missing_tool"
    elif kind == "construction_failed" and "cycle" in detail.lower():
        error_type = "cycle_detected"
    elif "does not accept upstream dataframes" in detail.lower():
        error_type = "source_tool_upstream"
    else:
        error_type = _KIND_TO_TYPE.get(kind, "parameter_invalid")
    return GraphValidationError(
        type=cast(Any, error_type),
        detail=detail,
        node=node,
        field=err.field,
        edge_id=err.edge_id,
    )
