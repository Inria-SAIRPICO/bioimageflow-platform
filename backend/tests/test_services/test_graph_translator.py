"""Tests for :mod:`bioimageflow_server.services.graph_translator`."""
# pyright: reportInvalidTypeForm=false
# Rationale: library factory types like ``ImagePath(semantics={...})`` return
# ``Annotated[Path, spec]`` at runtime; pyright can't evaluate them statically.

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
from bioimageflow_server.services.graph_translator import (
    POSITIONAL_KEY,
    graph_state_to_lib_dict,
    lib_validation_error_to_graph_error,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


class _Inputs(IOModel):
    input_image: ImagePath(semantics={Semantic.INTENSITY})
    diameter: float = 30.0


class _Outputs(IOModel):
    mask: ImagePath(semantics={Semantic.LABEL})


class TProcTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = _Inputs
    Outputs = _Outputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class _DFInputs(IOModel):
    threshold: float = 0.5


class TDfTool(DataFrameTool):
    Inputs = _DFInputs


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in [("TProcTool", TProcTool), ("TDfTool", TDfTool)]:
        reg.register_tool(
            name,
            ToolMetadata(
                name=name, display_name=name,
                package="test-pkg", package_version="1.0.0",
                tool_type="ProcessingTool",
            ),
            tool_class=cls,
        )
    return reg


def test_empty_graph(registry: ToolRegistryService) -> None:
    result = graph_state_to_lib_dict(GraphState(nodes=[], edges=[]), registry)
    assert result.errors == []
    assert result.lib_dict["nodes"] == []
    assert result.lib_dict["edges"] == []


def test_single_node_with_constants(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n", name="n", tool_name="TProcTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "diameter": 42.0}),
        ],
        edges=[],
    )
    result = graph_state_to_lib_dict(graph, registry)
    assert result.errors == []
    [node_dict] = result.lib_dict["nodes"]
    assert node_dict["name"] == "n"
    assert node_dict["tool_class"] == "TProcTool"
    assert node_dict["constants"]["input_image"] == {"__type__": "str", "value": "/a"}
    assert node_dict["constants"]["diameter"] == {"__type__": "float", "value": 42.0}


def test_column_ref_edge_emitted(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="TProcTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dst", name="dst", tool_name="TProcTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            ColumnRefEdge(id="e", source_node="src", target_node="dst",
                          source_output="mask", target_input="input_image"),
        ],
    )
    result = graph_state_to_lib_dict(graph, registry)
    edges = result.lib_dict["edges"]
    assert edges == [
        {"from": "src", "to": "dst", "column": "mask", "field": "input_image"},
    ]
    assert result.edge_id_by_key[("src", "dst", "input_image")] == "e"


def test_positional_edges_sorted_and_normalised(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id=f"s{i}", name=f"s{i}", tool_name="TProcTool",
                      position=(0, 0), parameters={"input_image": f"/{i}"})
            for i in range(3)
        ] + [
            NodeState(id="df", name="df", tool_name="TDfTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            PositionalEdge(id="e0", source_node="s0", target_node="df", positional_index=2),
            PositionalEdge(id="e1", source_node="s1", target_node="df", positional_index=0),
            PositionalEdge(id="e2", source_node="s2", target_node="df", positional_index=1),
        ],
    )
    result = graph_state_to_lib_dict(graph, registry)
    df_node = next(n for n in result.lib_dict["nodes"] if n["name"] == "df")
    assert df_node["args"] == ["s1", "s2", "s0"]
    positional_edges = [e for e in result.lib_dict["edges"] if e["column"] == POSITIONAL_KEY]
    assert [e["from"] for e in positional_edges] == ["s1", "s2", "s0"]


def test_duplicate_node_ids_emit_errors(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="dup", name="a", tool_name="TProcTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dup", name="b", tool_name="TProcTool",
                      position=(0, 0), parameters={"input_image": "/b"}),
        ],
        edges=[],
    )
    result = graph_state_to_lib_dict(graph, registry)
    assert any(e.type == "invalid_node_id" for e in result.errors)
    # Only one node entry emitted (first occurrence).
    assert len(result.lib_dict["nodes"]) == 1


def test_unknown_tool_emits_missing_tool(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n", name="n", tool_name="NoSuchTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[],
    )
    result = graph_state_to_lib_dict(graph, registry)
    assert any(e.type == "missing_tool" and e.node == "n" for e in result.errors)
    assert result.lib_dict["nodes"] == []


def test_error_kind_mapping() -> None:
    """Every library ``ValidationErrorKind`` maps to a platform type."""
    from bioimageflow import ValidationError, ValidationErrorKind

    edge_map = {("a", "b", "x"): "edge-id-1"}

    cases: list[tuple[ValidationErrorKind, str]] = [
        ("cycle", "cycle_detected"),
        ("type_mismatch", "type_incompatible"),
        ("column_not_found", "type_incompatible"),
        ("missing_input", "missing_connection"),
        ("unknown_input", "parameter_invalid"),
        ("parameter_invalid", "parameter_invalid"),
        ("duplicate_name", "invalid_node_id"),
        ("construction_failed", "parameter_invalid"),
    ]
    for kind, expected_type in cases:
        err = ValidationError(kind=kind, message="m", node="a", field="x")
        out = lib_validation_error_to_graph_error(err, edge_map)
        assert out.type == expected_type, f"{kind} → {out.type}, expected {expected_type}"


def test_unknown_tool_kind_splits_on_message() -> None:
    from bioimageflow import ValidationError

    pkg_err = ValidationError(
        kind="unknown_tool",
        message="Package 'foo' is not installed.",
        node="n",
    )
    tool_err = ValidationError(
        kind="unknown_tool",
        message="Attribute not found on module",
        node="n",
    )
    assert lib_validation_error_to_graph_error(pkg_err, {}).type == "missing_package"
    assert lib_validation_error_to_graph_error(tool_err, {}).type == "missing_tool"


def test_error_edge_attribution() -> None:
    from bioimageflow import ValidationError

    edge_map = {("src", "dst", "input_image"): "my-edge-id"}
    err = ValidationError(
        kind="type_mismatch", message="bad",
        node="dst", field="input_image",
        edge=("src", "dst", "input_image"),
    )
    out = lib_validation_error_to_graph_error(err, edge_map)
    assert out.edge_id == "my-edge-id"
    assert out.node == "dst"
    assert out.field == "input_image"


def test_error_path_flattened_into_detail() -> None:
    from bioimageflow import ValidationError

    err = ValidationError(
        kind="parameter_invalid",
        message="n must be >= 0",
        node="inner",
        field="n",
        path=("outer_sw", "inner_sw"),
    )
    out = lib_validation_error_to_graph_error(err, {})
    assert "outer_sw/inner_sw" in out.detail
    assert "n must be >= 0" in out.detail
