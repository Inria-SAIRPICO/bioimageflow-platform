"""Semantic placement helpers for graph proposal operations."""

from __future__ import annotations

from collections import deque

from bioimageflow_server.models.graph import GraphState, NodeState
from bioimageflow_server.models.graph_proposals import (
    AfterNodePlacement,
    BetweenNodesPlacement,
    EndOfBranchPlacement,
    GraphProposalPlacement,
)

HORIZONTAL_GAP = 280
VERTICAL_GAP = 120
NODE_WIDTH = 220
NODE_HEIGHT = 90


def place_node(
    graph: GraphState,
    placement: GraphProposalPlacement | None,
    *,
    horizontal_gap: float = HORIZONTAL_GAP,
    vertical_gap: float = VERTICAL_GAP,
    node_box: tuple[float, float] = (NODE_WIDTH, NODE_HEIGHT),
) -> tuple[float, float]:
    """Return a collision-free position for a proposed node."""

    if placement is None:
        return _avoid_collisions(
            _right_of_rightmost(graph, horizontal_gap),
            graph.nodes,
            vertical_gap=vertical_gap,
            node_box=node_box,
        )

    nodes_by_id = {node.id: node for node in graph.nodes}
    candidate: tuple[float, float] | None = None

    if isinstance(placement, AfterNodePlacement):
        anchor = nodes_by_id.get(placement.node_id)
        if anchor is not None:
            candidate = (anchor.position[0] + horizontal_gap, anchor.position[1])
    elif isinstance(placement, BetweenNodesPlacement):
        source = nodes_by_id.get(placement.source_node)
        target = nodes_by_id.get(placement.target_node)
        if source is not None and target is not None:
            candidate = (
                (source.position[0] + target.position[0]) / 2,
                (source.position[1] + target.position[1]) / 2,
            )
    elif isinstance(placement, EndOfBranchPlacement):
        terminal = _terminal_descendant(graph, placement.node_id)
        if terminal is not None:
            candidate = (
                terminal.position[0] + horizontal_gap,
                terminal.position[1],
            )

    if candidate is None:
        candidate = _right_of_rightmost(graph, horizontal_gap)

    return _avoid_collisions(
        candidate,
        graph.nodes,
        vertical_gap=vertical_gap,
        node_box=node_box,
    )


def _right_of_rightmost(
    graph: GraphState,
    horizontal_gap: float,
) -> tuple[float, float]:
    if not graph.nodes:
        return (0, 0)
    rightmost = max(graph.nodes, key=lambda node: (node.position[0], node.position[1]))
    return (rightmost.position[0] + horizontal_gap, rightmost.position[1])


def _terminal_descendant(graph: GraphState, node_id: str) -> NodeState | None:
    nodes_by_id = {node.id: node for node in graph.nodes}
    if node_id not in nodes_by_id:
        return None

    outgoing: dict[str, list[str]] = {}
    for edge in graph.edges:
        outgoing.setdefault(edge.source_node, []).append(edge.target_node)

    best = nodes_by_id[node_id]
    queue: deque[str] = deque(outgoing.get(node_id, []))
    seen = {node_id}
    while queue:
        current_id = queue.popleft()
        if current_id in seen:
            continue
        seen.add(current_id)
        current = nodes_by_id.get(current_id)
        if current is None:
            continue
        if current.position[0] > best.position[0]:
            best = current
        children = outgoing.get(current_id, [])
        if children:
            queue.extend(children)
        elif current.position[0] >= best.position[0]:
            best = current

    return best


def _avoid_collisions(
    candidate: tuple[float, float],
    nodes: list[NodeState],
    *,
    vertical_gap: float,
    node_box: tuple[float, float],
) -> tuple[float, float]:
    x, y = candidate
    while _collides((x, y), nodes, node_box=node_box):
        y += vertical_gap
    return (x, y)


def _collides(
    candidate: tuple[float, float],
    nodes: list[NodeState],
    *,
    node_box: tuple[float, float],
) -> bool:
    width, height = node_box
    x, y = candidate
    for node in nodes:
        node_x, node_y = node.position
        if abs(x - node_x) < width and abs(y - node_y) < height:
            return True
    return False
