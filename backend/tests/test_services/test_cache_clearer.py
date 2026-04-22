"""Tests for :func:`bioimageflow_server.services.execution.clear_node_cache`."""

from __future__ import annotations

from pathlib import Path

import pytest

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
    PositionalEdge,
)
from bioimageflow_server.services.execution import clear_node_cache


def _node(id: str) -> NodeState:
    return NodeState(
        id=id,
        name=id,
        tool_name="tool",
        position=(0.0, 0.0),
        parameters={},
    )


def _edge(source: str, target: str, idx: int = 0) -> ColumnRefEdge:
    return ColumnRefEdge(
        id=f"{source}->{target}-{idx}",
        source_node=source,
        target_node=target,
        source_output="out",
        target_input="in",
    )


def _make_graph(nodes: list[str], edges: list[tuple[str, str]]) -> GraphState:
    return GraphState(
        nodes=[_node(n) for n in nodes],
        edges=[_edge(s, t, i) for i, (s, t) in enumerate(edges)],
    )


def test_clear_single_node_returns_unexecuted(tmp_path: Path) -> None:
    graph = _make_graph(["a"], [])
    result = clear_node_cache(["a"], graph, tmp_path)
    assert result["a"].status == "unexecuted"
    assert result["a"].cached is False


def test_clear_propagates_out_of_date_to_downstream(tmp_path: Path) -> None:
    # a -> b -> c
    graph = _make_graph(["a", "b", "c"], [("a", "b"), ("b", "c")])
    result = clear_node_cache(["a"], graph, tmp_path)
    assert result["a"].status == "unexecuted"
    assert result["b"].status == "out_of_date"
    assert result["c"].status == "out_of_date"


def test_clear_node_with_no_downstream(tmp_path: Path) -> None:
    graph = _make_graph(["a", "b"], [("a", "b")])
    result = clear_node_cache(["b"], graph, tmp_path)
    assert set(result.keys()) == {"b"}
    assert result["b"].status == "unexecuted"


def test_clear_multiple_nodes_shared_downstream(tmp_path: Path) -> None:
    # a -> c, b -> c
    graph = _make_graph(["a", "b", "c"], [("a", "c"), ("b", "c")])
    result = clear_node_cache(["a", "b"], graph, tmp_path)
    assert result["a"].status == "unexecuted"
    assert result["b"].status == "unexecuted"
    assert result["c"].status == "out_of_date"


def test_non_existent_node_id_is_skipped(tmp_path: Path) -> None:
    graph = _make_graph(["a"], [])
    result = clear_node_cache(["ghost"], graph, tmp_path)
    assert result == {}


def test_non_existent_cache_dir_is_idempotent(tmp_path: Path) -> None:
    graph = _make_graph(["a"], [])
    # tmp_path/data/a does not exist
    result = clear_node_cache(["a"], graph, tmp_path)
    assert result["a"].status == "unexecuted"


def test_cleared_node_takes_priority_over_out_of_date(tmp_path: Path) -> None:
    # a -> b. Clear both a and b: b should be "unexecuted", not "out_of_date".
    graph = _make_graph(["a", "b"], [("a", "b")])
    result = clear_node_cache(["a", "b"], graph, tmp_path)
    assert result["a"].status == "unexecuted"
    assert result["b"].status == "unexecuted"


def test_clear_removes_cache_directory(tmp_path: Path) -> None:
    graph = _make_graph(["a"], [])
    node_dir = tmp_path / "data" / "a"
    node_dir.mkdir(parents=True)
    (node_dir / "cached.txt").write_text("hi")
    assert node_dir.exists()
    clear_node_cache(["a"], graph, tmp_path)
    assert not node_dir.exists()


def test_positional_edges_count_as_downstream(tmp_path: Path) -> None:
    graph = GraphState(
        nodes=[_node("a"), _node("b")],
        edges=[
            PositionalEdge(
                id="e1", source_node="a", target_node="b", positional_index=0
            )
        ],
    )
    result = clear_node_cache(["a"], graph, tmp_path)
    assert result["a"].status == "unexecuted"
    assert result["b"].status == "out_of_date"
