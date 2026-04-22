"""Graph validation orchestration.

Given a ``GraphState``, produce a ``ValidationResult`` describing:

* **structural errors** (duplicate IDs, unknown edge endpoints)
* **cycle detection** (one ``cycle_detected`` error per run)
* **type compatibility** for each ``ColumnRefEdge``
* **parameter validation** via Pydantic models built from tool ``Inputs``
* **missing required connections** (required inputs with no edge/constant)
* **cache status** per node (signature hash lookup in the storage path)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bioimageflow_server.models.graph import ColumnRefEdge, GraphState
from bioimageflow_server.models.validation import (
    GraphValidationError,
    NodeStatus,
    ValidationResult,
)
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService


# ---- Helpers ---------------------------------------------------------------


def _is_binding_shape(value: Any) -> bool:
    """Return True if *value* looks like a serialised ``ColumnRef`` binding.

    Binding shape is ``{"node_id": ..., "output": ...}``. PATCH endpoints
    reject this because parameter-only patches must carry constants only.
    """
    if not isinstance(value, dict):
        return False
    return "node_id" in value and "output" in value


def _get_inputs_annotations(tool_class: type) -> dict[str, Any]:
    inputs_cls = getattr(tool_class, "Inputs", None)
    if inputs_cls is None:
        return {}
    if hasattr(inputs_cls, "_get_all_annotations"):
        return inputs_cls._get_all_annotations()
    annotations: dict[str, Any] = {}
    for klass in reversed(inputs_cls.__mro__):
        annotations.update(getattr(klass, "__annotations__", {}))
    return annotations


def _get_outputs_annotations(tool_class: type) -> dict[str, Any] | None:
    outputs_cls = getattr(tool_class, "Outputs", None)
    if outputs_cls is None:
        return None
    if hasattr(outputs_cls, "_get_all_annotations"):
        return outputs_cls._get_all_annotations()
    annotations: dict[str, Any] = {}
    for klass in reversed(outputs_cls.__mro__):
        annotations.update(getattr(klass, "__annotations__", {}))
    return annotations


def _is_dataframe_tool(tool_class: type) -> bool:
    try:
        from bioimageflow.dataframe_tool import DataFrameTool
    except Exception:  # pragma: no cover
        return False
    return issubclass(tool_class, DataFrameTool)


def _has_default(tool_class: type, field_name: str) -> bool:
    inputs_cls = getattr(tool_class, "Inputs", None)
    if inputs_cls is None:
        return False
    return hasattr(inputs_cls, field_name)


def _get_env_hash(tool_class: type) -> str:
    from bioimageflow.cache import compute_env_hash

    env = getattr(tool_class, "environment", None)
    deps = getattr(env, "dependencies", None) if env is not None else None
    if deps is None:
        return compute_env_hash({})
    return compute_env_hash(deps)


def _tool_version(tool_class: type, metadata_version: str) -> str:
    return getattr(tool_class, "_bif_package_version", None) or metadata_version


# ---- Core validation -------------------------------------------------------


def _detect_cycle(graph: GraphState) -> GraphValidationError | None:
    """Run topological-sort-based cycle detection on the node graph.

    Returns a ``cycle_detected`` error or ``None``.
    """
    from graphlib import CycleError, TopologicalSorter

    node_ids = {n.id for n in graph.nodes}
    predecessors: dict[str, set[str]] = {nid: set() for nid in node_ids}

    # Self-loop — produce a readable error immediately.
    for edge in graph.edges:
        if edge.source_node == edge.target_node and edge.source_node in node_ids:
            return GraphValidationError(
                type="cycle_detected",
                detail=f"Self-loop on node: {edge.source_node}",
            )

    for edge in graph.edges:
        if edge.source_node in node_ids and edge.target_node in node_ids:
            predecessors[edge.target_node].add(edge.source_node)

    sorter = TopologicalSorter(predecessors)
    try:
        sorter.prepare()
    except CycleError as exc:
        cycle_path = exc.args[1] if len(exc.args) > 1 else []
        return GraphValidationError(
            type="cycle_detected",
            detail="Cycle: " + " -> ".join(cycle_path),
        )
    return None


def _validate_parameter_value(
    tool_class: type,
    parameters: dict[str, Any],
    excluded_fields: set[str],
    node_id: str,
) -> list[GraphValidationError]:
    """Run Pydantic validation on ``parameters`` for ``tool_class``.

    Fields in ``excluded_fields`` are skipped (they are connected via an
    edge and validated elsewhere). Returns a list of
    ``parameter_invalid`` errors.
    """
    from bioimageflow.validation import build_pydantic_model
    from pydantic import ValidationError

    inputs_cls = getattr(tool_class, "Inputs", None)
    if inputs_cls is None:
        return []

    try:
        Model = build_pydantic_model(inputs_cls)
    except Exception:
        return []

    to_validate = {k: v for k, v in parameters.items() if k not in excluded_fields}

    errors: list[GraphValidationError] = []
    try:
        # Validate only the supplied fields — skip required-field checks here
        # because they are handled separately in missing-connection logic.
        # Pydantic would otherwise fail on missing required fields that are
        # actually satisfied via edges.
        # We call the model per-field to isolate validation errors.
        for field_name, value in to_validate.items():
            if field_name not in inputs_cls._get_all_annotations():
                continue
            try:
                # Build a single-field model and validate
                from pydantic import create_model as _create

                annotation = inputs_cls._get_all_annotations()[field_name]
                default = getattr(inputs_cls, field_name, ...)
                SingleModel = _create(
                    f"{inputs_cls.__name__}__{field_name}",
                    **{field_name: (annotation, default)},
                )
                SingleModel(**{field_name: value})
            except ValidationError as exc:
                first = exc.errors()[0] if exc.errors() else {"msg": "invalid"}
                errors.append(
                    GraphValidationError(
                        type="parameter_invalid",
                        detail=str(first.get("msg", "invalid")),
                        node=node_id,
                        field=field_name,
                    )
                )
    except Exception:
        # Fall back to best-effort: don't crash the validator on unexpected errors.
        pass
    return errors


def _compute_node_status(
    node_id: str,
    tool_class: type,
    tool_metadata_version: str,
    resolved_params: dict[str, Any],
    upstream_hashes: dict[str, str],
    storage_path: Path | None,
    dev_mode: bool,
) -> tuple[NodeStatus, str]:
    """Compute a node's cache status and return (NodeStatus, signature_hash)."""
    from bioimageflow.cache import cache_lookup, compute_signature_hash
    from bioimageflow.storage import get_node_dir
    from bioimageflow.validation import get_source_hash

    env_hash = _get_env_hash(tool_class)
    source_hash = get_source_hash(tool_class) if dev_mode else None
    try:
        sig_hash = compute_signature_hash(
            tool_class.__name__,
            _tool_version(tool_class, tool_metadata_version),
            env_hash,
            resolved_params,
            upstream_hashes,
            source_hash=source_hash,
        )
    except Exception:
        # If serialisation fails (e.g. non-hashable constant), treat as unexecuted.
        return (
            NodeStatus(node_id=node_id, status="unexecuted", cached=False),
            "",
        )

    if storage_path is None:
        return (
            NodeStatus(node_id=node_id, status="unexecuted", cached=False),
            sig_hash,
        )

    node_dir = get_node_dir(storage_path, node_id)
    cache_path = cache_lookup(node_dir, sig_hash)
    if cache_path is not None:
        return (
            NodeStatus(node_id=node_id, status="executed", cached=True),
            sig_hash,
        )
    if node_dir.exists() and any(node_dir.iterdir()):
        return (
            NodeStatus(node_id=node_id, status="out_of_date", cached=False),
            sig_hash,
        )
    return (
        NodeStatus(node_id=node_id, status="unexecuted", cached=False),
        sig_hash,
    )


def validate_graph(
    graph: GraphState,
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    dev_mode: bool = True,
) -> ValidationResult:
    """Run full validation on ``graph``.

    Returns a :class:`ValidationResult` containing per-node statuses and a
    list of errors (structural, cycle, type, parameter, missing-connection).
    """
    build_result = build_workflow(graph, registry, storage_path=storage_path)
    errors: list[GraphValidationError] = list(build_result.errors)

    node_statuses: dict[str, NodeStatus] = {}

    # Disabled nodes get disabled status.
    for nid in build_result.disabled_node_ids:
        node_statuses[nid] = NodeStatus(node_id=nid, status="disabled", cached=False)

    # Cycle detection (report a single error).
    cycle_err = _detect_cycle(graph)
    if cycle_err is not None:
        errors.append(cycle_err)

    # Type compatibility for each ColumnRefEdge.
    from bioimageflow.validation import extract_image_spec
    from bioimageflow_core.types import check_compatibility

    for edge in graph.edges:
        if not isinstance(edge, ColumnRefEdge):
            continue
        src_cls = build_result.tool_classes.get(edge.source_node)
        dst_cls = build_result.tool_classes.get(edge.target_node)
        if src_cls is None or dst_cls is None:
            continue
        # Skip when producer is a DataFrameTool with no declared Outputs.
        if _is_dataframe_tool(src_cls) and getattr(src_cls, "Outputs", None) is None:
            continue
        src_outputs = _get_outputs_annotations(src_cls)
        dst_inputs = _get_inputs_annotations(dst_cls)
        if src_outputs is None or dst_inputs is None:
            continue
        if edge.source_output not in src_outputs or edge.target_input not in dst_inputs:
            continue
        producer_spec = extract_image_spec(src_outputs[edge.source_output])
        consumer_spec = extract_image_spec(dst_inputs[edge.target_input])
        if producer_spec is None or consumer_spec is None:
            continue
        if not check_compatibility(producer_spec, consumer_spec):
            errors.append(
                GraphValidationError(
                    type="type_incompatible",
                    detail=(
                        f"Output '{edge.source_output}' of '{edge.source_node}' "
                        f"is not compatible with input '{edge.target_input}' of "
                        f"'{edge.target_node}'"
                    ),
                    edge_id=edge.id,
                )
            )

    # For each enabled node: parameter validation + missing connections + cache status.
    # Compute upstream hashes in topological order.
    from graphlib import CycleError, TopologicalSorter

    node_ids_enabled = set(build_result.tool_classes.keys())
    dep_graph: dict[str, set[str]] = {nid: set() for nid in node_ids_enabled}
    edges_by_target: dict[str, list[Any]] = {nid: [] for nid in node_ids_enabled}
    for edge in graph.edges:
        if edge.source_node in node_ids_enabled and edge.target_node in node_ids_enabled:
            dep_graph[edge.target_node].add(edge.source_node)
        if edge.target_node in node_ids_enabled:
            edges_by_target[edge.target_node].append(edge)

    try:
        topo_order = list(TopologicalSorter(dep_graph).static_order())
    except CycleError:
        topo_order = list(node_ids_enabled)

    sig_hashes: dict[str, str] = {}
    nodes_by_id = {n.id: n for n in graph.nodes}
    metadata_by_id: dict[str, Any] = {
        nid: registry.get_tool(nodes_by_id[nid].tool_name) for nid in node_ids_enabled
    }

    for nid in topo_order:
        node_state = nodes_by_id.get(nid)
        if node_state is None:
            continue
        tool_class = build_result.tool_classes[nid]
        metadata = metadata_by_id.get(nid)
        tool_version = metadata.package_version if metadata is not None else "unknown"

        connected_fields: set[str] = set()
        for edge in edges_by_target.get(nid, []):
            if isinstance(edge, ColumnRefEdge):
                connected_fields.add(edge.target_input)

        # --- Parameter validation ---
        param_errors = _validate_parameter_value(
            tool_class, node_state.parameters, connected_fields, nid
        )
        errors.extend(param_errors)

        # --- Missing required connections ---
        inputs_cls = getattr(tool_class, "Inputs", None)
        if inputs_cls is not None:
            for field_name in inputs_cls._get_all_annotations():
                if field_name in connected_fields:
                    continue
                if field_name in node_state.parameters:
                    continue
                if _has_default(tool_class, field_name):
                    continue
                errors.append(
                    GraphValidationError(
                        type="missing_connection",
                        detail=(
                            f"Required input '{field_name}' of node "
                            f"'{nid}' has no connection and no constant value"
                        ),
                        node=nid,
                        field=field_name,
                    )
                )

        # --- Cache status ---
        upstream_hashes: dict[str, str] = {}
        for upstream_id in dep_graph.get(nid, set()):
            if upstream_id in sig_hashes:
                upstream_hashes[upstream_id] = sig_hashes[upstream_id]

        resolved_params = {
            k: v
            for k, v in node_state.parameters.items()
            if k not in connected_fields
        }
        status, sig_hash = _compute_node_status(
            nid,
            tool_class,
            tool_version,
            resolved_params,
            upstream_hashes,
            storage_path,
            dev_mode,
        )
        node_statuses[nid] = status
        sig_hashes[nid] = sig_hash

    # Nodes whose build failed (missing_tool/missing_package) don't appear in
    # tool_classes — assign a best-effort "unexecuted" status so the frontend
    # still has an entry to render.
    for node in graph.nodes:
        if node.id in node_statuses:
            continue
        if node.id in build_result.disabled_node_ids:
            continue
        node_statuses[node.id] = NodeStatus(
            node_id=node.id, status="unexecuted", cached=False
        )

    return ValidationResult(
        valid=len(errors) == 0,
        node_statuses=node_statuses,
        errors=errors,
    )


def validate_parameters(
    node_id: str,
    tool_name: str,
    parameters: dict[str, Any],
    registry: ToolRegistryService,
    storage_path: Path | None = None,
    dev_mode: bool = True,
) -> ValidationResult:
    """Validate a single node's parameters in isolation.

    Used by the PATCH endpoint. Returns a :class:`ValidationResult` whose
    ``node_statuses`` contains exactly one entry (the patched node).
    """
    errors: list[GraphValidationError] = []

    metadata = registry.get_tool(tool_name)
    if metadata is None:
        errors.append(
            GraphValidationError(
                type="missing_tool",
                detail=f"Tool '{tool_name}' not found in registry",
                node=node_id,
            )
        )
        return ValidationResult(
            valid=False,
            node_statuses={
                node_id: NodeStatus(node_id=node_id, status="out_of_date", cached=False)
            },
            errors=errors,
        )

    # Reject binding-shaped values (constants only for PATCH).
    for field_name, value in parameters.items():
        if _is_binding_shape(value):
            errors.append(
                GraphValidationError(
                    type="parameter_invalid",
                    detail=(
                        "PATCH accepts constant parameters only; use PUT /graph "
                        "to modify connections"
                    ),
                    node=node_id,
                    field=field_name,
                )
            )

    tool_class = registry.get_tool_class(tool_name)
    if tool_class is not None and not errors:
        errors.extend(
            _validate_parameter_value(tool_class, parameters, set(), node_id)
        )

    # Conservative cache status: check the filesystem only.
    status = _patch_cache_status(node_id, storage_path)

    return ValidationResult(
        valid=len(errors) == 0,
        node_statuses={node_id: status},
        errors=errors,
    )


def _patch_cache_status(node_id: str, storage_path: Path | None) -> NodeStatus:
    """Conservative cache status for a PATCH response.

    Returns ``out_of_date`` if the node's cache directory exists on disk,
    ``unexecuted`` otherwise. Does not compute a signature hash — the
    follow-up debounced PUT /graph is authoritative.
    """
    if storage_path is None:
        return NodeStatus(node_id=node_id, status="unexecuted", cached=False)
    from bioimageflow.storage import get_node_dir

    node_dir = get_node_dir(storage_path, node_id)
    if node_dir.exists() and any(node_dir.iterdir()):
        return NodeStatus(node_id=node_id, status="out_of_date", cached=False)
    return NodeStatus(node_id=node_id, status="unexecuted", cached=False)
