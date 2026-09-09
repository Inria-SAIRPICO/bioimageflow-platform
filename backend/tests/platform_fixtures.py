"""Small executable fixtures for local platform contract and journey tests.

Tool metadata comes from the actual classes; graph edges express the public
DataFrame/column distinction. Intentional invalid variants belong in tests.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel

from bioimageflow_server.models.graph import ColumnEdge, DataFrameEdge, GraphState, ToolNodeState
from bioimageflow_server.services.tool_registry import ToolRegistryService
from tests.fixtures.worker_numbers import WorkerNumbers
from tests.graph_factory import graph_state


class SourceNumbers(DataFrameTool):
    """Produce named rows so accidental positional alignment is observable."""

    accepts_upstream = False

    class Inputs(IOModel):
        start: int = 1
        count: int = 3

    class Outputs(IOModel):
        value: int

    def transform(self, df: Any, arguments: Any) -> pd.DataFrame:
        return pd.DataFrame(
            {"value": list(range(arguments.start, arguments.start + arguments.count))},
            index=[f"row{i}" for i in range(arguments.count)],
        )


class AddOffset(DataFrameTool):
    """Consume a whole positional DataFrame and a constant offset."""

    class Inputs(IOModel):
        offset: int = 10

    class Outputs(IOModel):
        value: int
        shifted: int

    def transform(self, df: pd.DataFrame, arguments: Any) -> pd.DataFrame:
        out = df[["value"]].copy()
        out["shifted"] = out["value"] + arguments.offset
        return out


class ExplodingNumbers(DataFrameTool):
    accepts_upstream = False

    class Inputs(IOModel):
        message: str = "deterministic failure"

    class Outputs(IOModel):
        value: int

    def transform(self, df: Any, arguments: Any) -> pd.DataFrame:
        raise RuntimeError(arguments.message)


def local_registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    for tool in (SourceNumbers, AddOffset, ExplodingNumbers, WorkerNumbers):
        registry._register_tool_from_class(tool, tool.__name__, "test-tools", "1.0.0")
    return registry


def dataframe_chain() -> GraphState:
    """A sequential local source-to-transform journey with an exact oracle."""
    return graph_state(
        config={"engine": "wetlands", "execution": "sequential"},
        nodes=[
            ToolNodeState(
                type="tool", id="source", name="source", tool_name="SourceNumbers",
                position=(0, 0), parameters={"start": 2, "count": 3},
            ),
            ToolNodeState(
                type="tool", id="offset", name="offset", tool_name="AddOffset",
                position=(200, 0), parameters={"offset": 5},
            ),
        ],
        edges=[
            DataFrameEdge(
                type="dataframe", id="source_to_offset", source_node="source",
                target_node="offset", target_position=0,
            ),
        ],
    )


def worker_chain() -> GraphState:
    """Sequential processing through Wetlands with independent output oracles."""
    graph = dataframe_chain()
    graph.nodes = [graph.nodes[0], ToolNodeState(
        type="tool", id="worker", name="worker", tool_name="WorkerNumbers",
        position=(200, 0), parameters={"multiplier": 3},
    )]
    graph.edges = [ColumnEdge(
        type="column", id="source_to_worker", source_node="source",
        source_output="value", target_node="worker", target_input="value",
    )]
    return graph
