"""Recursive platform/library translation contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.tool import IOModel

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.tools import PackageInfo, ToolMetadata
from bioimageflow_server.services.graph_translator import (
    _detect_missing_packages,
    collect_required_packages,
    graph_state_to_lib_dict,
    lib_dict_to_graph_state,
    lib_validation_error_to_graph_error,
    rebind_lib_dict_versions,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


class Inputs(IOModel):
    value: int = 1


class Outputs(IOModel):
    value: int


class ExampleTool(DataFrameTool):
    accepts_upstream = True
    Inputs = Inputs
    Outputs = Outputs


def _registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    registry.register_tool(
        "ExampleTool",
        ToolMetadata(
            name="ExampleTool",
            display_name="Example",
            package="example-tools",
            package_version="1.0.0",
            tool_type="DataFrameTool",
        ),
        tool_class=ExampleTool,
    )
    registry.register_package(
        "example-tools",
        PackageInfo(
            name="example-tools",
            installed_versions=["1.0.0", "2.0.0"],
            active_version="2.0.0",
            tools={"1.0.0": ["ExampleTool"], "2.0.0": ["ExampleTool"]},
        ),
    )
    return registry


def _tool(node_id: str) -> dict[str, Any]:
    return {
        "type": "tool",
        "id": node_id,
        "name": node_id.title(),
        "tool_name": "ExampleTool",
        "position": [20, 40],
        "parameters": {"value": 4},
        "resources": {"cpu": 2},
        "collapsed": True,
    }


def _graph(name: str, nodes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": name,
        "display_name": name.title(),
        "nodes": nodes or [],
        "edges": [],
        "interface": {"inputs": [], "outputs": []},
        "config": {
            "storage_path": "./definition-data",
            "engine": "direct",
            "execution": "parallel",
        },
    }


def test_recursive_translation_uses_one_library_grammar() -> None:
    child = _graph("child", [_tool("inner")])
    child["interface"] = {
        "inputs": [
            {
                "id": "input-value",
                "name": "Value",
                "kind": "field",
                "targets": [
                    {"node": "inner", "port": {"kind": "field", "name": "value"}}
                ],
            }
        ],
        "outputs": [
            {
                "id": "output-value",
                "name": "Value",
                "source": {"node": "inner", "column": "value"},
            }
        ],
    }
    parent = _graph(
        "parent",
        [
            {
                "type": "workflow",
                "id": "child-node",
                "name": "Canvas label only",
                "workflow": child,
                "bindings": {"input-value": {"__type__": "int", "value": 9}},
                "position": [100, 200],
            }
        ],
    )
    graph = GraphState.model_validate(parent)

    translated = graph_state_to_lib_dict(graph, _registry())

    assert translated.errors == []
    node = translated.lib_dict["nodes"][0]
    assert node == {
        "name": "child-node",
        "type": "workflow",
        "workflow": {
            **node["workflow"],
            "name": "child",
            "display_name": "Child",
        },
        "bindings": {"input-value": {"__type__": "int", "value": 9}},
    }
    assert node["workflow"]["nodes"][0]["type"] == "tool"
    assert "position" not in node
    assert "resources" not in node["workflow"]["nodes"][0]
    assert "collapsed" not in node["workflow"]["nodes"][0]


def test_column_and_dataframe_edges_round_trip_at_workflow_boundary() -> None:
    child = _graph("child")
    child["interface"] = {
        "inputs": [
            {"id": "field", "name": "Field", "kind": "field", "targets": []},
            {"id": "frame", "name": "Frame", "kind": "dataframe", "targets": []},
        ],
        "outputs": [],
    }
    parent = _graph(
        "parent",
        [
            _tool("source"),
            {
                "type": "workflow",
                "id": "child",
                "name": "Child",
                "workflow": child,
                "bindings": {},
                "position": [0, 0],
            },
        ],
    )
    parent["edges"] = [
        {
            "type": "column",
            "id": "column-edge",
            "source_node": "source",
            "source_output": "value",
            "target_node": "child",
            "target_input": "field",
        },
        {
            "type": "dataframe",
            "id": "frame-edge",
            "source_node": "source",
            "target_node": "child",
            "target_input": "frame",
        },
    ]
    graph = GraphState.model_validate(parent)
    library = graph_state_to_lib_dict(graph, _registry()).lib_dict
    restored = lib_dict_to_graph_state(library)

    assert restored.edges == graph.edges
    assert restored.nodes[1].workflow.interface == graph.nodes[1].workflow.interface  # type: ignore[union-attr]


def test_golden_recursive_library_fixture_imports_without_an_adapter_schema() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "unified_workflow_graph.json"
    library = json.loads(fixture.read_text(encoding="utf-8"))
    graph = lib_dict_to_graph_state(library)
    translated = graph_state_to_lib_dict(graph, ToolRegistryService())

    assert graph.name == "parent"
    assert graph.nodes[0].type == "workflow"
    assert translated.errors == []
    assert translated.lib_dict["nodes"][0]["type"] == "workflow"
    assert translated.lib_dict["nodes"][0]["workflow"]["schema_version"] == 1


def test_requirements_and_version_rebinding_recurse() -> None:
    child = _graph("child", [_tool("inner")])
    parent = _graph(
        "parent",
        [
            {
                "type": "workflow",
                "id": "child",
                "name": "Child",
                "workflow": child,
                "bindings": {},
                "position": [0, 0],
            }
        ],
    )
    library = graph_state_to_lib_dict(
        GraphState.model_validate(parent), _registry()
    ).lib_dict
    # Exercise the portable package fields independently of local test-module
    # package discovery.
    inner = library["nodes"][0]["workflow"]["nodes"][0]
    inner["tool_package"] = "example-tools"
    inner["tool_package_version"] = "1.0.0"

    packages, local = collect_required_packages(library, _registry())
    rebound = rebind_lib_dict_versions(library, _registry())

    assert [(item.name, item.version) for item in packages] == [
        ("example-tools", "1.0.0")
    ]
    assert local == []
    assert rebound["nodes"][0]["workflow"]["nodes"][0][
        "tool_package_version"
    ] == "2.0.0"


def test_missing_packages_report_scoped_node_paths() -> None:
    library = _graph("root")
    child = _graph("child")
    child["nodes"] = [
        {
            "name": "tool",
            "type": "tool",
            "tool_module": "missing.tool",
            "tool_class": "Missing",
            "tool_package": "missing-package",
            "tool_package_version": "3.0.0",
            "constants": {},
        }
    ]
    library["nodes"] = [
        {
            "name": "child",
            "type": "workflow",
            "workflow": child,
            "bindings": {},
        }
    ]

    missing = _detect_missing_packages(library, ToolRegistryService())

    assert missing[0].affected_nodes == ["child/tool"]


def test_library_validation_paths_are_preserved() -> None:
    error = SimpleNamespace(
        kind="missing_input",
        message="value is required",
        node="tool",
        field="value",
        edge_id=None,
        path=("outer", "inner"),
    )

    mapped = lib_validation_error_to_graph_error(error)

    assert mapped.node == "outer/inner/tool"
    assert mapped.detail == "in workflow 'outer/inner': value is required"
