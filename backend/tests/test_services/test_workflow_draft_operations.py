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
from bioimageflow_server.models.tools import (
    InputFieldSchema,
    OutputFieldSchema,
    ToolMetadata,
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
    MoveNodesOperation,
    RenameNodeOperation,
    SetNodeEnabledOperation,
    SetPublishedInputOperation,
    SetPublishedOutputOperation,
    UpdateNodeParametersOperation,
)
from bioimageflow_server.services.workflow_draft_operations import (
    WorkflowDraftOperationError,
    apply_and_validate_workflow_draft_operations,
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


def _nested_graph() -> GraphState:
    return GraphState(
        nodes=[
            _node(
                "outer",
                sub_workflow=GraphState(
                    nodes=[
                        _node("a", position=(1, 1), parameters={"nested": True}),
                        _node(
                            "nested",
                            position=(2, 2),
                            sub_workflow=GraphState(
                                nodes=[_node("deep", position=(3, 3))],
                                edges=[],
                            ),
                            sub_workflow_readonly_reason=None,
                        ),
                        _node(
                            "read_only",
                            position=(4, 4),
                            sub_workflow=GraphState(nodes=[_node("leaf")], edges=[]),
                            sub_workflow_readonly_reason="locked",
                        ),
                    ],
                    edges=[],
                    published_inputs=[
                        PublishedInput(
                            name="nested_input",
                            internal_node_id="a",
                            internal_field="image",
                            kind="input",
                        )
                    ],
                ),
                sub_workflow_readonly_reason=None,
            ),
            _node("a", position=(9, 9)),
            _node("plain", position=(0, 0), sub_workflow_readonly_reason=None),
        ],
        edges=[],
        published_outputs=[
            PublishedOutput(
                name="root_output",
                internal_node_id="outer",
                internal_output="mask",
            )
        ],
    )


def _apply(*operations: object, graph: GraphState | None = None) -> GraphState:
    return apply_workflow_draft_operations(graph or _graph(), list(operations))


def _tool(
    name: str = "Tool",
    *,
    inputs: dict[str, InputFieldSchema] | None = None,
    outputs: dict[str, object] | None = None,
    dynamic_outputs: bool = False,
) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="test-package",
        package_version="1.0.0",
        tool_type="ProcessingTool",
        dynamic_outputs=dynamic_outputs,
        inputs=inputs
        or {
            "image": InputFieldSchema(
                type="ImageFile",
                required=True,
                connectable="by_default",
            ),
            "hidden": InputFieldSchema(
                type="str",
                required=False,
                connectable="never",
            ),
        },
        outputs=outputs or {"mask": OutputFieldSchema(type="ImageFile")},
    )


def _validated_apply(
    *operations: object,
    graph: GraphState | None = None,
    tools: dict[str, ToolMetadata] | None = None,
) -> GraphState:
    tool_map = tools if tools is not None else {"Tool": _tool()}
    return apply_and_validate_workflow_draft_operations(
        graph or _graph(),
        list(operations),
        get_tool_metadata=tool_map.get,
    )


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


def test_move_nodes_updates_multiple_positions_and_preserves_other_fields() -> None:
    graph = _graph()

    result = _apply(
        MoveNodesOperation(
            moves=[
                {"node_id": "a", "position": (100, 120)},
                {"node_id": "c", "position": (300, 120)},
            ],
        ),
        graph=graph,
    )

    assert [(node.id, node.position) for node in result.nodes] == [
        ("a", (100, 120)),
        ("b", (0, 0)),
        ("c", (300, 120)),
    ]
    assert result.nodes[0].parameters == graph.nodes[0].parameters
    assert result.nodes[0].resources == graph.nodes[0].resources
    assert result.nodes[0].output_templates == graph.nodes[0].output_templates
    assert result.nodes[0].collapsed == graph.nodes[0].collapsed
    assert result.edges == graph.edges
    assert result.published_inputs == graph.published_inputs
    assert result.published_outputs == graph.published_outputs
    assert graph == _graph()


@pytest.mark.parametrize(
    ("moves", "code"),
    [
        (
            [
                {"node_id": "a", "position": (10, 20)},
                {"node_id": "a", "position": (30, 40)},
            ],
            "duplicate_move_node_id",
        ),
        ([{"node_id": "missing", "position": (10, 20)}], "missing_node"),
    ],
)
def test_move_nodes_preflights_failures_atomically(
    moves: list[dict[str, object]],
    code: str,
) -> None:
    graph = _graph()

    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _apply(MoveNodesOperation(moves=moves), graph=graph)

    assert exc_info.value.code == code
    assert graph == _graph()


def test_scoped_move_node_updates_nested_graph_only() -> None:
    graph = _nested_graph()

    result = _apply(
        MoveNodeOperation(
            node_id="a",
            position=(100, 120),
            scope={"sub_workflow_path": ["outer"]},
        ),
        graph=graph,
    )

    outer = result.nodes[0]
    assert result.nodes[1].id == "a"
    assert result.nodes[1].position == (9, 9)
    assert outer.position == graph.nodes[0].position
    assert outer.sub_workflow is not None
    assert outer.sub_workflow.nodes[0].position == (100, 120)
    assert outer.sub_workflow.nodes[0].parameters == {"nested": True}
    assert outer.sub_workflow.published_inputs == graph.nodes[0].sub_workflow.published_inputs
    assert result.published_outputs == graph.published_outputs
    assert graph == _nested_graph()


def test_scoped_move_nodes_supports_deep_sub_workflow_path() -> None:
    result = _apply(
        MoveNodesOperation(
            moves=[{"node_id": "deep", "position": (500, 600)}],
            scope={"sub_workflow_path": ["outer", "nested"]},
        ),
        graph=_nested_graph(),
    )

    outer = result.nodes[0]
    assert outer.sub_workflow is not None
    nested = outer.sub_workflow.nodes[1]
    assert nested.sub_workflow is not None
    assert nested.sub_workflow.nodes[0].position == (500, 600)


@pytest.mark.parametrize(
    ("scope", "code"),
    [
        ({"sub_workflow_path": ["missing"]}, "missing_scope_node"),
        ({"sub_workflow_path": ["plain"]}, "missing_sub_workflow"),
        ({"sub_workflow_path": ["outer", "read_only"]}, "readonly_sub_workflow"),
        ({"sub_workflow_path": ["outer", "missing"]}, "missing_scope_node"),
    ],
)
def test_scoped_layout_rejects_invalid_scope_paths(
    scope: dict[str, list[str]],
    code: str,
) -> None:
    graph = _nested_graph()

    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _apply(MoveNodeOperation(node_id="a", position=(10, 20), scope=scope), graph=graph)

    assert exc_info.value.code == code
    assert graph == _nested_graph()


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


def test_set_published_input_adds_and_updates_by_internal_target() -> None:
    result = _apply(
        SetPublishedInputOperation(
            name="raw_image",
            internal_node_id="b",
            internal_field="image",
            kind="input",
            schema={"type": "ImageFile"},
            default="demo.tif",
        ),
        SetPublishedInputOperation(
            name="renamed_image",
            internal_node_id="b",
            internal_field="image",
            kind="input",
        ),
    )

    assert [item.name for item in result.published_inputs] == [
        "root_input",
        "renamed_image",
    ]
    item = result.published_inputs[1]
    assert item.internal_node_id == "b"
    assert item.internal_field == "image"
    assert item.schema_ == {"type": "ImageFile"}
    assert item.default == "demo.tif"
    assert result.nodes == _graph().nodes
    assert result.edges == _graph().edges


def test_set_published_output_adds_and_delete_operations_remove_by_name() -> None:
    result = _apply(
        SetPublishedOutputOperation(
            name="labels",
            internal_node_id="a",
            internal_output="mask",
            schema={"type": "ImageFile"},
        ),
        DeletePublishedInputOperation(name="root_input"),
        DeletePublishedOutputOperation(name="root_output"),
    )

    assert result.published_inputs == []
    assert [item.name for item in result.published_outputs] == ["labels"]
    assert result.published_outputs[0].schema_ == {"type": "ImageFile"}


def test_metadata_validation_accepts_valid_create_then_publish_batch() -> None:
    result = _validated_apply(
        CreateNodeOperation(
            node_id="created",
            tool_name="Tool",
            name="Created",
            position=(10, 20),
            parameters={},
        ),
        SetPublishedInputOperation(
            name="raw_image",
            internal_node_id="created",
            internal_field="image",
            kind="input",
            schema={"type": "ImageFile"},
        ),
        SetPublishedOutputOperation(
            name="mask",
            internal_node_id="created",
            internal_output="mask",
            schema={"type": "ImageFile"},
        ),
    )

    assert result.published_inputs[-1].name == "raw_image"
    assert result.published_outputs[-1].name == "mask"


def test_metadata_validation_rejects_unknown_input_target_with_operation_index() -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _validated_apply(
            CreateNodeOperation(
                node_id="created",
                tool_name="Tool",
                name="Created",
                position=(10, 20),
                parameters={},
            ),
            SetPublishedInputOperation(
                name="typo",
                internal_node_id="created",
                internal_field="iamge",
                kind="input",
                schema={"type": "ImageFile"},
            ),
        )

    assert exc_info.value.operation_index == 1
    assert exc_info.value.code == "missing_published_input_target"


def test_metadata_validation_rejects_unknown_static_output_target() -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _validated_apply(
            SetPublishedOutputOperation(
                name="labels",
                internal_node_id="a",
                internal_output="labels",
                schema={"type": "ImageFile"},
            )
        )

    assert exc_info.value.operation_index == 0
    assert exc_info.value.code == "missing_published_output_target"


def test_metadata_validation_accepts_dynamic_and_passthrough_outputs() -> None:
    dynamic_result = _validated_apply(
        SetPublishedOutputOperation(
            name="dynamic_label",
            internal_node_id="a",
            internal_output="label_7",
            schema={"type": "ImageFile"},
        ),
        tools={"Tool": _tool(dynamic_outputs=True, outputs={})},
    )
    passthrough_result = _validated_apply(
        SetPublishedOutputOperation(
            name="passthrough_label",
            internal_node_id="a",
            internal_output="label_8",
            schema={"type": "ImageFile"},
        ),
        tools={"Tool": _tool(outputs={"_passthrough": True})},
    )

    assert dynamic_result.published_outputs[-1].internal_output == "label_7"
    assert passthrough_result.published_outputs[-1].internal_output == "label_8"


def test_metadata_validation_does_not_treat_passthrough_marker_as_output() -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _validated_apply(
            SetPublishedOutputOperation(
                name="marker",
                internal_node_id="a",
                internal_output="_passthrough",
                schema={"type": "ImageFile"},
            ),
            tools={"Tool": _tool(outputs={"_passthrough": True})},
        )

    assert exc_info.value.code == "missing_published_output_target"


def test_metadata_validation_rejects_missing_tool_metadata_for_published_target() -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _validated_apply(
            SetPublishedInputOperation(
                name="image",
                internal_node_id="a",
                internal_field="image",
                kind="input",
                schema={"type": "ImageFile"},
            ),
            tools={},
        )

    assert exc_info.value.code == "missing_tool"


def test_metadata_validation_rejects_non_connectable_published_input() -> None:
    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _validated_apply(
            SetPublishedInputOperation(
                name="hidden",
                internal_node_id="a",
                internal_field="hidden",
                kind="input",
                schema={"type": "str"},
            )
        )

    assert exc_info.value.code == "published_input_not_connectable"


def test_metadata_validation_accepts_sub_workflow_node_published_pins() -> None:
    graph = GraphState(
        nodes=[
            _node(
                "outer",
                tool_name="__sub_workflow__",
                sub_workflow=GraphState(nodes=[_node("inner")], edges=[]),
                published_inputs=[
                    PublishedInput(
                        name="sub_image",
                        internal_node_id="inner",
                        internal_field="image",
                        kind="input",
                    )
                ],
                published_outputs=[
                    PublishedOutput(
                        name="sub_mask",
                        internal_node_id="inner",
                        internal_output="mask",
                    )
                ],
                sub_workflow_readonly_reason=None,
            )
        ],
        edges=[],
    )

    result = _validated_apply(
        SetPublishedInputOperation(
            name="root_image",
            internal_node_id="outer",
            internal_field="sub_image",
            kind="input",
            schema={"type": "ImageFile"},
        ),
        SetPublishedOutputOperation(
            name="root_mask",
            internal_node_id="outer",
            internal_output="sub_mask",
            schema={"type": "ImageFile"},
        ),
        graph=graph,
        tools={},
    )

    assert result.published_inputs[0].internal_field == "sub_image"
    assert result.published_outputs[0].internal_output == "sub_mask"


def test_metadata_validation_rejects_missing_sub_workflow_published_pin() -> None:
    graph = GraphState(
        nodes=[
            _node(
                "outer",
                tool_name="__sub_workflow__",
                sub_workflow=GraphState(nodes=[_node("inner")], edges=[]),
                published_outputs=[
                    PublishedOutput(
                        name="sub_mask",
                        internal_node_id="inner",
                        internal_output="mask",
                    )
                ],
                sub_workflow_readonly_reason=None,
            )
        ],
        edges=[],
    )

    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _validated_apply(
            SetPublishedOutputOperation(
                name="root_labels",
                internal_node_id="outer",
                internal_output="sub_labels",
                schema={"type": "ImageFile"},
            ),
            graph=graph,
            tools={},
        )

    assert exc_info.value.code == "missing_published_output_target"


def test_published_interface_operations_reject_duplicate_names_and_missing_targets() -> None:
    with pytest.raises(WorkflowDraftOperationError) as duplicate:
        _apply(
            SetPublishedInputOperation(
                name="root_output",
                internal_node_id="b",
                internal_field="image",
                kind="input",
                schema={"type": "ImageFile"},
            )
        )
    assert duplicate.value.code == "duplicate_published_name"

    with pytest.raises(WorkflowDraftOperationError) as missing_node:
        _apply(
            SetPublishedOutputOperation(
                name="missing",
                internal_node_id="missing",
                internal_output="out",
                schema={"type": "ImageFile"},
            )
        )
    assert missing_node.value.code == "missing_node"


def test_published_interface_operations_are_atomic() -> None:
    graph = _graph()

    with pytest.raises(WorkflowDraftOperationError) as exc_info:
        _apply(
            SetPublishedInputOperation(
                name="new_input",
                internal_node_id="b",
                internal_field="image",
                kind="input",
                schema={"type": "ImageFile"},
            ),
            DeletePublishedOutputOperation(name="missing_output"),
            graph=graph,
        )

    assert exc_info.value.operation_index == 1
    assert exc_info.value.code == "missing_published_output"
    assert graph == _graph()


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
