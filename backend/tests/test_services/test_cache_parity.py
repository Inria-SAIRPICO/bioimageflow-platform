"""Cache parity tests.

Lock the invariant that ``validate_graph``'s per-node ``cached`` flag
matches what the engine would observe when it runs the same signature
hash lookup. Before the library-adoption refactor, the validator
recomputed signature hashes with a *different* resolved-params shape
from the execution engine — so validation could report ``cached=True``
while execution recomputed (or vice versa). Now both paths go through
``Workflow.plan()`` / ``compute()`` which share a single hash
implementation. These tests guard against regressions.
"""
from pathlib import Path
from typing import Any

import pytest
from tests.graph_factory import graph_state

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.tool import IOModel

from bioimageflow_server.models.graph import (
    GraphState,
    ToolNodeState,
    DataFrameEdge,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.tool_registry import ToolRegistryService


class _SourceInputs(IOModel):
    diameter: float = 30.0


class _SourceOutputs(IOModel):
    value: int


class SourceTool(DataFrameTool):
    accepts_upstream = False
    Inputs = _SourceInputs
    Outputs = _SourceOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        import pandas as pd

        return pd.DataFrame({"value": [int(arguments.diameter)]})


class _MidInputs(IOModel):
    scale: float = 1.0


class _MidOutputs(IOModel):
    result: int


class MidTool(DataFrameTool):
    Inputs = _MidInputs
    Outputs = _MidOutputs

    def transform(self, df: Any, arguments: Any) -> Any:
        result = df.copy()
        result["result"] = result["value"] * int(arguments.scale)
        return result


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in [("SourceTool", SourceTool), ("MidTool", MidTool)]:
        reg.register_tool(
            name,
            ToolMetadata(
                name=name, display_name=name,
                package="test-pkg", package_version="1.0.0",
                tool_type="DataFrameTool",
            ),
            tool_class=cls,
        )
    return reg


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


def _seed_cache(storage_path: Path, registry: ToolRegistryService,
                graph: GraphState, dev_mode: bool) -> None:
    """Populate the cache by executing the workflow through the clean API."""
    workflow, _errors, _disabled = build_workflow(graph, registry, storage_path=storage_path)
    workflow.compute(dev_mode=dev_mode)


def _chain_graph() -> GraphState:
    return graph_state(
        nodes=[
            ToolNodeState(type="tool", id="src", name="src", tool_name="SourceTool",
                      position=(0, 0),
                      parameters={"diameter": 30.0}),
            ToolNodeState(type="tool", id="mid", name="mid", tool_name="MidTool",
                      position=(0, 0),
                      parameters={"scale": 2.0}),
        ],
        edges=[
            DataFrameEdge(type="dataframe",
                id="e1",
                source_node="src",
                target_node="mid",
                target_position=0,
            ),
        ],
    )


@pytest.mark.parametrize("dev_mode", [True, False])
def test_empty_cache_reports_unexecuted(
    registry: ToolRegistryService, tmp_path: Path, dev_mode: bool,
) -> None:
    graph = _chain_graph()
    result = validate_graph(graph, registry, storage_path=tmp_path, dev_mode=dev_mode)
    assert result.valid is True
    for nid in ("src", "mid"):
        status = result.node_statuses[nid]
        assert status.status == "unexecuted"
        assert status.cached is False


@pytest.mark.parametrize("dev_mode", [True, False])
def test_seeded_cache_reports_executed(
    registry: ToolRegistryService, tmp_path: Path, dev_mode: bool,
) -> None:
    """After seeding the cache via the engine's own hash, every node
    must be reported as ``executed``/``cached=True`` by the validator."""
    graph = _chain_graph()
    _seed_cache(tmp_path, registry, graph, dev_mode)

    result = validate_graph(graph, registry, storage_path=tmp_path, dev_mode=dev_mode)
    for nid in ("src", "mid"):
        status = result.node_statuses[nid]
        assert status.status == "executed", f"{nid}: {status}"
        assert status.cached is True, f"{nid}: {status}"


@pytest.mark.parametrize("dev_mode", [True, False])
def test_constant_change_invalidates_downstream(
    registry: ToolRegistryService, tmp_path: Path, dev_mode: bool,
) -> None:
    """Changing a constant on ``src`` must flip both ``src`` and ``mid``
    off ``cached``; an unchanged chain stays fully cached."""
    graph = _chain_graph()
    _seed_cache(tmp_path, registry, graph, dev_mode)

    # Mutate the upstream node's constant.
    modified = graph_state(
        nodes=[
            ToolNodeState(type="tool", id="src", name="src", tool_name="SourceTool",
                      position=(0, 0),
                      parameters={"diameter": 99.0}),
            ToolNodeState(type="tool", id="mid", name="mid", tool_name="MidTool",
                      position=(0, 0),
                      parameters={"scale": 2.0}),
        ],
        edges=graph.edges,
    )

    result = validate_graph(modified, registry, storage_path=tmp_path, dev_mode=dev_mode)
    assert result.node_statuses["src"].cached is False
    assert result.node_statuses["mid"].cached is False
    # ``src`` previously had a hash dir on disk → out_of_date.
    assert result.node_statuses["src"].status in {"out_of_date", "unexecuted"}


@pytest.mark.parametrize("dev_mode", [True, False])
def test_unrelated_node_stays_cached(
    registry: ToolRegistryService, tmp_path: Path, dev_mode: bool,
) -> None:
    """Changing a downstream node must NOT invalidate its upstream."""
    graph = _chain_graph()
    _seed_cache(tmp_path, registry, graph, dev_mode)

    modified = graph_state(
        nodes=[
            ToolNodeState(type="tool", id="src", name="src", tool_name="SourceTool",
                      position=(0, 0),
                      parameters={"diameter": 30.0}),
            ToolNodeState(type="tool", id="mid", name="mid", tool_name="MidTool",
                      position=(0, 0),
                      parameters={"scale": 99.0}),
        ],
        edges=graph.edges,
    )

    result = validate_graph(modified, registry, storage_path=tmp_path, dev_mode=dev_mode)
    assert result.node_statuses["src"].status == "executed"
    assert result.node_statuses["src"].cached is True
    assert result.node_statuses["mid"].cached is False
