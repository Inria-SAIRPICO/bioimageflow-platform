"""Mechanical translation between platform graphs and BioImageFlow graphs."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from bioimageflow import deserialize_constant, serialize_constant

from bioimageflow_server.models.graph import (
    ColumnEdge,
    GraphState,
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

if TYPE_CHECKING:
    from bioimageflow_server.models.settings import Settings


@dataclass
class TranslationResult:
    """A recursive library graph and any tool-resolution errors."""

    lib_dict: dict[str, Any]
    errors: list[GraphValidationError] = field(default_factory=list)


def _absolute_runtime_path(path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else Path.cwd() / candidate


def _scoped(scope: tuple[str, ...], node_id: str) -> str:
    return "/".join((*scope, node_id))


def _tool_library_identity(
    node: ToolNodeState,
    registry: ToolRegistryService,
    errors: list[GraphValidationError],
    scope: tuple[str, ...],
) -> tuple[str, str, str | None, str | None]:
    """Resolve one tool without inspecting private library state."""

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
    root_storage_path: Path | None = None,
    root_engine: str | None = None,
    root_execution: str | None = None,
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
        if not node.enabled:
            item["enabled"] = False
        nodes.append(item)

    config = graph.config.model_dump(mode="json", by_alias=True, exclude_none=True)
    if root_storage_path is not None:
        config["storage_path"] = str(_absolute_runtime_path(root_storage_path))
    if root_engine is not None:
        config["engine"] = root_engine
    if root_execution is not None:
        config["execution"] = root_execution

    return {
        "schema_version": 1,
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
        tool_class = registry.get_tool_class(node.tool_name)
        if tool_class is None or issubclass(tool_class, ProcessingTool):
            return True
    return False


def graph_state_to_lib_dict(
    graph: GraphState,
    registry: ToolRegistryService,
    *,
    storage_path: Path | None = None,
    engine: str | None = None,
    settings: Settings | None = None,
) -> TranslationResult:
    """Translate the accepted recursive graph through one code path."""

    errors: list[GraphValidationError] = []
    resolved_engine = (
        "wetlands" if graph_requires_wetlands(graph, registry) else "direct"
    )
    execution = settings.execution_engine if settings is not None else engine
    return TranslationResult(
        lib_dict=_graph_to_library(
            graph,
            registry,
            errors,
            root_storage_path=storage_path,
            root_engine=resolved_engine,
            root_execution=execution,
        ),
        errors=errors,
    )


def _default_position(index: int) -> tuple[float, float]:
    return (float((index % 4) * 280), float((index // 4) * 180))


def lib_dict_to_graph_state(workflow_data: dict[str, Any]) -> GraphState:
    """Materialize an editable platform graph from the strict library grammar."""

    if set(workflow_data) == {"archive_version", "workflow", "custom_sources"}:
        graph_data = workflow_data["workflow"]
    else:
        graph_data = workflow_data
    if not isinstance(graph_data, dict):
        raise ValueError("Library workflow graph must be an object")

    raw_nodes = graph_data.get("nodes")
    if not isinstance(raw_nodes, list):
        raise ValueError("Library workflow nodes must be an array")
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
                    "position": _default_position(index),
                    "enabled": raw.get("enabled", True),
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
                "position": _default_position(index),
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
            }
        )

    return GraphState.model_validate(
        {
            "schema_version": graph_data.get("schema_version"),
            "name": graph_data.get("name"),
            "display_name": graph_data.get("display_name"),
            "nodes": nodes,
            "edges": graph_data.get("edges"),
            "interface": graph_data.get("interface"),
            "config": graph_data.get("config"),
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
