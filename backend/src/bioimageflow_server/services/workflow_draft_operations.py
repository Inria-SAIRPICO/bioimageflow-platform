"""Pure, atomic transforms for recursive workflow draft operations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import NoReturn, cast
from uuid import uuid4

from bioimageflow_server.models.graph import (
    ColumnEdge,
    DataFrameEdge,
    GraphState,
    ToolNodeState,
    WorkflowNodeState,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.models.workflow_draft_operations import (
    ConnectColumnEdgeOperation,
    ConnectDataFrameEdgeOperation,
    CreateToolNodeOperation,
    CreateWorkflowNodeOperation,
    DeleteEdgeOperation,
    DeleteNodeOperation,
    DeleteWorkflowInputOperation,
    DeleteWorkflowOutputOperation,
    DetachWorkflowSourceOperation,
    ExposeWorkflowInputOperation,
    ExposeWorkflowOutputOperation,
    MoveNodeOperation,
    MoveNodesOperation,
    RenameNodeOperation,
    SetNodeEnabledOperation,
    UpdateToolParametersOperation,
    WorkflowDraftOperation,
)


class WorkflowDraftOperationError(ValueError):
    """Stable semantic operation error for HTTP 422 mapping."""

    def __init__(self, *, operation_index: int, code: str, detail: str) -> None:
        self.operation_index = operation_index
        self.code = code
        self.detail = detail
        super().__init__(detail)


def apply_workflow_draft_operations(
    graph: GraphState,
    operations: Sequence[WorkflowDraftOperation],
) -> GraphState:
    """Apply a batch without mutating the accepted input graph."""

    next_graph = graph.model_copy(deep=True)
    for index, operation in enumerate(operations):
        try:
            next_graph = _apply_scoped(
                next_graph,
                operation.scope.workflow_path,
                lambda current, item=operation: _apply_local(current, item),
            )
            # ``model_copy`` is intentionally cheap during transforms; parse
            # the complete recursive result after every semantic transition.
            next_graph = GraphState.model_validate(
                next_graph.model_dump(mode="json", by_alias=True)
            )
        except WorkflowDraftOperationError as exc:
            raise WorkflowDraftOperationError(
                operation_index=index, code=exc.code, detail=exc.detail
            ) from exc
        except ValueError as exc:
            raise WorkflowDraftOperationError(
                operation_index=index,
                code="invalid_workflow_graph",
                detail=str(exc),
            ) from exc
    return next_graph


def apply_and_validate_workflow_draft_operations(
    graph: GraphState,
    operations: Sequence[WorkflowDraftOperation],
    *,
    get_tool_metadata: Callable[[str], ToolMetadata | None],
) -> GraphState:
    """Apply operations and validate referenced tool ports against metadata."""

    result = apply_workflow_draft_operations(graph, operations)
    _validate_tool_targets(result, get_tool_metadata)
    return result


def _apply_scoped(
    graph: GraphState,
    path: Sequence[str],
    update: Callable[[GraphState], GraphState],
) -> GraphState:
    if not path:
        return update(graph)
    node_id = path[0]
    node = _require_node(graph, node_id)
    if not isinstance(node, WorkflowNodeState):
        _raise("scope_not_workflow", f"Scope node is not a workflow: {node_id}")
    child = _apply_scoped(node.workflow, path[1:], update)
    valid_inputs = {item.id for item in child.interface.inputs}
    valid_outputs = {item.id for item in child.interface.outputs}
    replacement = node.model_copy(
        update={
            "workflow": child,
            "bindings": {
                key: value for key, value in node.bindings.items() if key in valid_inputs
            },
        }
    )
    edges = [
        edge
        for edge in graph.edges
        if not (
            edge.target_node == node_id
            and edge.target_input is not None
            and edge.target_input not in valid_inputs
        )
        and not (
            edge.source_node == node_id
            and isinstance(edge, ColumnEdge)
            and edge.source_output not in valid_outputs
        )
    ]
    return graph.model_copy(
        update={"nodes": _replace_node_list(graph, node_id, replacement), "edges": edges}
    )


def _apply_local(graph: GraphState, operation: WorkflowDraftOperation) -> GraphState:
    if isinstance(operation, CreateToolNodeOperation):
        _ensure_new_node(graph, operation.node_id)
        node = ToolNodeState(
            type="tool",
            id=operation.node_id,
            name=operation.name,
            tool_name=operation.tool_name,
            position=operation.position,
            parameters=operation.parameters,
        )
        return graph.model_copy(update={"nodes": [*graph.nodes, node]})
    if isinstance(operation, CreateWorkflowNodeOperation):
        _ensure_new_node(graph, operation.node_id)
        node = WorkflowNodeState(
            type="workflow",
            id=operation.node_id,
            name=operation.name,
            position=operation.position,
            workflow=operation.workflow,
            bindings=operation.bindings,
            source=operation.source,
        )
        return graph.model_copy(update={"nodes": [*graph.nodes, node]})
    if isinstance(operation, DeleteNodeOperation):
        _require_node(graph, operation.node_id)
        interface = graph.interface.model_copy(
            update={
                "inputs": [
                    port
                    for port in graph.interface.inputs
                    if all(target.node != operation.node_id for target in port.targets)
                ],
                "outputs": [
                    port
                    for port in graph.interface.outputs
                    if port.source.node != operation.node_id
                ],
            }
        )
        return graph.model_copy(
            update={
                "nodes": [node for node in graph.nodes if node.id != operation.node_id],
                "edges": [
                    edge
                    for edge in graph.edges
                    if edge.source_node != operation.node_id
                    and edge.target_node != operation.node_id
                ],
                "interface": interface,
            }
        )
    if isinstance(operation, RenameNodeOperation):
        node = _require_node(graph, operation.node_id)
        return _replace_node(graph, node.model_copy(update={"name": operation.name}))
    if isinstance(operation, UpdateToolParametersOperation):
        node = _require_node(graph, operation.node_id)
        if not isinstance(node, ToolNodeState):
            _raise("node_not_tool", f"Node is not a tool: {operation.node_id}")
        return _replace_node(
            graph,
            node.model_copy(
                update={"parameters": {**node.parameters, **operation.parameters}},
                deep=True,
            ),
        )
    if isinstance(operation, SetNodeEnabledOperation):
        node = _require_node(graph, operation.node_id)
        return _replace_node(graph, node.model_copy(update={"enabled": operation.enabled}))
    if isinstance(operation, MoveNodeOperation):
        node = _require_node(graph, operation.node_id)
        return _replace_node(graph, node.model_copy(update={"position": operation.position}))
    if isinstance(operation, MoveNodesOperation):
        positions = {move.node_id: move.position for move in operation.moves}
        if len(positions) != len(operation.moves):
            _raise("duplicate_move_node_id", "A node appears more than once in the move")
        for node_id in positions:
            _require_node(graph, node_id)
        return graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(update={"position": positions[node.id]})
                    if node.id in positions
                    else node
                    for node in graph.nodes
                ]
            }
        )
    if isinstance(operation, ExposeWorkflowInputOperation):
        inputs = [
            operation.input if item.id == operation.input.id else item
            for item in graph.interface.inputs
        ]
        if not any(item.id == operation.input.id for item in graph.interface.inputs):
            inputs.append(operation.input)
        return graph.model_copy(
            update={"interface": graph.interface.model_copy(update={"inputs": inputs})}
        )
    if isinstance(operation, DeleteWorkflowInputOperation):
        if not any(item.id == operation.input_id for item in graph.interface.inputs):
            _raise("missing_workflow_input", f"Workflow input not found: {operation.input_id}")
        return graph.model_copy(
            update={
                "interface": graph.interface.model_copy(
                    update={
                        "inputs": [
                            item
                            for item in graph.interface.inputs
                            if item.id != operation.input_id
                        ]
                    }
                )
            }
        )
    if isinstance(operation, ExposeWorkflowOutputOperation):
        outputs = [
            operation.output if item.id == operation.output.id else item
            for item in graph.interface.outputs
        ]
        if not any(item.id == operation.output.id for item in graph.interface.outputs):
            outputs.append(operation.output)
        return graph.model_copy(
            update={"interface": graph.interface.model_copy(update={"outputs": outputs})}
        )
    if isinstance(operation, DeleteWorkflowOutputOperation):
        if not any(item.id == operation.output_id for item in graph.interface.outputs):
            _raise(
                "missing_workflow_output", f"Workflow output not found: {operation.output_id}"
            )
        return graph.model_copy(
            update={
                "interface": graph.interface.model_copy(
                    update={
                        "outputs": [
                            item
                            for item in graph.interface.outputs
                            if item.id != operation.output_id
                        ]
                    }
                )
            }
        )
    if isinstance(operation, ConnectColumnEdgeOperation):
        return _connect_column(graph, operation)
    if isinstance(operation, ConnectDataFrameEdgeOperation):
        return _connect_dataframe(graph, operation)
    if isinstance(operation, DeleteEdgeOperation):
        if not any(edge.id == operation.edge_id for edge in graph.edges):
            _raise("missing_edge", f"Edge not found: {operation.edge_id}")
        return graph.model_copy(
            update={"edges": [edge for edge in graph.edges if edge.id != operation.edge_id]}
        )
    if isinstance(operation, DetachWorkflowSourceOperation):
        node = _require_node(graph, operation.node_id)
        if not isinstance(node, WorkflowNodeState):
            _raise("node_not_workflow", f"Node is not a workflow: {operation.node_id}")
        return _replace_node(graph, node.model_copy(update={"source": None}))
    _raise("unknown_operation", f"Unsupported operation: {operation!r}")


def _connect_column(
    graph: GraphState, operation: ConnectColumnEdgeOperation
) -> GraphState:
    _validate_connection_nodes(graph, operation.source_node, operation.target_node)
    edge_id = operation.edge_id or f"edge-{uuid4().hex}"
    replacement = {
        edge.id
        for edge in graph.edges
        if isinstance(edge, ColumnEdge)
        and edge.target_node == operation.target_node
        and edge.target_input == operation.target_input
    }
    _ensure_edge_id(graph, edge_id, replacement)
    edge = ColumnEdge(
        type="column",
        id=edge_id,
        source_node=operation.source_node,
        source_output=operation.source_output,
        target_node=operation.target_node,
        target_input=operation.target_input,
    )
    return graph.model_copy(
        update={"edges": [item for item in graph.edges if item.id not in replacement] + [edge]}
    )


def _connect_dataframe(
    graph: GraphState, operation: ConnectDataFrameEdgeOperation
) -> GraphState:
    _validate_connection_nodes(graph, operation.source_node, operation.target_node)
    edge_id = operation.edge_id or f"edge-{uuid4().hex}"
    replacement = {
        edge.id
        for edge in graph.edges
        if isinstance(edge, DataFrameEdge)
        and edge.target_node == operation.target_node
        and edge.target_position == operation.target_position
        and edge.target_input == operation.target_input
    }
    _ensure_edge_id(graph, edge_id, replacement)
    edge = DataFrameEdge(
        type="dataframe",
        id=edge_id,
        source_node=operation.source_node,
        target_node=operation.target_node,
        target_position=operation.target_position,
        target_input=operation.target_input,
    )
    return graph.model_copy(
        update={"edges": [item for item in graph.edges if item.id not in replacement] + [edge]}
    )


def _validate_tool_targets(
    graph: GraphState,
    get_tool_metadata: Callable[[str], ToolMetadata | None],
) -> None:
    node_by_id = {node.id: node for node in graph.nodes}
    for input_port in graph.interface.inputs:
        for target in input_port.targets:
            node = node_by_id[target.node]
            if isinstance(node, WorkflowNodeState):
                continue
            metadata = get_tool_metadata(node.tool_name)
            if metadata is None:
                _raise("missing_tool", f"Tool metadata not found: {node.tool_name}")
            if target.port.kind == "field" and target.port.name not in metadata.inputs:
                _raise(
                    "missing_workflow_input_target",
                    f"Input target not found on {metadata.name}: {target.port.name}",
                )
    for output in graph.interface.outputs:
        node = node_by_id[output.source.node]
        if isinstance(node, WorkflowNodeState):
            continue
        metadata = get_tool_metadata(node.tool_name)
        if metadata is None:
            _raise("missing_tool", f"Tool metadata not found: {node.tool_name}")
        if (
            output.source.column not in metadata.outputs
            and not metadata.dynamic_outputs
            and metadata.outputs.get("_passthrough") is not True
        ):
            _raise(
                "missing_workflow_output_target",
                f"Output target not found on {metadata.name}: {output.source.column}",
            )
    for node in graph.nodes:
        if isinstance(node, WorkflowNodeState):
            _validate_tool_targets(node.workflow, get_tool_metadata)


def _replace_node(graph: GraphState, replacement: ToolNodeState | WorkflowNodeState) -> GraphState:
    _require_node(graph, replacement.id)
    return graph.model_copy(
        update={"nodes": _replace_node_list(graph, replacement.id, replacement)}
    )


def _replace_node_list(
    graph: GraphState,
    node_id: str,
    replacement: ToolNodeState | WorkflowNodeState,
) -> list[ToolNodeState | WorkflowNodeState]:
    return [replacement if node.id == node_id else node for node in graph.nodes]


def _require_node(graph: GraphState, node_id: str) -> ToolNodeState | WorkflowNodeState:
    for node in graph.nodes:
        if node.id == node_id:
            return cast(ToolNodeState | WorkflowNodeState, node)
    _raise("missing_node", f"Node not found: {node_id}")


def _ensure_new_node(graph: GraphState, node_id: str) -> None:
    if any(node.id == node_id for node in graph.nodes):
        _raise("duplicate_node_id", f"Node already exists: {node_id}")


def _validate_connection_nodes(graph: GraphState, source: str, target: str) -> None:
    _require_node(graph, source)
    _require_node(graph, target)
    if source == target:
        _raise("self_connection", f"Cannot connect node to itself: {source}")


def _ensure_edge_id(graph: GraphState, edge_id: str, replacement: set[str]) -> None:
    if any(edge.id == edge_id and edge.id not in replacement for edge in graph.edges):
        _raise("duplicate_edge_id", f"Edge already exists: {edge_id}")


def _raise(code: str, detail: str) -> NoReturn:
    raise WorkflowDraftOperationError(operation_index=-1, code=code, detail=detail)
