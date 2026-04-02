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
