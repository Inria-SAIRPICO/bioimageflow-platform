"""Tests for :mod:`bioimageflow_server.services.graph_builder`."""

from typing import Any

import pytest

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImagePath, Semantic

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
    PositionalEdge,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService


# ---- Mock tool classes (module-level so from_dict can re-import) -----------


class ProcInputs(IOModel):
    input_image: ImagePath(semantics={Semantic.INTENSITY})
    diameter: float = 30.0
    model: str = "default"


class ProcOutputs(IOModel):
    mask: ImagePath(semantics={Semantic.LABEL})


class MockProcessingTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = ProcInputs
    Outputs = ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class DFInputs(IOModel):
    threshold: float = 0.5


class MockDataFrameTool(DataFrameTool):
    Inputs = DFInputs


class DownstreamInputs(IOModel):
    mask_input: ImagePath(semantics={Semantic.LABEL})
    scale: float = 1.0


class DownstreamOutputs(IOModel):
    result: ImagePath(semantics={Semantic.LABEL})


class DownstreamTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = DownstreamInputs
    Outputs = DownstreamOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


_TOOL_CLASSES: dict[str, type] = {
    "MockProcessingTool": MockProcessingTool,
    "MockDataFrameTool": MockDataFrameTool,
    "DownstreamTool": DownstreamTool,
}


def _make_metadata(name: str) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="test-package",
        package_version="1.0.0",
        tool_type="ProcessingTool",
        documentation="",
    )


@pytest.fixture
def registry() -> ToolRegistryService:
    """A registry populated with mock tools."""
    reg = ToolRegistryService()
    for name, cls in _TOOL_CLASSES.items():
        reg.register_tool(name, _make_metadata(name), tool_class=cls)
    return reg


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    """Reset the global active workflow between tests."""
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


# ---- Tests ------------------------------------------------------------------


def test_empty_graph(registry: ToolRegistryService) -> None:
    result = build_workflow(GraphState(nodes=[], edges=[]), registry)
    assert result.errors == []
    assert result.node_map == {}
    assert result.disabled_node_ids == set()
    assert result.workflow is not None


def test_single_valid_node(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="n1",
                name="n1",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
            )
        ],
        edges=[],
    )
    result = build_workflow(graph, registry)
    assert result.errors == []
    assert "n1" in result.node_map
    assert result.node_map["n1"].name == "n1"


def test_missing_tool_error(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="n1",
                name="n1",
                tool_name="Nonexistent",
                position=(0, 0),
                parameters={},
            )
        ],
        edges=[],
    )
    result = build_workflow(graph, registry)
    assert len(result.errors) == 1
    assert result.errors[0].type == "missing_tool"
    assert result.errors[0].node == "n1"


def test_missing_package_error() -> None:
    """A tool whose class cannot be loaded produces missing_package."""
    reg = ToolRegistryService()
    reg.register_tool(
        "Missing",
        ToolMetadata(
            name="Missing",
            display_name="Missing",
            package="nonexistent-package",
            package_version="0.0.1",
            tool_type="ProcessingTool",
        ),
    )
    graph = GraphState(
        nodes=[
            NodeState(
                id="n1",
                name="n1",
                tool_name="Missing",
                position=(0, 0),
                parameters={},
            )
        ],
        edges=[],
    )
    result = build_workflow(graph, reg)
    assert len(result.errors) == 1
    assert result.errors[0].type == "missing_package"
    assert result.errors[0].node == "n1"


def test_disabled_node_excluded(registry: ToolRegistryService) -> None:
    """Disabled nodes are tracked in ``disabled_node_ids``.

    Unlike the pre-library-delegation builder, the library keeps
    disabled nodes in the workflow (with ``enabled=False``) so that
    downstream references stay resolvable. The platform tracks the
    explicit ``enabled=False`` set separately.
    """
    graph = GraphState(
        nodes=[
            NodeState(
                id="n1",
                name="n1",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
                enabled=False,
            )
        ],
        edges=[],
    )
    result = build_workflow(graph, registry)
    assert result.disabled_node_ids == {"n1"}
    assert result.errors == []


def test_column_ref_edge(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="src",
                name="src",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
            ),
            NodeState(
                id="dst",
                name="dst",
                tool_name="DownstreamTool",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            ColumnRefEdge(
                id="e1",
                source_node="src",
                target_node="dst",
                source_output="mask",
                target_input="mask_input",
            )
        ],
    )
    result = build_workflow(graph, registry)
    assert result.errors == []
    assert set(result.node_map.keys()) == {"src", "dst"}
    dst = result.node_map["dst"]
    assert "mask_input" in dst._column_bindings
    assert dst._column_bindings["mask_input"].column == "mask"


def test_positional_edge_reindexing(registry: ToolRegistryService) -> None:
    """Positional indices [2, 0, 5] should yield args in ascending order."""
    graph = GraphState(
        nodes=[
            NodeState(
                id="s1",
                name="s1",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/a"},
            ),
            NodeState(
                id="s2",
                name="s2",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/b"},
            ),
            NodeState(
                id="s3",
                name="s3",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/c"},
            ),
            NodeState(
                id="df",
                name="df",
                tool_name="MockDataFrameTool",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            PositionalEdge(id="e1", source_node="s1", target_node="df", positional_index=2),
            PositionalEdge(id="e2", source_node="s2", target_node="df", positional_index=0),
            PositionalEdge(id="e3", source_node="s3", target_node="df", positional_index=5),
        ],
    )
    result = build_workflow(graph, registry)
    assert result.errors == []
    df = result.node_map["df"]
    arg_names = [a.name for a in df._args]
    assert arg_names == ["s2", "s1", "s3"]


def test_duplicate_node_ids(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="dup",
                name="a",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/a"},
            ),
            NodeState(
                id="dup",
                name="b",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/b"},
            ),
        ],
        edges=[],
    )
    result = build_workflow(graph, registry)
    types = [e.type for e in result.errors]
    assert "invalid_node_id" in types


def test_duplicate_edge_ids(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="a", name="a", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="b", name="b", tool_name="DownstreamTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            ColumnRefEdge(id="dup", source_node="a", target_node="b",
                          source_output="mask", target_input="mask_input"),
            ColumnRefEdge(id="dup", source_node="a", target_node="b",
                          source_output="mask", target_input="mask_input"),
        ],
    )
    result = build_workflow(graph, registry)
    types = [e.type for e in result.errors]
    assert "invalid_edge_id" in types


def test_edge_references_unknown_node(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="a", name="a", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
        ],
        edges=[
            ColumnRefEdge(id="e", source_node="a", target_node="ghost",
                          source_output="mask", target_input="x"),
        ],
    )
    result = build_workflow(graph, registry)
    types = [e.type for e in result.errors]
    assert "invalid_edge_id" in types


def test_mixed_graph(registry: ToolRegistryService) -> None:
    """Graph with valid nodes, a missing tool, and a disabled node."""
    graph = GraphState(
        nodes=[
            NodeState(id="good", name="g", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="missing", name="m", tool_name="NoSuchTool",
                      position=(0, 0), parameters={}),
            NodeState(id="disabled", name="d", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/d"}, enabled=False),
        ],
        edges=[],
    )
    result = build_workflow(graph, registry)
    assert "good" in result.node_map
    assert "disabled" in result.disabled_node_ids
    assert any(e.type == "missing_tool" and e.node == "missing" for e in result.errors)
