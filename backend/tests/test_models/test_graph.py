"""Tests for the graph Pydantic models."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    Edge,
    GraphState,
    NodeState,
    PositionalEdge,
    PublishedInput,
    PublishedOutput,
)


class TestNodeState:
    def test_full_construction(self) -> None:
        node = NodeState(
            id="node-1",
            name="My Node",
            tool_name="threshold",
            position=(100.0, 200.0),
            parameters={"value": 128},
            resources={"cpu": 2},
            output_templates={"out": "result_{name}.csv"},
            enabled=False,
            collapsed=True,
        )
        assert node.id == "node-1"
        assert node.name == "My Node"
        assert node.tool_name == "threshold"
        assert node.position == (100.0, 200.0)
        assert node.parameters == {"value": 128}
        assert node.resources == {"cpu": 2}
        assert node.output_templates == {"out": "result_{name}.csv"}
        assert node.enabled is False
        assert node.collapsed is True

    def test_defaults(self) -> None:
        node = NodeState(
            id="node-2",
            name="Node",
            tool_name="blur",
            position=(0.0, 0.0),
            parameters={},
        )
        assert node.resources == {}
        assert node.output_templates == {}
        assert node.enabled is True
        assert node.collapsed is False
        assert node.sub_workflow is None
        assert node.published_inputs == []
        assert node.published_outputs == []
        assert node.sub_workflow_readonly_reason is None

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            NodeState()  # type: ignore[call-arg]

    def test_roundtrip(self) -> None:
        data: dict[str, Any] = {
            "id": "node-3",
            "name": "Test",
            "tool_name": "crop",
            "position": [50.5, 75.5],
            "parameters": {"x": 10, "y": 20},
        }
        node = NodeState.model_validate(data)
        dumped = json.loads(node.model_dump_json())
        node2 = NodeState.model_validate(dumped)
        assert node2 == node

    def test_sub_workflow_roundtrip_preserves_nested_graph(self) -> None:
        data: dict[str, Any] = {
            "id": "outer",
            "name": "Outer",
            "tool_name": "__sub_workflow__",
            "position": [10, 20],
            "parameters": {"image": "/tmp/input.tif"},
            "sub_workflow": {
                "nodes": [
                    {
                        "id": "inner",
                        "name": "Inner",
                        "tool_name": "segment",
                        "position": [1, 2],
                        "parameters": {"diameter": 30},
                        "resources": {"cpu": 2},
                        "output_templates": {"mask": "mask.tif"},
                        "enabled": False,
                        "collapsed": True,
                    },
                ],
                "edges": [
                    {
                        "type": "positional",
                        "id": "pos",
                        "source_node": "inner",
                        "target_node": "inner",
                        "positional_index": 0,
                    },
                ],
            },
            "published_inputs": [
                {
                    "name": "image",
                    "internal_node_id": "inner",
                    "internal_field": "input_image",
                    "kind": "input",
                    "schema": {"type": "Path"},
                    "default": None,
                },
            ],
            "published_outputs": [
                {
                    "name": "mask",
                    "internal_node_id": "inner",
                    "internal_output": "mask",
                    "schema": {"type": "Path"},
                },
            ],
        }

        node = NodeState.model_validate(data)
        dumped = json.loads(node.model_dump_json())
        restored = NodeState.model_validate(dumped)

        assert restored == node
        assert restored.sub_workflow is not None
        assert restored.sub_workflow.nodes[0].resources == {"cpu": 2}
        assert isinstance(restored.sub_workflow.edges[0], PositionalEdge)

    def test_class_based_sub_workflow_readonly_metadata(self) -> None:
        node = NodeState(
            id="outer",
            name="Outer",
            tool_name="__sub_workflow__",
            position=(0, 0),
            parameters={},
            sub_workflow_readonly_reason="Class-based sub-workflow has no editable graph data.",
            published_inputs=[
                PublishedInput(
                    name="image",
                    internal_node_id="",
                    internal_field="image",
                    kind="input",
                    schema={"type": "Path"},
                ),
            ],
            published_outputs=[
                PublishedOutput(
                    name="mask",
                    internal_node_id="",
                    internal_output="mask",
                    schema={"type": "Path"},
                ),
            ],
        )

        dumped = node.model_dump(mode="json")
        assert dumped["sub_workflow"] is None
        assert dumped["sub_workflow_readonly_reason"].startswith("Class-based")


class TestColumnRefEdge:
    def test_construction(self) -> None:
        edge = ColumnRefEdge(
            id="edge-1",
            source_node="n1",
            target_node="n2",
            source_output="out",
            target_input="in",
        )
        assert edge.type == "column_ref"
        assert edge.id == "edge-1"
        assert edge.source_node == "n1"
        assert edge.target_node == "n2"
        assert edge.source_output == "out"
        assert edge.target_input == "in"


class TestPositionalEdge:
    def test_construction(self) -> None:
        edge = PositionalEdge(
            id="edge-2",
            source_node="n1",
            target_node="n3",
            positional_index=0,
        )
        assert edge.type == "positional"
        assert edge.id == "edge-2"
        assert edge.positional_index == 0


class TestEdgeUnion:
    def test_dispatch_column_ref(self) -> None:
        from pydantic import TypeAdapter

        adapter = TypeAdapter(Edge)
        data = {
            "type": "column_ref",
            "id": "e1",
            "source_node": "a",
            "target_node": "b",
            "source_output": "out",
            "target_input": "in",
        }
        edge = adapter.validate_python(data)
        assert isinstance(edge, ColumnRefEdge)

    def test_dispatch_positional(self) -> None:
        from pydantic import TypeAdapter

        adapter = TypeAdapter(Edge)
        data = {
            "type": "positional",
            "id": "e2",
            "source_node": "a",
            "target_node": "b",
            "positional_index": 1,
        }
        edge = adapter.validate_python(data)
        assert isinstance(edge, PositionalEdge)

    def test_rejection_invalid_type(self) -> None:
        from pydantic import TypeAdapter

        adapter = TypeAdapter(Edge)
        with pytest.raises(ValidationError):
            adapter.validate_python({"type": "unknown", "id": "x"})

    def test_roundtrip(self) -> None:
        from pydantic import TypeAdapter

        adapter = TypeAdapter(Edge)
        data = {
            "type": "column_ref",
            "id": "e1",
            "source_node": "a",
            "target_node": "b",
            "source_output": "out",
            "target_input": "in",
        }
        edge = adapter.validate_python(data)
        dumped = json.loads(adapter.dump_json(edge))
        edge2 = adapter.validate_python(dumped)
        assert edge == edge2


class TestGraphState:
    def test_empty(self) -> None:
        g = GraphState(nodes=[], edges=[])
        assert g.nodes == []
        assert g.edges == []

    def test_mixed_edges(self) -> None:
        node = NodeState(
            id="n1",
            name="N",
            tool_name="t",
            position=(0, 0),
            parameters={},
        )
        col_edge = ColumnRefEdge(
            id="e1",
            source_node="n1",
            target_node="n2",
            source_output="o",
            target_input="i",
        )
        pos_edge = PositionalEdge(
            id="e2",
            source_node="n1",
            target_node="n2",
            positional_index=0,
        )
        g = GraphState(nodes=[node], edges=[col_edge, pos_edge])
        assert len(g.edges) == 2
        assert isinstance(g.edges[0], ColumnRefEdge)
        assert isinstance(g.edges[1], PositionalEdge)

    def test_roundtrip(self) -> None:
        node = NodeState(
            id="n1",
            name="N",
            tool_name="t",
            position=(0, 0),
            parameters={"k": "v"},
        )
        edge = ColumnRefEdge(
            id="e1",
            source_node="n1",
            target_node="n2",
            source_output="o",
            target_input="i",
        )
        g = GraphState(nodes=[node], edges=[edge])
        dumped = json.loads(g.model_dump_json())
        g2 = GraphState.model_validate(dumped)
        assert g2.nodes[0].id == "n1"
        assert isinstance(g2.edges[0], ColumnRefEdge)
