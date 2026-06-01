"""Pure transforms for semantic workflow draft operations."""

from __future__ import annotations

from collections.abc import Sequence

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
    PositionalEdge,
    PublishedInput,
    PublishedOutput,
)
from bioimageflow_server.models.workflow_draft_operations import (
    ConnectColumnRefOperation,
    ConnectPositionalOperation,
    CreateNodeOperation,
    DeleteEdgeOperation,
    DeleteNodeOperation,
    DeletePublishedInputOperation,
    DeletePublishedOutputOperation,
    MoveNodeOperation,
    RenameNodeOperation,
    SetNodeEnabledOperation,
    SetPublishedInputOperation,
    SetPublishedOutputOperation,
    UpdateNodeParametersOperation,
    WorkflowDraftOperation,
)


class WorkflowDraftOperationError(ValueError):
    """Stable semantic operation error for later HTTP 422 mapping."""

    def __init__(
        self,
        *,
        operation_index: int,
        code: str,
        detail: str,
    ) -> None:
        self.operation_index = operation_index
        self.code = code
        self.detail = detail
        super().__init__(detail)


def apply_workflow_draft_operations(
    graph: GraphState,
    operations: Sequence[WorkflowDraftOperation],
) -> GraphState:
    """Apply a semantic operation batch to a deep copy of ``graph``.

    The input graph is never mutated. If any operation fails, no partially
    transformed graph is returned to the caller.
    """

    next_graph = graph.model_copy(deep=True)
    for index, operation in enumerate(operations):
        try:
            next_graph = _apply_one(next_graph, operation)
        except WorkflowDraftOperationError as exc:
            raise WorkflowDraftOperationError(
                operation_index=index,
                code=exc.code,
                detail=exc.detail,
            ) from exc
    return next_graph


def _apply_one(
    graph: GraphState,
    operation: WorkflowDraftOperation,
) -> GraphState:
    if isinstance(operation, CreateNodeOperation):
        return _create_node(graph, operation)
    if isinstance(operation, DeleteNodeOperation):
        return _delete_node(graph, operation)
    if isinstance(operation, RenameNodeOperation):
        return _replace_node(
            graph,
            operation.node_id,
            _require_node(graph, operation.node_id).model_copy(update={"name": operation.name}),
        )
    if isinstance(operation, UpdateNodeParametersOperation):
        node = _require_node(graph, operation.node_id)
        return _replace_node(
            graph,
            operation.node_id,
            node.model_copy(
                update={"parameters": {**node.parameters, **operation.parameters}},
                deep=True,
            ),
        )
    if isinstance(operation, SetNodeEnabledOperation):
        return _replace_node(
            graph,
            operation.node_id,
            _require_node(graph, operation.node_id).model_copy(
                update={"enabled": operation.enabled}
            ),
        )
    if isinstance(operation, MoveNodeOperation):
        return _replace_node(
            graph,
            operation.node_id,
            _require_node(graph, operation.node_id).model_copy(
                update={"position": operation.position}
            ),
        )
    if isinstance(operation, SetPublishedInputOperation):
        return _set_published_input(graph, operation)
    if isinstance(operation, DeletePublishedInputOperation):
        return _delete_published_input(graph, operation)
    if isinstance(operation, SetPublishedOutputOperation):
        return _set_published_output(graph, operation)
    if isinstance(operation, DeletePublishedOutputOperation):
        return _delete_published_output(graph, operation)
    if isinstance(operation, ConnectColumnRefOperation):
        return _connect_column_ref(graph, operation)
    if isinstance(operation, ConnectPositionalOperation):
        return _connect_positional(graph, operation)
    if isinstance(operation, DeleteEdgeOperation):
        return _delete_edge(graph, operation)
    _raise("unknown_operation", f"Unsupported operation: {operation!r}")


def _create_node(graph: GraphState, operation: CreateNodeOperation) -> GraphState:
    if _node_exists(graph, operation.node_id):
        _raise("duplicate_node_id", f"Node already exists: {operation.node_id}")
    node = NodeState(
        id=operation.node_id,
        name=operation.name,
        tool_name=operation.tool_name,
        position=operation.position,
        parameters=operation.parameters,
    )
    return graph.model_copy(update={"nodes": [*graph.nodes, node]})


def _delete_node(graph: GraphState, operation: DeleteNodeOperation) -> GraphState:
    _require_node(graph, operation.node_id)
    return graph.model_copy(
        update={
            "nodes": [node for node in graph.nodes if node.id != operation.node_id],
            "edges": [
                edge
                for edge in graph.edges
                if edge.source_node != operation.node_id and edge.target_node != operation.node_id
            ],
        }
    )


def _set_published_input(
    graph: GraphState,
    operation: SetPublishedInputOperation,
) -> GraphState:
    _require_node(graph, operation.internal_node_id)
    target = (operation.internal_node_id, operation.internal_field)
    existing_index = next(
        (
            index
            for index, item in enumerate(graph.published_inputs)
            if (item.internal_node_id, item.internal_field) == target
        ),
        None,
    )
    _ensure_published_name_available(graph, operation.name, allowed_input_target=target)
    if existing_index is None and "schema_" not in operation.model_fields_set:
        _raise(
            "missing_published_schema",
            f"Published input schema is required for new input: {operation.name}",
        )
    existing = (
        graph.published_inputs[existing_index]
        if existing_index is not None
        else None
    )
    item = PublishedInput(
        name=operation.name,
        internal_node_id=operation.internal_node_id,
        internal_field=operation.internal_field,
        kind=operation.kind,
        schema=(
            operation.schema_
            if "schema_" in operation.model_fields_set
            else existing.schema_ if existing is not None else None
        ),
        default=(
            operation.default
            if "default" in operation.model_fields_set
            else existing.default if existing is not None else None
        ),
    )
    inputs = list(graph.published_inputs)
    if existing_index is None:
        inputs.append(item)
    else:
        inputs[existing_index] = item
    return graph.model_copy(update={"published_inputs": inputs})


def _delete_published_input(
    graph: GraphState,
    operation: DeletePublishedInputOperation,
) -> GraphState:
    inputs = [item for item in graph.published_inputs if item.name != operation.name]
    if len(inputs) == len(graph.published_inputs):
        _raise("missing_published_input", f"Published input not found: {operation.name}")
    return graph.model_copy(update={"published_inputs": inputs})


def _set_published_output(
    graph: GraphState,
    operation: SetPublishedOutputOperation,
) -> GraphState:
    _require_node(graph, operation.internal_node_id)
    target = (operation.internal_node_id, operation.internal_output)
    existing_index = next(
        (
            index
            for index, item in enumerate(graph.published_outputs)
            if (item.internal_node_id, item.internal_output) == target
        ),
        None,
    )
    _ensure_published_name_available(graph, operation.name, allowed_output_target=target)
    if existing_index is None and "schema_" not in operation.model_fields_set:
        _raise(
            "missing_published_schema",
            f"Published output schema is required for new output: {operation.name}",
        )
    existing = (
        graph.published_outputs[existing_index]
        if existing_index is not None
        else None
    )
    item = PublishedOutput(
        name=operation.name,
        internal_node_id=operation.internal_node_id,
        internal_output=operation.internal_output,
        schema=(
            operation.schema_
            if "schema_" in operation.model_fields_set
            else existing.schema_ if existing is not None else None
        ),
    )
    outputs = list(graph.published_outputs)
    if existing_index is None:
        outputs.append(item)
    else:
        outputs[existing_index] = item
    return graph.model_copy(update={"published_outputs": outputs})


def _delete_published_output(
    graph: GraphState,
    operation: DeletePublishedOutputOperation,
) -> GraphState:
    outputs = [item for item in graph.published_outputs if item.name != operation.name]
    if len(outputs) == len(graph.published_outputs):
        _raise("missing_published_output", f"Published output not found: {operation.name}")
    return graph.model_copy(update={"published_outputs": outputs})


def _connect_column_ref(
    graph: GraphState,
    operation: ConnectColumnRefOperation,
) -> GraphState:
    _validate_connection_nodes(graph, operation.source_node, operation.target_node)
    edge_id = operation.edge_id or _column_ref_edge_id(operation)
    replacement_scope = {
        edge.id
        for edge in graph.edges
        if isinstance(edge, ColumnRefEdge)
        and edge.target_node == operation.target_node
        and edge.target_input == operation.target_input
    }
    _ensure_edge_id_available(graph, edge_id, replacement_scope)
    edge = ColumnRefEdge(
        id=edge_id,
        source_node=operation.source_node,
        target_node=operation.target_node,
        source_output=operation.source_output,
        target_input=operation.target_input,
    )
    return graph.model_copy(
        update={
            "edges": [
                existing
                for existing in graph.edges
                if not (
                    isinstance(existing, ColumnRefEdge)
                    and existing.target_node == operation.target_node
                    and existing.target_input == operation.target_input
                )
            ]
            + [edge]
        }
    )


def _connect_positional(
    graph: GraphState,
    operation: ConnectPositionalOperation,
) -> GraphState:
    _validate_connection_nodes(graph, operation.source_node, operation.target_node)
    edge_id = operation.edge_id or _positional_edge_id(operation)
    replacement_scope = {
        edge.id
        for edge in graph.edges
        if isinstance(edge, PositionalEdge)
        and edge.target_node == operation.target_node
        and edge.positional_index == operation.positional_index
    }
    _ensure_edge_id_available(graph, edge_id, replacement_scope)
    edge = PositionalEdge(
        id=edge_id,
        source_node=operation.source_node,
        target_node=operation.target_node,
        positional_index=operation.positional_index,
    )
    return graph.model_copy(
        update={
            "edges": [
                existing
                for existing in graph.edges
                if not (
                    isinstance(existing, PositionalEdge)
                    and existing.target_node == operation.target_node
                    and existing.positional_index == operation.positional_index
                )
            ]
            + [edge]
        }
    )


def _delete_edge(graph: GraphState, operation: DeleteEdgeOperation) -> GraphState:
    if not any(edge.id == operation.edge_id for edge in graph.edges):
        _raise("missing_edge", f"Edge not found: {operation.edge_id}")
    return graph.model_copy(
        update={"edges": [edge for edge in graph.edges if edge.id != operation.edge_id]}
    )


def _replace_node(graph: GraphState, node_id: str, replacement: NodeState) -> GraphState:
    _require_node(graph, node_id)
    return graph.model_copy(
        update={"nodes": [replacement if node.id == node_id else node for node in graph.nodes]}
    )


def _require_node(graph: GraphState, node_id: str) -> NodeState:
    for node in graph.nodes:
        if node.id == node_id:
            return node
    _raise("missing_node", f"Node not found: {node_id}")


def _node_exists(graph: GraphState, node_id: str) -> bool:
    return any(node.id == node_id for node in graph.nodes)


def _ensure_published_name_available(
    graph: GraphState,
    name: str,
    *,
    allowed_input_target: tuple[str, str] | None = None,
    allowed_output_target: tuple[str, str] | None = None,
) -> None:
    for item in graph.published_inputs:
        target = (item.internal_node_id, item.internal_field)
        if item.name == name and target != allowed_input_target:
            _raise("duplicate_published_name", f"Published name already exists: {name}")
    for item in graph.published_outputs:
        target = (item.internal_node_id, item.internal_output)
        if item.name == name and target != allowed_output_target:
            _raise("duplicate_published_name", f"Published name already exists: {name}")


def _validate_connection_nodes(graph: GraphState, source_node: str, target_node: str) -> None:
    _require_node(graph, source_node)
    _require_node(graph, target_node)
    if source_node == target_node:
        _raise("self_connection", f"Cannot connect node to itself: {source_node}")


def _ensure_edge_id_available(
    graph: GraphState,
    edge_id: str,
    replacement_scope: set[str],
) -> None:
    for edge in graph.edges:
        if edge.id == edge_id and edge.id not in replacement_scope:
            _raise("duplicate_edge_id", f"Edge already exists: {edge_id}")


def _column_ref_edge_id(operation: ConnectColumnRefOperation) -> str:
    return (
        f"e-{operation.source_node}-{operation.source_output}-"
        f"{operation.target_node}-{operation.target_input}"
    )


def _positional_edge_id(operation: ConnectPositionalOperation) -> str:
    return (
        f"e-{operation.source_node}-__dataframe_out-"
        f"{operation.target_node}-__positional_{operation.positional_index}"
    )


def _raise(code: str, detail: str) -> None:
    raise WorkflowDraftOperationError(
        operation_index=-1,
        code=code,
        detail=detail,
    )
