"""Tests for :mod:`bioimageflow_server.services.graph_builder`."""
# pyright: reportInvalidTypeForm=false
# Rationale: image file fields use ``Annotated[Path, ImageSpec(...)]`` metadata;
# pyright can't evaluate this runtime metadata statically.

import hashlib
import os
from pathlib import Path
from typing import Annotated, Any

import pytest
from tests.graph_factory import graph_state

from bioimageflow.dataframe_tool import DataFrameTool
from bioimageflow_core.environment import EnvironmentSpec
from bioimageflow_core.tool import IOModel, ProcessingTool, RowConsumption
from bioimageflow_core.types import ImageSpec, Semantic

from bioimageflow_server.models.graph import (
    ColumnEdge,
    ToolNodeState,
    DataFrameEdge,
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_artifacts import OwnedWorkflowSources


# ---- Mock tool classes (module-level so from_dict can re-import) -----------


class ProcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    diameter: float = 30.0
    model: str = "default"


class ProcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class MockProcessingTool(ProcessingTool):

    row_consumption = RowConsumption.MAPPED
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

    row_consumption = RowConsumption.MAPPED
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
        row_consumption="mapped" if tool_type == "ProcessingTool" else None,
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


def test_empty_graph(registry: ToolRegistryService, tmp_path: Path) -> None:
    workflow, errors, disabled = build_workflow(
        graph_state(nodes=[], edges=[]), registry, storage_path=tmp_path
    )
    assert errors == []
    assert workflow.nodes == {}
    assert disabled == set()


def test_single_valid_node(registry: ToolRegistryService, tmp_path: Path) -> None:
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
    workflow, errors, _disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )
    assert errors == []
    assert "n1" in workflow.nodes
    assert workflow.nodes["n1"].name == "n1"


def test_built_workflow_uses_wetlands(
    registry: ToolRegistryService, tmp_path: Path
) -> None:
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

    workflow, errors, _disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )

    assert errors == []
    assert workflow.engine_type == "wetlands"
    assert workflow.execution == "parallel"


@pytest.mark.parametrize("catalog_kind", ["dataframe", "higher_processing_floor"])
def test_owned_processing_resources_follow_captured_source_not_catalog(
    tmp_path: Path, catalog_kind: str,
) -> None:
    """Materialize real owned bytes before testing the platform adapter boundary."""
    from bioimageflow import NodeResourceOverrides, Workflow
    from bioimageflow_core import ResourceSpec

    source = """from bioimageflow_core import IOModel, ProcessingTool, RowConsumption, ResourceSpec, EnvironmentSpec
class Outputs(IOModel):
    value: int
class BoundTool(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name='binding-test', dependencies={})
    resources = ResourceSpec(cpu=2)
    Outputs = Outputs
    def process_row(self, arguments, *, context=None):
        return self.Outputs(value=1)
"""
    record = {
        "id": "bound-source", "module": "bound", "filename": "bound.py",
        "source_hash": hashlib.sha256(source.encode()).hexdigest(), "source": source,
    }
    node = {
        "type": "tool", "name": "bound", "tool_module": "bound",
        "tool_class": "BoundTool", "tool_package": None,
        "tool_package_version": None, "source_module": record["id"], "constants": {},
        "resource_overrides": NodeResourceOverrides(cpu=3).to_dict(),
    }
    payload = {
        "archive_version": 1, "custom_sources": [record],
        "workflow": {
            "schema_version": 2, "name": "bound", "display_name": "Bound",
            "nodes": [node], "edges": [], "interface": {"inputs": [], "outputs": []},
            "config": {"engine": "wetlands", "execution": "sequential"},
        },
    }
    # This control uses the actual public loader and actual source class. It
    # neither provisions a worker nor computes a mocked result.
    control = Workflow.from_dict(payload, storage_path=tmp_path / "control", auto_install=False)
    assert isinstance(control.nodes["bound"].tool, ProcessingTool)
    assert type(control.nodes["bound"].tool).__name__ == "BoundTool"
    assert control.nodes["bound"].effective_resources.cpu == 3
    assert control.engine_type == "wetlands"
    node["resource_overrides"]["cpu"] = 1
    with pytest.raises(ValueError, match="below tool floor 2"):
        Workflow.from_dict(payload, storage_path=tmp_path / "invalid-control", auto_install=False)
    node["resource_overrides"]["cpu"] = 3

    from bioimageflow_server.services.graph_translator import lib_dict_to_graph_state
    graph = lib_dict_to_graph_state(payload["workflow"])
    owned = OwnedWorkflowSources(tmp_path / "owned")
    staged = owned.stage([record])
    try:
        owned.publish(staged)
    finally:
        owned.discard(staged)
    registry = ToolRegistryService()
    if catalog_kind == "dataframe":
        catalog_class = MockDataFrameTool
    else:
        class CatalogProcessingTool(MockProcessingTool):
            row_consumption = RowConsumption.MAPPED
            resources = ResourceSpec(cpu=8)
        catalog_class = CatalogProcessingTool
    registry.register_tool("BoundTool", _make_metadata("BoundTool", catalog_class), tool_class=catalog_class)
    built = build_workflow(graph, registry, storage_path=tmp_path / "owned" / "outputs")

    assert built.errors == []
    assert isinstance(built.workflow.nodes["bound"].tool, ProcessingTool)
    assert type(built.workflow.nodes["bound"].tool).__name__ == "BoundTool"
    assert built.workflow.nodes["bound"].effective_resources.cpu == 3
    assert built.workflow.engine_type == "wetlands"
    assert built.workflow.execution == "sequential"
    graph.nodes[0].resources.cpu = 1
    invalid = build_workflow(graph, registry, storage_path=tmp_path / "owned" / "invalid-outputs")
    assert any(
        error.type == "parameter_invalid" and error.node == "bound"
        and "below tool floor 2" in error.detail
        for error in invalid.errors
    )


@pytest.mark.parametrize("case", ["preserve", "rebind", "missing_version", "missing_class", "dataframe_resources", "export_resources", "metadata"])
def test_portable_version_binding_uses_public_loaded_class_and_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    """Two local package versions distinguish executable identity, not only wire fields."""
    from bioimageflow import Workflow
    from bioimageflow.tool_loader import load_versioned_package, unload_versioned_package
    from bioimageflow_server.services.graph_translator import lib_dict_to_graph_state

    package = "binding_probe"
    store = Path(os.environ["BIOIMAGEFLOW_TOOL_STORE"])
    definitions = {
        "1.0.0": """from bioimageflow_core import IOModel, ProcessingTool, RowConsumption, EnvironmentSpec
class Outputs(IOModel):
    value: int
class BoundTool(ProcessingTool):
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(name='bound-v1', dependencies={})
    Outputs = Outputs
    def process_row(self, arguments, *, context=None):
        return self.Outputs(value=1)
""",
        "2.0.0": """from bioimageflow import DataFrameTool
from bioimageflow_core import IOModel
class Outputs(IOModel):
    value: int
class BoundTool(DataFrameTool):
    accepts_upstream = False
    Outputs = Outputs
""",
    }
    for version, source in definitions.items():
        directory = store / package / version / package
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text(source)
        from tests.fixtures.package_metadata import write_package_metadata
        write_package_metadata(directory, version)
    portable = {
        "schema_version": 2, "name": "bound", "display_name": "Bound",
        "nodes": [{
            "type": "tool", "name": "bound", "tool_module": package,
            "tool_class": "BoundTool", "tool_package": package,
            "tool_package_version": "1.0.0", "constants": {},
        }],
        "edges": [], "interface": {"inputs": [], "outputs": []},
        "config": {"engine": "wetlands", "execution": "sequential"},
    }
    try:
        first = load_versioned_package(package, "1.0.0", store)
        second = load_versioned_package(package, "2.0.0", store)
        control = Workflow.from_dict(portable, storage_path=tmp_path / "control", auto_install=False)
        assert type(control.nodes["bound"].tool) is first.BoundTool
        assert control.engine_type == "wetlands"
        registry = ToolRegistryService()
        metadata = _make_metadata("BoundTool", second.BoundTool).model_copy(update={
            "package": package, "package_version": "2.0.0",
        })
        registry.register_tool("BoundTool", metadata, tool_class=second.BoundTool)
        if case == "rebind":
            from bioimageflow_server.services.graph_translator import rebind_lib_dict_versions
            portable = rebind_lib_dict_versions(portable, registry)
        elif case == "missing_version":
            portable["nodes"][0]["tool_package_version"] = "9.0.0"
        elif case == "missing_class":
            portable["nodes"][0]["tool_class"] = "MissingClass"
        elif case in {"dataframe_resources", "export_resources"}:
            from bioimageflow import NodeResourceOverrides
            portable["nodes"][0]["tool_package_version"] = "2.0.0"
            portable["nodes"][0]["resource_overrides"] = NodeResourceOverrides(cpu=3).to_dict()
            registry = ToolRegistryService()
        elif case == "metadata":
            registry = ToolRegistryService()

        if case == "export_resources":
            from bioimageflow_server.services.workflow_archive import BioImageFlowWorkflowArchiveAdapter
            destination = tmp_path / "invalid.zip"
            with pytest.raises(ValueError, match="ProcessingTool"):
                BioImageFlowWorkflowArchiveAdapter().export_archive(
                    portable, destination, storage_path=tmp_path / "export-results",
                )
            assert not destination.exists()
            return

        graph = lib_dict_to_graph_state(portable)
        if case == "missing_class":
            graph.nodes[0].tool_name = "BoundTool"
        before = graph.model_dump(mode="json")
        calls = []
        real_from_dict = Workflow.from_dict
        def materialize(*args, **kwargs):
            calls.append(kwargs)
            return real_from_dict(*args, **kwargs)
        monkeypatch.setattr(Workflow, "from_dict", materialize)
        built = build_workflow(graph, registry, storage_path=tmp_path / "outputs")
        assert len(calls) == 1
        assert graph.model_dump(mode="json") == before
        if case in {"missing_version", "missing_class"}:
            assert any(error.node == "bound" for error in built.errors)
            assert "bound" not in built.workflow.nodes
        elif case == "dataframe_resources":
            assert any(
                error.type == "parameter_invalid" and error.node == "bound"
                and error.field == "resources" and "ProcessingTool" in error.detail
                for error in built.errors
            )
        elif case == "metadata":
            from bioimageflow_server.services.graph_validator import _validation_from_compilation
            validation = _validation_from_compilation(graph, built)
            metadata = validation.node_tools["bound"]
            assert metadata.tool_type == "ProcessingTool"
            assert metadata.outputs["value"]["type"] == "int"
            assert (metadata.package, metadata.package_version) == (package, "1.0.0")
            assert metadata.source_kind == "package"
            assert metadata.editable is False
        else:
            assert built.errors == []
            expected_class, expected_engine = (
                (second.BoundTool, "direct") if case == "rebind"
                else (first.BoundTool, "wetlands")
            )
            assert (type(built.workflow.nodes["bound"].tool), built.workflow.engine_type) == (
                expected_class, expected_engine,
            )

    finally:
        for version in definitions:
            unload_versioned_package(package, version)


def test_processing_tool_can_feed_dataframe_tool_positionally(
    registry: ToolRegistryService, tmp_path: Path
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

    workflow, errors, _disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )

    assert errors == []
    assert workflow.nodes["df"]._args == [workflow.nodes["proc"]]


def test_missing_tool_error(registry: ToolRegistryService, tmp_path: Path) -> None:
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
    _workflow, errors, _disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )
    assert len(errors) == 1
    assert errors[0].type == "missing_tool"
    assert errors[0].node == "n1"


def test_missing_package_error(tmp_path: Path) -> None:
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
            row_consumption="mapped",
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
    _workflow, errors, _disabled = build_workflow(
        graph, reg, storage_path=tmp_path
    )
    assert len(errors) == 1
    assert errors[0].type == "missing_package"
    assert errors[0].node == "n1"


def test_disabled_node_excluded(
    registry: ToolRegistryService, tmp_path: Path
) -> None:
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
    _workflow, errors, disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )
    assert disabled == {"n1"}
    assert errors == []


def test_column_edge(registry: ToolRegistryService, tmp_path: Path) -> None:
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
    workflow, errors, _disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )
    assert errors == []
    assert set(workflow.nodes.keys()) == {"src", "dst"}
    dst = workflow.nodes["dst"]
    assert "mask_input" in dst._column_bindings
    assert dst._column_bindings["mask_input"].column == "mask"


def test_dataframe_edges_retain_explicit_positions(
    registry: ToolRegistryService, tmp_path: Path
) -> None:
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
    workflow, errors, _disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )
    assert errors == []
    df = workflow.nodes["df"]
    arg_names = [a.name for a in df._args]
    assert arg_names == ["s2", "s3", "s1"]


def test_mixed_graph(registry: ToolRegistryService, tmp_path: Path) -> None:
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
    workflow, errors, disabled = build_workflow(
        graph, registry, storage_path=tmp_path
    )
    assert "good" in workflow.nodes
    assert "disabled" in disabled
    assert any(e.type == "missing_tool" and e.node == "missing" for e in errors)
