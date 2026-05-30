"""Tests for pure workflow draft operation transforms."""

from __future__ import annotations

import pytest

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
    MoveNodeOperation,
    RenameNodeOperation,
    SetNodeEnabledOperation,
    UpdateNodeParametersOperation,
)
from bioimageflow_server.services.workflow_draft_operations import (
    WorkflowDraftOperationError,
    apply_workflow_draft_operations,
)


def _node(node_id: str, **overrides: object) -> NodeState:
    values = {
        "id": node_id,
        "name": node_id,
        "tool_name": "Tool",
        "position": (0, 0),
        "parameters": {"keep": "original"},
        "resources": {"cpu": 2},
        "output_templates": {"out": "{id}.csv"},
        "enabled": True,
        "collapsed": True,
        "published_inputs": [
            PublishedInput(
                name="image",
                internal_node_id="inner",
                internal_field="image",
                kind="input",
            )
        ],
        "published_outputs": [
            PublishedOutput(
                name="mask",
                internal_node_id="inner",
                internal_output="mask",
            )
        ],
        "sub_workflow_readonly_reason": "read-only",
    }
    values.update(overrides)
    return NodeState(**values)


def _graph() -> GraphState:
    return GraphState(
        nodes=[
            _node("a", parameters={"alpha": 1, "keep": "a"}),
            _node("b", parameters={"beta": 2, "keep": "b"}, enabled=False),
            _node("c"),
        ],
        edges=[
            ColumnRefEdge(
                id="a-to-b-image",
                source_node="a",
                target_node="b",
                source_output="mask",
                target_input="image",
            ),
            PositionalEdge(
                id="a-to-c-pos-0",
                source_node="a",
                target_node="c",
                positional_index=0,
            ),
        ],
        published_inputs=[
            PublishedInput(
                name="root_input",
                internal_node_id="a",
                internal_field="image",
                kind="input",
            )
        ],
        published_outputs=[
            PublishedOutput(
                name="root_output",
                internal_node_id="c",
                internal_output="table",
            )
        ],
    )


def _apply(*operations: object, graph: GraphState | None = None) -> GraphState:
    return apply_workflow_draft_operations(graph or _graph(), list(operations))


def test_create_node_adds_node_and_preserves_unrelated_graph_fields() -> None:
    graph = _graph()

    result = _apply(
        CreateNodeOperation(
            node_id="blur_1",
            tool_name="GaussianBlur",
            name="Blur",
            position=(10, 20),
            parameters={"sigma": 2},
        ),
        graph=graph,
    )

    assert [node.id for node in result.nodes] == ["a", "b", "c", "blur_1"]
    created = result.nodes[-1]
    assert created.name == "Blur"
    assert created.tool_name == "GaussianBlur"
    assert created.position == (10, 20)
    assert created.parameters == {"sigma": 2}
    assert created.enabled is True
    assert result.published_inputs == graph.published_inputs
    assert result.published_outputs == graph.published_outputs
    assert graph.nodes == _graph().nodes


def test_delete_node_removes_incident_edges_only() -> None:
    result = _apply(DeleteNodeOperation(node_id="a"))

    assert [node.id for node in result.nodes] == ["b", "c"]
    assert result.edges == []


def test_node_field_operations_preserve_unrelated_node_fields() -> None:
    result = _apply(
        RenameNodeOperation(node_id="a", name="Renamed"),
        UpdateNodeParametersOperation(
            node_id="a",
            parameters={"alpha": 3, "new": True},
        ),
        SetNodeEnabledOperation(node_id="a", enabled=False),
        MoveNodeOperation(node_id="a", position=(50, 75)),
    )

    node = result.nodes[0]
    assert node.name == "Renamed"
    assert node.parameters == {"alpha": 3, "keep": "a", "new": True}
    assert node.enabled is False
    assert node.position == (50, 75)
    assert node.resources == {"cpu": 2}
    assert node.output_templates == {"out": "{id}.csv"}
    assert node.collapsed is True
    assert node.published_inputs
    assert node.published_outputs
    assert node.sub_workflow_readonly_reason == "read-only"


def test_connect_column_ref_replaces_target_input_edge_and_generates_edge_id() -> None:
    result = _apply(
        ConnectColumnRefOperation(
            source_node="c",
            target_node="b",
            source_output="labels",
            target_input="image",
        )
    )

    column_edges = [edge for edge in result.edges if isinstance(edge, ColumnRefEdge)]
    assert column_edges == [
        ColumnRefEdge(
            id="e-c-labels-b-image",
            source_node="c",
            target_node="b",
            source_output="labels",
            target_input="image",
        )
    ]
    assert [edge.id for edge in result.edges if isinstance(edge, PositionalEdge)] == [
        "a-to-c-pos-0"
    ]


def test_connect_positional_replaces_target_index_edge() -> None:
    result = _apply(
        ConnectPositionalOperation(
            source_node="b",
            target_node="c",
            positional_index=0,
            edge_id="custom-pos",
        )
    )

    positional_edges = [edge for edge in result.edges if isinstance(edge, PositionalEdge)]
    assert positional_edges == [
        PositionalEdge(
            id="custom-pos",
            source_node="b",
            target_node="c",
            positional_index=0,
        )
    ]


def test_delete_edge_removes_edge_by_id() -> None:
    result = _apply(DeleteEdgeOperation(edge_id="a-to-b-image"))

    assert [edge.id for edge in result.edges] == ["a-to-c-pos-0"]


@pytest.mark.parametrize(
    ("operation", "code"),
    [
        (
            CreateNodeOperation(
                node_id="a",
                tool_name="Tool",
                name="Duplicate",
                position=(0, 0),
                parameters={},
            ),
            "duplicate_node_id",
        ),
        (DeleteNodeOperation(node_id="missing"), "missing_node"),
        (RenameNodeOperation(node_id="missing", name="Missing"), "missing_node"),
        (
            ConnectColumnRefOperation(
                source_node="missing",
                target_node="b",
                source_output="out",
                target_input="image",
            ),
            "missing_node",
        ),
        (
            ConnectColumnRefOperation(
                source_node="a",
                target_node="a",
                source_output="out",
                target_input="image",
            ),
            "self_connection",
        ),
        (DeleteEdgeOperation(edge_id="missing"), "missing_edge"),
    ],
)
def test_operation_errors_include_operation_index_and_code(
    operation: object,
    code: str,
) -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _apply(RenameNodeOperation(node_id="b", name="Changed"), operation)

    assert exc_info.value.operation_index == 1
    assert exc_info.value.code == code


def test_failed_batch_is_atomic() -> None:
    graph = _graph()

    with pytest.raises(WorkflowDraftOperationError):
        _apply(
            RenameNodeOperation(node_id="a", name="Changed"),
            DeleteEdgeOperation(edge_id="missing"),
            graph=graph,
        )

    assert graph == _graph()


def test_connect_rejects_duplicate_edge_id_after_replacement_scope() -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _apply(
            ConnectColumnRefOperation(
                source_node="c",
                target_node="b",
                source_output="labels",
                target_input="image",
                edge_id="a-to-c-pos-0",
            )
        )

    assert exc_info.value.operation_index == 0
    assert exc_info.value.code == "duplicate_edge_id"
