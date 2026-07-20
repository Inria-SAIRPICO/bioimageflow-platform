"""Tests for :mod:`bioimageflow_server.services.graph_builder`."""
# pyright: reportInvalidTypeForm=false
# Rationale: image file fields use ``Annotated[Path, ImageSpec(...)]`` metadata;
# pyright can't evaluate this runtime metadata statically.

from pathlib import Path
from typing import Annotated, Any

import pytest
from tests.graph_factory import graph_state

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImageSpec, Semantic

from bioimageflow_server.models.graph import (
    ColumnEdge,
    ToolNodeState,
    DataFrameEdge,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService


# ---- Mock tool classes (module-level so from_dict can re-import) -----------


class ProcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    diameter: float = 30.0
    model: str = "default"


class ProcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class MockProcessingTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = ProcInputs
    Outputs = ProcOutputs

    def process_row(self, arguments: Any, *, context: Any = None) -> Any:
        return {}


class DFInputs(IOModel):
    threshold: float = 0.5


class MockDataFrameTool(DataFrameTool):
    Inputs = DFInputs


class DownstreamInputs(IOModel):
    mask_input: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]
    scale: float = 1.0


class DownstreamOutputs(IOModel):
    result: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class DownstreamTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = DownstreamInputs
    Outputs = DownstreamOutputs

    def process_row(self, arguments: Any, *, context: Any = None) -> Any:
        return {}


_TOOL_CLASSES: dict[str, type] = {
    "MockProcessingTool": MockProcessingTool,
    "MockDataFrameTool": MockDataFrameTool,
    "DownstreamTool": DownstreamTool,
}


def _make_metadata(name: str, cls: type) -> ToolMetadata:
    tool_type = "DataFrameTool" if issubclass(cls, DataFrameTool) else "ProcessingTool"
    return ToolMetadata(
        name=name,
        display_name=name,
        package="test-package",
        package_version="1.0.0",
        tool_type=tool_type,
        accepts_upstream=bool(getattr(cls, "accepts_upstream", True)),
        dataframe_output=True,
        documentation="",
    )


@pytest.fixture
def registry() -> ToolRegistryService:
    """A registry populated with mock tools."""
    reg = ToolRegistryService()
    for name, cls in _TOOL_CLASSES.items():
        reg.register_tool(name, _make_metadata(name, cls), tool_class=cls)
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
    workflow, errors, disabled = build_workflow(graph_state(nodes=[], edges=[]), registry)
    assert errors == []
    assert workflow.nodes == {}
    assert disabled == set()


def test_single_valid_node(registry: ToolRegistryService) -> None:
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="n1",
                name="n1",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
            )
        ],
        edges=[],
    )
    workflow, errors, _disabled = build_workflow(graph, registry)
    assert errors == []
    assert "n1" in workflow.nodes
    assert workflow.nodes["n1"].name == "n1"


def test_built_workflow_uses_wetlands(registry: ToolRegistryService) -> None:
    """GUI-built workflows must execute processing tools through Wetlands."""
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="n1",
                name="n1",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
            )
        ],
        edges=[],
    )

    workflow, errors, _disabled = build_workflow(graph, registry)

    assert errors == []
    assert workflow.engine_type == "wetlands"
    assert workflow.execution == "parallel"


def test_processing_tool_can_feed_dataframe_tool_positionally(
    registry: ToolRegistryService,
) -> None:
    """A ProcessingTool node's whole output DataFrame may feed a DataFrameTool."""
    metadata = registry.get_tool("MockDataFrameTool")
    assert metadata is not None
    assert metadata.tool_type == "DataFrameTool"
    assert metadata.dataframe_output is True

    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="proc",
                name="proc",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
            ),
            ToolNodeState(type="tool",
                id="df",
                name="df",
                tool_name="MockDataFrameTool",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            DataFrameEdge(type="dataframe",
                id="e1",
                source_node="proc",
                target_node="df",
                target_position=0,
            )
        ],
    )

    workflow, errors, _disabled = build_workflow(graph, registry)

    assert errors == []
    assert workflow.nodes["df"]._args == [workflow.nodes["proc"]]


def test_missing_tool_error(registry: ToolRegistryService) -> None:
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="n1",
                name="n1",
                tool_name="Nonexistent",
                position=(0, 0),
                parameters={},
            )
        ],
        edges=[],
    )
    _workflow, errors, _disabled = build_workflow(graph, registry)
    assert len(errors) == 1
    assert errors[0].type == "missing_tool"
    assert errors[0].node == "n1"


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
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="n1",
                name="n1",
                tool_name="Missing",
                position=(0, 0),
                parameters={},
            )
        ],
        edges=[],
    )
    _workflow, errors, _disabled = build_workflow(graph, reg)
    assert len(errors) == 1
    assert errors[0].type == "missing_package"
    assert errors[0].node == "n1"


def test_disabled_node_excluded(registry: ToolRegistryService) -> None:
    """Disabled nodes are tracked in ``disabled_node_ids``.

    Unlike the pre-library-delegation builder, the library keeps
    disabled nodes in the workflow (with ``enabled=False``) so that
    downstream references stay resolvable. The platform tracks the
    explicit ``enabled=False`` set separately.
    """
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
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
    _workflow, errors, disabled = build_workflow(graph, registry)
    assert disabled == {"n1"}
    assert errors == []


def test_column_edge(registry: ToolRegistryService) -> None:
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="src",
                name="src",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/tmp/x.tif"},
            ),
            ToolNodeState(type="tool",
                id="dst",
                name="dst",
                tool_name="DownstreamTool",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            ColumnEdge(type="column",
                id="e1",
                source_node="src",
                target_node="dst",
                source_output="mask",
                target_input="mask_input",
            )
        ],
    )
    workflow, errors, _disabled = build_workflow(graph, registry)
    assert errors == []
    assert set(workflow.nodes.keys()) == {"src", "dst"}
    dst = workflow.nodes["dst"]
    assert "mask_input" in dst._column_bindings
    assert dst._column_bindings["mask_input"].column == "mask"


def test_dataframe_edges_retain_explicit_positions(registry: ToolRegistryService) -> None:
    """DataFrame inputs are ordered by their explicit contiguous positions."""
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool",
                id="s1",
                name="s1",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/a"},
            ),
            ToolNodeState(type="tool",
                id="s2",
                name="s2",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/b"},
            ),
            ToolNodeState(type="tool",
                id="s3",
                name="s3",
                tool_name="MockProcessingTool",
                position=(0, 0),
                parameters={"input_image": "/c"},
            ),
            ToolNodeState(type="tool",
                id="df",
                name="df",
                tool_name="MockDataFrameTool",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            DataFrameEdge(type="dataframe", id="e1", source_node="s1", target_node="df", target_position=2),
            DataFrameEdge(type="dataframe", id="e2", source_node="s2", target_node="df", target_position=0),
            DataFrameEdge(type="dataframe", id="e3", source_node="s3", target_node="df", target_position=1),
        ],
    )
    workflow, errors, _disabled = build_workflow(graph, registry)
    assert errors == []
    df = workflow.nodes["df"]
    arg_names = [a.name for a in df._args]
    assert arg_names == ["s2", "s3", "s1"]


def test_mixed_graph(registry: ToolRegistryService) -> None:
    """Graph with valid nodes, a missing tool, and a disabled node."""
    graph = graph_state(
        nodes=[
            ToolNodeState(type="tool", id="good", name="g", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            ToolNodeState(type="tool", id="missing", name="m", tool_name="NoSuchTool",
                      position=(0, 0), parameters={}),
            ToolNodeState(type="tool", id="disabled", name="d", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/d"}, enabled=False),
        ],
        edges=[],
    )
    workflow, errors, disabled = build_workflow(graph, registry)
    assert "good" in workflow.nodes
    assert "disabled" in disabled
    assert any(e.type == "missing_tool" and e.node == "missing" for e in errors)
