"""Recursive platform/library translation contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core import ResourceSpec
from bioimageflow_core.tool import IOModel, ProcessingTool, RowConsumption
from pydantic import ValidationError
import pytest

from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.models.tools import PackageInfo, ToolMetadata
from bioimageflow_server.services.graph_translator import (
    _detect_missing_packages,
    _detect_missing_tools,
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


class ProcessingExample(ProcessingTool):

    row_consumption = RowConsumption.MAPPED
    Inputs = Inputs
    Outputs = Outputs
    environment = None
    resources = ResourceSpec(cpu=2, max_concurrent=2)

    def process_row(self, arguments: Any, *, context: Any = None) -> Any:
        return arguments


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
            row_consumption=None,
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
    registry.register_tool(
        "ProcessingExample",
        ToolMetadata(
            name="ProcessingExample",
            display_name="Processing example",
            package="example-tools",
            package_version="1.0.0",
            tool_type="ProcessingTool",
            row_consumption="mapped",
        ),
        tool_class=ProcessingExample,
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
        "resources": {},
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


def test_schema_v2_viewer_additions_round_trip_through_library_wire() -> None:
    payload = _graph("viewer", [_tool("inner")])
    payload["schema_version"] = 2
    viewer = {
        "napari": {
            "required_packages": [
                {
                    "distribution": "example-reader",
                    "normalized_name": "example-reader",
                    "version": ">=1",
                }
            ],
            "recommended_packages": [],
            "napari_version": None,
            "reader_id": "example.reader",
        }
    }
    payload["nodes"][0]["viewer_additions"] = {"image": viewer}
    graph = GraphState.model_validate(payload)

    library = graph_state_to_lib_dict(graph, _registry()).lib_dict
    restored = lib_dict_to_graph_state(library)

    assert library["schema_version"] == 2
    assert library["nodes"][0]["viewer_additions"]["image"] == viewer
    assert restored.nodes[0].viewer_additions["image"].model_dump(mode="json") == viewer


def test_processing_resource_overrides_round_trip_recursively() -> None:
    child = _graph(
        "child",
        [
            {
                **_tool("worker"),
                "tool_name": "ProcessingExample",
                "resources": {
                    "cpu": 4,
                    "gpu": 1,
                    "memory": "16GB",
                    "gpu_memory": "8GiB",
                    "max_concurrent": 2,
                },
            }
        ],
    )
    parent = _graph(
        "parent",
        [
            {
                "type": "workflow",
                "id": "nested",
                "name": "Nested",
                "workflow": child,
                "bindings": {},
                "position": [0, 0],
            }
        ],
    )

    graph = GraphState.model_validate(parent)
    translated = graph_state_to_lib_dict(graph, _registry())

    assert translated.errors == []
    library_node = translated.lib_dict["nodes"][0]["workflow"]["nodes"][0]
    assert library_node["resource_overrides"] == {
        "schema": "bioimageflow.node_resource_overrides.v1",
        "cpu": 4,
        "gpu": 1,
        "memory": "16GB",
        "gpu_memory": "8GiB",
        "max_concurrent": 2,
    }
    restored = lib_dict_to_graph_state(translated.lib_dict)
    restored_worker = restored.nodes[0].workflow.nodes[0]  # type: ignore[union-attr]
    assert restored_worker.resources == graph.nodes[0].workflow.nodes[0].resources  # type: ignore[union-attr]


def test_dataframe_resource_overrides_are_reported_and_not_translated() -> None:
    graph = GraphState.model_validate(
        _graph("invalid", [{**_tool("frame"), "resources": {"cpu": 2}}])
    )

    translated = graph_state_to_lib_dict(graph, _registry())

    assert translated.errors[0].type == "parameter_invalid"
    assert translated.errors[0].field == "resources"
    assert "resource_overrides" not in translated.lib_dict["nodes"][0]


def test_resource_values_are_strict_and_declaration_constraints_are_scoped() -> None:
    with pytest.raises(ValidationError):
        GraphState.model_validate(
            _graph("coerced", [{**_tool("worker"), "resources": {"cpu": "2"}}])
        )
    graph = GraphState.model_validate(
        _graph(
            "below-floor",
            [
                {
                    **_tool("worker"),
                    "tool_name": "ProcessingExample",
                    "resources": {"cpu": 1, "max_concurrent": 3},
                }
            ],
        )
    )

    translated = graph_state_to_lib_dict(graph, _registry())

    assert translated.errors[0].node == "worker"
    assert translated.errors[0].field == "resources"
    assert "resource_overrides" not in translated.lib_dict["nodes"][0]


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


def test_library_import_derives_dependency_aligned_canvas_positions() -> None:
    graph_data = _graph(
        "layered",
        [_tool("sink"), _tool("branch_b"), _tool("source"), _tool("branch_a")],
    )
    graph_data["edges"] = [
        {
            "type": "dataframe",
            "id": "source-a",
            "source_node": "source",
            "target_node": "branch_a",
            "target_position": 0,
        },
        {
            "type": "dataframe",
            "id": "source-b",
            "source_node": "source",
            "target_node": "branch_b",
            "target_position": 0,
        },
        {
            "type": "dataframe",
            "id": "a-sink",
            "source_node": "branch_a",
            "target_node": "sink",
            "target_position": 0,
        },
        {
            "type": "dataframe",
            "id": "b-sink",
            "source_node": "branch_b",
            "target_node": "sink",
            "target_position": 1,
        },
    ]
    library = graph_state_to_lib_dict(
        GraphState.model_validate(graph_data), _registry()
    ).lib_dict

    restored = lib_dict_to_graph_state(library)

    assert {node.id: node.position for node in restored.nodes} == {
        "sink": (640.0, 110.0),
        "branch_b": (320.0, 0.0),
        "source": (0.0, 110.0),
        "branch_a": (320.0, 220.0),
    }


def test_library_import_stacks_disconnected_components_below_primary_graph() -> None:
    graph_data = _graph(
        "components",
        [_tool("target"), _tool("orphan"), _tool("source")],
    )
    graph_data["edges"] = [
        {
            "type": "dataframe",
            "id": "source-target",
            "source_node": "source",
            "target_node": "target",
            "target_position": 0,
        }
    ]
    library = graph_state_to_lib_dict(
        GraphState.model_validate(graph_data), _registry()
    ).lib_dict

    restored = lib_dict_to_graph_state(library)

    assert {node.id: node.position for node in restored.nodes} == {
        "target": (320.0, 0.0),
        "orphan": (0.0, 440.0),
        "source": (0.0, 0.0),
    }


def test_golden_recursive_library_fixture_imports_without_an_adapter_schema() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "unified_workflow_graph.json"
    library = json.loads(fixture.read_text(encoding="utf-8"))
    graph = lib_dict_to_graph_state(library)
    translated = graph_state_to_lib_dict(graph, ToolRegistryService())

    assert graph.name == "parent"
    assert graph.nodes[0].type == "workflow"
    assert translated.errors == []
    assert translated.lib_dict["nodes"][0]["type"] == "workflow"
    assert translated.lib_dict["nodes"][0]["workflow"]["schema_version"] == 2


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


def test_custom_tools_are_local_references_not_installable_packages() -> None:
    library = _graph("root")
    library["nodes"] = [
        {
            "name": "custom",
            "type": "tool",
            "tool_module": "workflow_tools.custom",
            "tool_class": "CustomTool",
            "tool_package": "__custom__",
            "tool_package_version": "local",
            "source_module": "sha256-custom-source",
            "constants": {},
        }
    ]
    registry = ToolRegistryService()

    packages, local = collect_required_packages(library, registry)
    missing_packages = _detect_missing_packages(library, registry)
    missing_tools = _detect_missing_tools(library, registry)
    rebound = rebind_lib_dict_versions(library, registry)

    assert packages == []
    assert [(item.tool_name, item.node_ids) for item in local] == [
        ("CustomTool", ["custom"])
    ]
    assert missing_packages == []
    assert missing_tools == []
    assert rebound["nodes"][0]["tool_package"] == "__custom__"
    assert rebound["nodes"][0]["tool_package_version"] == "local"


def test_owned_tool_identity_takes_precedence_over_same_named_registry_tool() -> None:
    library = _graph("root")
    library["nodes"] = [
        {
            "name": "custom",
            "type": "tool",
            "tool_module": "tools.owned_example",
            "tool_class": "ExampleTool",
            "tool_package": "__custom__",
            "tool_package_version": "local",
            "source_module": "owned-source",
            "constants": {},
        }
    ]
    translated = graph_state_to_lib_dict(lib_dict_to_graph_state(library), _registry())

    assert translated.errors == []
    for key in ("tool_module", "tool_class", "tool_package", "tool_package_version", "source_module"):
        assert translated.lib_dict["nodes"][0][key] == library["nodes"][0][key]


def test_unavailable_custom_tool_is_not_labeled_as_a_package_dependency() -> None:
    library = _graph("root")
    library["nodes"] = [
        {
            "name": "custom",
            "type": "tool",
            "tool_module": "workflow_tools.custom",
            "tool_class": "CustomTool",
            "tool_package": "__custom__",
            "tool_package_version": "local",
            "constants": {},
        }
    ]

    missing_tools = _detect_missing_tools(library, ToolRegistryService())

    assert len(missing_tools) == 1
    assert missing_tools[0].package_name is None
    assert missing_tools[0].required_version is None


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


def test_incompatible_environment_validation_kind_is_preserved() -> None:
    error = SimpleNamespace(
        kind="environment_incompatible",
        message="bioimageflow-core requirement conflicts with the active runtime",
        node="tool",
        field=None,
        edge_id=None,
        path=(),
    )

    mapped = lib_validation_error_to_graph_error(error)

    assert mapped.type == "environment_incompatible"
    assert mapped.node == "tool"
