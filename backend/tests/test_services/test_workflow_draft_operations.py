"""Tests for atomic semantic recursive-workflow mutations."""

from __future__ import annotations

import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.workflow_draft_operations import (
    ConnectColumnEdgeOperation,
    ConnectDataFrameEdgeOperation,
    CreateToolNodeOperation,
    CreateWorkflowNodeOperation,
    DeleteWorkflowInputOperation,
    DetachWorkflowSourceOperation,
    ExposeWorkflowInputOperation,
    MoveNodeOperation,
    WorkflowDraftOperationScope,
)
from bioimageflow_server.services.workflow_draft_operations import (
    WorkflowDraftOperationError,
    apply_workflow_draft_operations,
)


def _graph(name: str = "root") -> GraphState:
    return GraphState.model_validate(
        {
            "schema_version": 1,
            "name": name,
            "display_name": name.title(),
            "nodes": [],
            "edges": [],
            "interface": {"inputs": [], "outputs": []},
            "config": {
                "storage_path": "./bif_data",
                "engine": "direct",
                "execution": "parallel",
            },
        }
    )


def _tool(node_id: str) -> dict[str, object]:
    return {
        "type": "tool",
        "id": node_id,
        "name": node_id.title(),
        "tool_name": "Tool",
        "position": [0, 0],
        "parameters": {},
    }


def test_create_tool_and_workflow_nodes_use_explicit_discriminators() -> None:
    graph = apply_workflow_draft_operations(
        _graph(),
        [
            CreateToolNodeOperation(
                type="create_tool_node",
                node_id="tool",
                tool_name="Tool",
                name="Tool",
                position=(0, 0),
            ),
            CreateWorkflowNodeOperation(
                type="create_workflow_node",
                node_id="child",
                name="Child",
                position=(100, 0),
                workflow=_graph("child"),
            ),
        ],
    )

    assert [node.type for node in graph.nodes] == ["tool", "workflow"]


def test_scoped_operations_address_structural_workflow_node_ids() -> None:
    child = _graph("child").model_copy(
        update={"nodes": [GraphState.model_validate({
            **_graph("holder").model_dump(mode="json", by_alias=True),
            "nodes": [_tool("inner")],
        }).nodes[0]]}
    )
    root = GraphState.model_validate(
        {
            **_graph().model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "child-node",
                    "name": "Editable label",
                    "workflow": child.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                }
            ],
        }
    )

    result = apply_workflow_draft_operations(
        root,
        [
            MoveNodeOperation(
                type="move_node",
                scope=WorkflowDraftOperationScope(workflow_path=["child-node"]),
                node_id="inner",
                position=(50, 75),
            )
        ],
    )

    assert result.nodes[0].workflow.nodes[0].position == (50, 75)  # type: ignore[union-attr]


def test_expose_input_and_connect_edges_by_stable_id() -> None:
    graph = GraphState.model_validate(
        {
            **_graph().model_dump(mode="json", by_alias=True),
            "nodes": [_tool("source"), _tool("target")],
        }
    )
    result = apply_workflow_draft_operations(
        graph,
        [
            ExposeWorkflowInputOperation.model_validate(
                {
                    "type": "expose_workflow_input",
                    "input": {
                        "id": "input-value",
                        "name": "Value",
                        "kind": "field",
                        "targets": [
                            {
                                "node": "target",
                                "port": {"kind": "field", "name": "value"},
                            }
                        ],
                    },
                }
            ),
            ConnectColumnEdgeOperation(
                type="connect_column_edge",
                source_node="source",
                source_output="value",
                target_node="target",
                target_input="value",
                edge_id="column-edge",
            ),
            ConnectDataFrameEdgeOperation(
                type="connect_dataframe_edge",
                source_node="source",
                target_node="target",
                target_position=0,
                edge_id="frame-edge",
            ),
        ],
    )

    assert result.interface.inputs[0].id == "input-value"
    assert [edge.type for edge in result.edges] == ["column", "dataframe"]


def test_deleting_nested_input_prunes_parent_edge_and_binding_atomically() -> None:
    child = GraphState.model_validate(
        {
            **_graph("child").model_dump(mode="json", by_alias=True),
            "interface": {
                "inputs": [
                    {
                        "id": "input-value",
                        "name": "Value",
                        "kind": "field",
                        "targets": [],
                    }
                ],
                "outputs": [],
            },
        }
    )
    root = GraphState.model_validate(
        {
            **_graph().model_dump(mode="json", by_alias=True),
            "nodes": [
                _tool("source"),
                {
                    "type": "workflow",
                    "id": "child",
                    "name": "Child",
                    "workflow": child.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                },
            ],
            "edges": [
                {
                    "type": "column",
                    "id": "edge",
                    "source_node": "source",
                    "source_output": "value",
                    "target_node": "child",
                    "target_input": "input-value",
                }
            ],
        }
    )

    result = apply_workflow_draft_operations(
        root,
        [
            DeleteWorkflowInputOperation(
                type="delete_workflow_input",
                scope=WorkflowDraftOperationScope(workflow_path=["child"]),
                input_id="input-value",
            )
        ],
    )

    assert result.nodes[1].workflow.interface.inputs == []  # type: ignore[union-attr]
    assert result.edges == []


def test_detach_source_changes_only_provenance() -> None:
    child = _graph("child")
    root = GraphState.model_validate(
        {
            **_graph().model_dump(mode="json", by_alias=True),
            "nodes": [
                {
                    "type": "workflow",
                    "id": "child",
                    "name": "Child",
                    "workflow": child.model_dump(mode="json", by_alias=True),
                    "bindings": {},
                    "position": [0, 0],
                    "source": {
                        "kind": "workspace",
                        "workflow_id": "saved-child",
                        "artifact_hash": "sha256:" + "a" * 64,
                    },
                }
            ],
        }
    )
    before = root.nodes[0].workflow  # type: ignore[union-attr]

    result = apply_workflow_draft_operations(
        root,
        [
            DetachWorkflowSourceOperation(
                type="detach_workflow_source", node_id="child"
            )
        ],
    )

    assert result.nodes[0].source is None  # type: ignore[union-attr]
    assert result.nodes[0].workflow == before  # type: ignore[union-attr]


def test_operation_batch_is_atomic_on_failure() -> None:
    graph = _graph()
    operations = [
        CreateToolNodeOperation(
            type="create_tool_node",
            node_id="tool",
            tool_name="Tool",
            name="Tool",
            position=(0, 0),
        ),
        CreateToolNodeOperation(
            type="create_tool_node",
            node_id="tool",
            tool_name="Tool",
            name="Duplicate",
            position=(0, 0),
        ),
    ]

    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        apply_workflow_draft_operations(graph, operations)

    assert exc_info.value.operation_index == 1
    assert graph.nodes == []
