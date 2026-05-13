"""Tests for semantic graph proposal placement."""

from bioimageflow_server.models.graph import ColumnRefEdge, GraphState, NodeState
from bioimageflow_server.models.graph_proposals import (
    AfterNodePlacement,
    BetweenNodesPlacement,
    EndOfBranchPlacement,
)
from bioimageflow_server.services.graph_layout import place_node


def _node(node_id: str, x: float, y: float) -> NodeState:
    return NodeState(
        id=node_id,
        name=node_id,
        tool_name="Tool",
        position=(x, y),
        parameters={},
    )


def test_end_of_branch_uses_terminal_descendant() -> None:
    graph = GraphState(
        nodes=[_node("root", 0, 0), _node("mid", 280, 0), _node("leaf", 560, 0)],
        edges=[
            ColumnRefEdge(
                id="e1",
                source_node="root",
                target_node="mid",
                source_output="out",
                target_input="input",
            ),
            ColumnRefEdge(
                id="e2",
                source_node="mid",
                target_node="leaf",
                source_output="out",
                target_input="input",
            ),
        ],
    )

    assert place_node(graph, EndOfBranchPlacement(node_id="root")) == (840, 0)


def test_collision_avoidance_offsets_down_by_vertical_gap() -> None:
    graph = GraphState(
        nodes=[_node("source", 0, 0), _node("occupied", 280, 0)],
        edges=[],
    )

    assert place_node(graph, AfterNodePlacement(node_id="source")) == (280, 120)


def test_between_nodes_places_midpoint_then_avoids_collision() -> None:
    graph = GraphState(
        nodes=[_node("a", 0, 0), _node("b", 560, 0), _node("occupied", 280, 0)],
        edges=[],
    )

    assert place_node(
        graph,
        BetweenNodesPlacement(source_node="a", target_node="b"),
    ) == (280, 120)


def test_missing_semantic_target_falls_back_right_of_rightmost() -> None:
    graph = GraphState(nodes=[_node("a", 100, 0), _node("b", 450, 80)], edges=[])

    assert place_node(graph, AfterNodePlacement(node_id="missing")) == (730, 80)
