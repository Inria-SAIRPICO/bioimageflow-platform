"""Tests for :mod:`bioimageflow_server.services.graph_translator`."""
# pyright: reportInvalidTypeForm=false
# Rationale: image file fields use ``Annotated[Path, ImageSpec(...)]`` metadata;
# pyright can't evaluate this runtime metadata statically.

from pathlib import Path
from typing import Annotated, Any

import pytest

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool
from bioimageflow_core.types import ImageSpec, Semantic

from bioimageflow_server.models.graph import (
    ColumnRefEdge,
    GraphState,
    NodeState,
    PositionalEdge,
    PublishedInput,
    PublishedOutput,
)
from bioimageflow_server.models.tools import PackageInfo, ToolMetadata
from bioimageflow_server.services.graph_translator import (
    POSITIONAL_KEY,
    _detect_missing_packages,
    _detect_missing_tools,
    graph_state_to_lib_dict,
    graph_state_to_persisted_sections,
    lib_dict_to_graph_state,
    lib_validation_error_to_graph_error,
    rebind_lib_dict_versions,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


class _Inputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    diameter: float = 30.0


class _Outputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


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
    reg.register_package(
        "test-pkg",
        PackageInfo(
            name="test-pkg",
            installed_versions=["1.0.0", "2.0.0"],
            active_version="2.0.0",
            tools={"1.0.0": ["TProcTool", "TDfTool"], "2.0.0": ["TProcTool"]},
        ),
    )
    return reg


def test_empty_graph(registry: ToolRegistryService) -> None:
    result = graph_state_to_lib_dict(GraphState(nodes=[], edges=[]), registry)
    assert result.errors == []
    assert result.lib_dict["nodes"] == []
    assert result.lib_dict["edges"] == []
    assert result.lib_dict["config"]["storage_path"] == str(Path.cwd() / "bif_data")


def test_storage_path_is_serialized_as_absolute_runtime_path(
    registry: ToolRegistryService,
) -> None:
    result = graph_state_to_lib_dict(
        GraphState(nodes=[], edges=[]),
        registry,
        storage_path=Path("relative_outputs"),
    )

    assert result.lib_dict["config"]["storage_path"] == str(
        Path.cwd() / "relative_outputs"
    )


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
        {"id": "e", "from": "src", "to": "dst", "column": "mask", "field": "input_image"},
    ]


def test_connected_input_does_not_emit_constant(registry: ToolRegistryService) -> None:
    """Fields with an incoming column_ref edge must not appear in ``constants``.

    The library engine merges constants on top of column bindings, so a
    leftover constant (e.g. a ``None`` placeholder kept by the frontend on
    the disabled parameter widget) would clobber the upstream value.
    """
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="TProcTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dst", name="dst", tool_name="TProcTool",
                      position=(0, 0),
                      parameters={"input_image": None, "diameter": 7.0}),
        ],
        edges=[
            ColumnRefEdge(id="e", source_node="src", target_node="dst",
                          source_output="mask", target_input="input_image"),
        ],
    )
    result = graph_state_to_lib_dict(graph, registry)
    dst_dict = next(n for n in result.lib_dict["nodes"] if n["name"] == "dst")
    assert "input_image" not in dst_dict["constants"]
    assert dst_dict["constants"]["diameter"] == {"__type__": "float", "value": 7.0}


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
        out = lib_validation_error_to_graph_error(err)
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
    assert lib_validation_error_to_graph_error(pkg_err).type == "missing_package"
    assert lib_validation_error_to_graph_error(tool_err).type == "missing_tool"


def test_error_edge_attribution() -> None:
    from bioimageflow import ValidationError

    err = ValidationError(
        kind="type_mismatch", message="bad",
        node="dst", field="input_image",
        edge=("src", "dst", "input_image"),
        edge_id="my-edge-id",
    )
    out = lib_validation_error_to_graph_error(err)
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
    out = lib_validation_error_to_graph_error(err)
    assert "outer_sw/inner_sw" in out.detail
    assert "n must be >= 0" in out.detail
    assert out.node == "outer_sw/inner_sw/inner"


def test_persisted_sections_keep_graph_lossless_and_split_gui(
    registry: ToolRegistryService,
) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="n",
                name="n",
                tool_name="TProcTool",
                position=(12, 34),
                parameters={"input_image": "/a", "diameter": 42.0},
                resources={"cpu": 2},
                output_templates={"mask": "mask.tif"},
                collapsed=True,
            ),
        ],
        edges=[],
    )
    graph_section, workflow_section, gui_section, errors = graph_state_to_persisted_sections(
        graph,
        registry,
    )
    assert errors == []
    assert GraphState.model_validate(graph_section) == graph
    assert workflow_section["nodes"][0]["tool_class"] == "TProcTool"
    assert workflow_section["nodes"][0]["output_templates"] == {"mask": "mask.tif"}
    assert gui_section["nodes"]["n"]["position"] == [12.0, 34.0]
    assert gui_section["nodes"]["n"]["collapsed"] is True
    assert gui_section["nodes"]["n"]["resources"] == {"cpu": 2}
    assert gui_section["nodes"]["n"]["output_templates"] == {"mask": "mask.tif"}


def test_lib_dict_to_graph_state_reads_output_templates_without_gui() -> None:
    graph = lib_dict_to_graph_state(
        {
            "nodes": [
                {
                    "name": "n",
                    "tool_class": "TProcTool",
                    "constants": {},
                    "output_templates": {"mask": "custom_{row_index}.tif"},
                },
            ],
            "edges": [],
        }
    )
    assert graph.nodes[0].output_templates == {"mask": "custom_{row_index}.tif"}


def test_lib_dict_to_graph_state_roundtrip_with_edges_and_constants(
    registry: ToolRegistryService,
) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="src",
                name="src",
                tool_name="TProcTool",
                position=(0, 0),
                parameters={"input_image": "/a", "diameter": 1.5},
            ),
            NodeState(
                id="dst",
                name="dst",
                tool_name="TProcTool",
                position=(20, 30),
                parameters={"diameter": 2.5},
                enabled=False,
            ),
            NodeState(
                id="df",
                name="df",
                tool_name="TDfTool",
                position=(50, 60),
                parameters={},
            ),
        ],
        edges=[
            ColumnRefEdge(
                id="e_col",
                source_node="src",
                target_node="dst",
                source_output="mask",
                target_input="input_image",
            ),
            PositionalEdge(
                id="e_pos",
                source_node="dst",
                target_node="df",
                positional_index=0,
            ),
        ],
    )
    _, workflow_section, gui_section, _ = graph_state_to_persisted_sections(
        graph,
        registry,
    )
    restored = lib_dict_to_graph_state(workflow_section, gui_section)
    assert restored.nodes == graph.nodes
    assert restored.edges == graph.edges


def test_lib_dict_to_graph_state_synthesizes_legacy_positional_edges() -> None:
    graph = lib_dict_to_graph_state(
        {
            "nodes": [
                {"name": "src", "tool_class": "TProcTool", "constants": {}},
                {
                    "name": "df",
                    "tool_class": "TDfTool",
                    "constants": {},
                    "args": ["src"],
                },
            ],
            "edges": [],
        }
    )
    assert graph.edges == [
        PositionalEdge(
            id="src__to__df__pos_0",
            source_node="src",
            target_node="df",
            positional_index=0,
        )
    ]


def test_rebind_versions_updates_to_active_registry_version(
    registry: ToolRegistryService,
) -> None:
    workflow = {
        "nodes": [
            {
                "name": "n",
                "tool_class": "TProcTool",
                "tool_package": "test-pkg",
                "tool_package_version": "1.0.0",
            }
        ],
        "edges": [],
    }
    rebound = rebind_lib_dict_versions(workflow, registry)
    assert rebound["nodes"][0]["tool_package_version"] == "2.0.0"
    assert workflow["nodes"][0]["tool_package_version"] == "1.0.0"


def test_missing_package_detection_is_package_version_level(
    registry: ToolRegistryService,
) -> None:
    workflow = {
        "nodes": [
            {
                "name": "n",
                "tool_class": "TProcTool",
                "tool_package": "test-pkg",
                "tool_package_version": "9.9.9",
            }
        ],
        "edges": [],
    }
    missing = _detect_missing_packages(workflow, registry)
    assert len(missing) == 1
    assert missing[0].package_name == "test-pkg"
    assert missing[0].required_version == "9.9.9"
    assert missing[0].installed_versions == ["1.0.0", "2.0.0"]
    assert missing[0].affected_nodes == ["n"]


def test_missing_tool_detection_is_node_level(registry: ToolRegistryService) -> None:
    workflow = {
        "nodes": [
            {
                "name": "n",
                "tool_class": "RemovedTool",
                "tool_package": "test-pkg",
                "tool_package_version": "1.0.0",
            }
        ],
        "edges": [],
    }
    missing = _detect_missing_tools(workflow, registry)
    assert len(missing) == 1
    assert missing[0].node_id == "n"
    assert missing[0].tool_name == "RemovedTool"


# ---- Cache settings wired through Settings -----------------------------


_UNLIMITED = 2**31 - 1


def test_default_settings_yields_unlimited_max_executions(
    registry: ToolRegistryService,
) -> None:
    from bioimageflow_server.models.settings import Settings

    settings = Settings(deployment_mode="desktop")
    result = graph_state_to_lib_dict(
        GraphState(nodes=[], edges=[]), registry, settings=settings
    )
    config = result.lib_dict["config"]
    assert config["max_executions"] == _UNLIMITED
    assert config["max_age"] is None


def test_zero_cache_max_executions_round_trips(
    registry: ToolRegistryService,
) -> None:
    from bioimageflow_server.models.settings import Settings

    settings = Settings(deployment_mode="desktop", cache_max_executions=0)
    result = graph_state_to_lib_dict(
        GraphState(nodes=[], edges=[]), registry, settings=settings
    )
    assert result.lib_dict["config"]["max_executions"] == 0


def test_positive_cache_max_executions_round_trips(
    registry: ToolRegistryService,
) -> None:
    from bioimageflow_server.models.settings import Settings

    settings = Settings(deployment_mode="desktop", cache_max_executions=3)
    result = graph_state_to_lib_dict(
        GraphState(nodes=[], edges=[]), registry, settings=settings
    )
    assert result.lib_dict["config"]["max_executions"] == 3


def test_cache_max_age_round_trips(registry: ToolRegistryService) -> None:
    from bioimageflow_server.models.settings import Settings

    settings = Settings(deployment_mode="desktop", cache_max_age="30d")
    result = graph_state_to_lib_dict(
        GraphState(nodes=[], edges=[]), registry, settings=settings
    )
    assert result.lib_dict["config"]["max_age"] == "30d"


def test_execution_engine_round_trips(registry: ToolRegistryService) -> None:
    from bioimageflow_server.models.settings import Settings

    settings = Settings(deployment_mode="desktop", execution_engine="parsl")
    result = graph_state_to_lib_dict(
        GraphState(nodes=[], edges=[]), registry, settings=settings
    )
    assert result.lib_dict["config"]["engine"] == "parsl"


def test_no_settings_preserves_legacy_defaults(
    registry: ToolRegistryService,
) -> None:
    """Backwards-compat: callers that don't pass settings keep the old behaviour."""
    result = graph_state_to_lib_dict(GraphState(nodes=[], edges=[]), registry)
    config = result.lib_dict["config"]
    assert config["engine"] == "sequential"
    assert config["max_executions"] == 0
    assert config["max_age"] is None


# ---- GUI-created sub-workflows ----------------------------------------


def test_library_surface_supports_config_sub_workflows() -> None:
    """B1 verification: installed library exposes the v2 sub-workflow APIs.

    The platform translator can therefore derive config-driven
    ``type=sub_workflow`` nodes directly. A small platform shim adds the
    class-level proxy ``Inputs`` expected by the installed validator.
    """
    from bioimageflow import SubWorkflow, Workflow, ValidationError

    assert callable(SubWorkflow.from_config)
    assert callable(Workflow.from_dict)
    assert callable(Workflow.to_dict)
    assert callable(Workflow.plan)
    err = ValidationError(kind="parameter_invalid", message="bad", path=("outer",))
    assert err.path == ("outer",)


def test_generated_sub_workflow_config_validates_in_library(
    registry: ToolRegistryService,
) -> None:
    from bioimageflow import Workflow

    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={"image": "/tmp/input.tif"},
                sub_workflow=GraphState(
                    nodes=[
                        NodeState(
                            id="seg",
                            name="seg",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={"input_image": None, "diameter": 9.0},
                        ),
                    ],
                    edges=[],
                ),
                published_inputs=[
                    PublishedInput(
                        name="image",
                        internal_node_id="seg",
                        internal_field="input_image",
                        kind="input",
                        schema={"type": "Path"},
                    ),
                ],
                published_outputs=[
                    PublishedOutput(
                        name="mask",
                        internal_node_id="seg",
                        internal_output="mask",
                        schema={"type": "Path"},
                    ),
                ],
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)
    workflow, build_errors = Workflow.from_dict(
        result.lib_dict,
        validate_only=True,
        partial=True,
        auto_install=False,
    )

    assert result.errors == []
    assert build_errors == []
    assert workflow.validate() == []


def test_sub_workflow_node_derives_config(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={"image": "/tmp/input.tif"},
                sub_workflow=GraphState(
                    nodes=[
                        NodeState(
                            id="seg",
                            name="seg",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={"input_image": None, "diameter": 9.0},
                        ),
                    ],
                    edges=[],
                ),
                published_inputs=[
                    PublishedInput(
                        name="image",
                        internal_node_id="seg",
                        internal_field="input_image",
                        kind="input",
                        schema={"type": "Path"},
                    ),
                ],
                published_outputs=[
                    PublishedOutput(
                        name="mask",
                        internal_node_id="seg",
                        internal_output="mask",
                        schema={"type": "Path"},
                    ),
                ],
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)

    assert result.errors == []
    [node_dict] = result.lib_dict["nodes"]
    assert node_dict["type"] == "sub_workflow"
    assert node_dict["sub_workflow_type"] == "config"
    assert node_dict["constants"]["image"] == {
        "__type__": "str",
        "value": "/tmp/input.tif",
    }
    config = node_dict["config"]
    assert config["name"] == "outer"
    assert config["inputs"] == {"image": {"type": "Path"}}
    assert config["outputs"] == {"mask": {"type": "Path"}}
    assert config["nodes"][0]["name"] == "seg"
    assert config["nodes"][0]["inputs"]["input_image"] == {"from_input": "image"}
    assert config["nodes"][0]["inputs"]["diameter"] == 9.0
    assert config["output_mapping"] == {
        "mask": {"from_node": "seg", "column": "mask"},
    }


def test_nested_sub_workflow_node_derives_inline_config(
    registry: ToolRegistryService,
) -> None:
    inner_graph = GraphState(
        nodes=[
            NodeState(
                id="leaf",
                name="leaf",
                tool_name="TProcTool",
                position=(0, 0),
                parameters={"input_image": None},
            ),
        ],
        edges=[],
    )
    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={},
                sub_workflow=GraphState(
                    nodes=[
                        NodeState(
                            id="inner",
                            name="Inner",
                            tool_name="__sub_workflow__",
                            position=(0, 0),
                            parameters={},
                            sub_workflow=inner_graph,
                            published_inputs=[
                                PublishedInput(
                                    name="image",
                                    internal_node_id="leaf",
                                    internal_field="input_image",
                                    kind="input",
                                    schema={"type": "Path"},
                                ),
                            ],
                            published_outputs=[
                                PublishedOutput(
                                    name="mask",
                                    internal_node_id="leaf",
                                    internal_output="mask",
                                    schema={"type": "Path"},
                                ),
                            ],
                        ),
                    ],
                    edges=[],
                ),
                published_outputs=[
                    PublishedOutput(
                        name="mask",
                        internal_node_id="inner",
                        internal_output="mask",
                        schema={"type": "Path"},
                    ),
                ],
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)

    assert result.errors == []
    nested = result.lib_dict["nodes"][0]["config"]["nodes"][0]
    assert nested["type"] == "sub_workflow"
    assert nested["config"]["nodes"][0]["name"] == "leaf"


def test_sub_workflow_internal_nodes_are_dependency_ordered(
    registry: ToolRegistryService,
) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={},
                sub_workflow=GraphState(
                    nodes=[
                        NodeState(
                            id="dst",
                            name="dst",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={},
                        ),
                        NodeState(
                            id="src",
                            name="src",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={"input_image": "/a"},
                        ),
                    ],
                    edges=[
                        ColumnRefEdge(
                            id="e",
                            source_node="src",
                            target_node="dst",
                            source_output="mask",
                            target_input="input_image",
                        ),
                    ],
                ),
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)

    names = [node["name"] for node in result.lib_dict["nodes"][0]["config"]["nodes"]]
    assert names == ["src", "dst"]


def test_sub_workflow_internal_disabled_node_is_serialized(
    registry: ToolRegistryService,
) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={},
                sub_workflow=GraphState(
                    nodes=[
                        NodeState(
                            id="inner",
                            name="inner",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={},
                            enabled=False,
                        ),
                    ],
                    edges=[],
                ),
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)

    inner = result.lib_dict["nodes"][0]["config"]["nodes"][0]
    assert inner["enabled"] is False


def test_sub_workflow_published_output_unknown_target_is_error(
    registry: ToolRegistryService,
) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={},
                sub_workflow=GraphState(nodes=[], edges=[]),
                published_outputs=[
                    PublishedOutput(
                        name="mask",
                        internal_node_id="missing",
                        internal_output="mask",
                        schema={"type": "Path"},
                    ),
                ],
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)

    assert any(
        e.type == "parameter_invalid"
        and e.node == "outer"
        and e.field == "mask"
        and "targets unknown internal node" in e.detail
        for e in result.errors
    )


def test_sub_workflow_structural_errors_are_scoped(
    registry: ToolRegistryService,
) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="outer",
                name="Outer",
                tool_name="__sub_workflow__",
                position=(0, 0),
                parameters={},
                sub_workflow=GraphState(
                    nodes=[
                        NodeState(
                            id="dup",
                            name="a",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={},
                        ),
                        NodeState(
                            id="dup",
                            name="b",
                            tool_name="TProcTool",
                            position=(0, 0),
                            parameters={},
                        ),
                    ],
                    edges=[
                        ColumnRefEdge(
                            id="dangling",
                            source_node="missing",
                            target_node="dup",
                            source_output="mask",
                            target_input="input_image",
                        ),
                    ],
                ),
            ),
        ],
        edges=[],
    )

    result = graph_state_to_lib_dict(graph, registry)

    assert any(
        e.type == "invalid_node_id" and e.node == "outer/dup"
        for e in result.errors
    )
    assert any(
        e.type == "invalid_edge_id" and e.edge_id == "dangling"
        for e in result.errors
    )


def test_lib_dict_to_graph_state_reconstructs_config_sub_workflow() -> None:
    graph = lib_dict_to_graph_state(
        {
            "nodes": [
                {
                    "name": "outer",
                    "type": "sub_workflow",
                    "sub_workflow_type": "config",
                    "constants": {"image": {"__type__": "str", "value": "/a"}},
                    "config": {
                        "name": "outer",
                        "inputs": {"image": {"type": "Path"}},
                        "outputs": {"mask": {"type": "Path"}},
                        "nodes": [
                            {
                                "name": "seg",
                                "tool_class": "TProcTool",
                                "tool_module": "tests.fake",
                                "inputs": {
                                    "input_image": {"from_input": "image"},
                                    "diameter": 5.0,
                                },
                            }
                        ],
                        "output_mapping": {
                            "mask": {"from_node": "seg", "column": "mask"},
                        },
                    },
                },
            ],
            "edges": [],
        }
    )

    [outer] = graph.nodes
    assert outer.tool_name == "__sub_workflow__"
    assert outer.parameters == {"image": "/a"}
    assert outer.sub_workflow is not None
    assert outer.sub_workflow.nodes[0].tool_name == "TProcTool"
    assert outer.sub_workflow.nodes[0].parameters == {"diameter": 5.0}
    assert outer.published_inputs[0].name == "image"
    assert outer.published_outputs[0].name == "mask"
