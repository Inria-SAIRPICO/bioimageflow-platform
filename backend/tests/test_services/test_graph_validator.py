"""Tests for :mod:`bioimageflow_server.services.graph_validator`."""
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
)
from bioimageflow_server.models.tools import ToolMetadata
from bioimageflow_server.services.graph_validator import (
    validate_graph,
    validate_parameters,
)
from bioimageflow_server.services.session_manager import SessionManager
from bioimageflow_server.services.tool_registry import ToolRegistryService


# ---- Mock tool classes (module-level so from_dict can re-import) -----------


class ProcInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    diameter: float = 30.0


class ProcOutputs(IOModel):
    mask: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class MockProcessingTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = ProcInputs
    Outputs = ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class CompatInputs(IOModel):
    mask_input: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class CompatOutputs(IOModel):
    result: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class CompatTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = CompatInputs
    Outputs = CompatOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class IncompatInputs(IOModel):
    img: Annotated[Path, ImageSpec(semantics={Semantic.DISPLACEMENT})]


class IncompatOutputs(IOModel):
    out: Annotated[Path, ImageSpec(semantics={Semantic.LABEL})]


class IncompatTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = IncompatInputs
    Outputs = IncompatOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class IntParamInputs(IOModel):
    input_image: Annotated[Path, ImageSpec(semantics={Semantic.INTENSITY})]
    n: int = 1


class IntParamTool(ProcessingTool):
    environment = EnvironmentSpec(name="test", dependencies={})
    Inputs = IntParamInputs
    Outputs = ProcOutputs

    def process_row(self, arguments: Any) -> Any:
        return {}


class DFInputs(IOModel):
    threshold: float = 0.5


class MockDataFrameTool(DataFrameTool):
    Inputs = DFInputs


class SourceDFInputs(IOModel):
    path: str = "/tmp"


class MockSourceDataFrameTool(DataFrameTool):
    """A source-only DataFrameTool that refuses positional upstream args."""
    accepts_upstream = False
    Inputs = SourceDFInputs


_TOOL_CLASSES: dict[str, type] = {
    "MockProcessingTool": MockProcessingTool,
    "CompatTool": CompatTool,
    "IncompatTool": IncompatTool,
    "IntParamTool": IntParamTool,
    "MockDataFrameTool": MockDataFrameTool,
    "MockSourceDataFrameTool": MockSourceDataFrameTool,
}


def _meta(name: str) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        display_name=name,
        package="test-package",
        package_version="1.0.0",
        tool_type="ProcessingTool",
    )


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    for name, cls in _TOOL_CLASSES.items():
        reg.register_tool(name, _meta(name), tool_class=cls)
    return reg


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


@pytest.fixture
def session_manager() -> SessionManager:
    return SessionManager()


# ---- validate_graph -------------------------------------------------------


def test_valid_graph(registry: ToolRegistryService, session_manager: SessionManager) -> None:
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
    result = validate_graph(graph, registry, session_manager)
    assert result.valid is True
    assert "n1" in result.node_statuses
    assert result.node_statuses["n1"].status == "unexecuted"
    assert result.errors == []


def test_cycle_detected(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="a", name="a", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="b", name="b", tool_name="CompatTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="a", target_node="b",
                          source_output="mask", target_input="mask_input"),
            ColumnRefEdge(id="e2", source_node="b", target_node="a",
                          source_output="result", target_input="input_image"),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    cycle_errors = [e for e in result.errors if e.type == "cycle_detected"]
    assert len(cycle_errors) >= 1


def test_self_loop_detected(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="a", name="a", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="a", target_node="a",
                          source_output="mask", target_input="input_image"),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    cycle_errors = [e for e in result.errors if e.type == "cycle_detected"]
    assert len(cycle_errors) >= 1


def test_type_incompatible(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dst", name="dst", tool_name="IncompatTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="src", target_node="dst",
                          source_output="mask", target_input="img"),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    type_errs = [e for e in result.errors if e.type == "type_incompatible"]
    assert len(type_errs) >= 1
    assert any(e.edge_id == "e1" for e in type_errs)


def test_parameter_invalid(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="n1",
                name="n1",
                tool_name="IntParamTool",
                position=(0, 0),
                parameters={"input_image": "/a", "n": "not-a-number"},
            ),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry, session_manager)
    param_errs = [e for e in result.errors if e.type == "parameter_invalid"]
    assert len(param_errs) >= 1
    assert any(e.field == "n" and e.node == "n1" for e in param_errs)


def test_missing_connection(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry, session_manager)
    missing = [e for e in result.errors if e.type == "missing_connection"]
    assert any(e.field == "input_image" and e.node == "n1" for e in missing)


def test_connected_input_skips_parameter_validation(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    """A field that has an incoming edge should NOT be validated as a constant."""
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dst", name="dst", tool_name="CompatTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="src", target_node="dst",
                          source_output="mask", target_input="mask_input"),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    param_errs = [
        e for e in result.errors
        if e.type == "parameter_invalid" and e.node == "dst"
    ]
    assert param_errs == []


def test_disabled_node_status(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={}, enabled=False),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry, session_manager)
    assert result.node_statuses["n1"].status == "disabled"


def test_cache_hit_status(registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path) -> None:
    """A node with a matching v1 cache selection gets status=executed.

    Seeds the cache using the same ``Workflow.plan()`` logical signature
    that the validator will compute.
    """
    import pandas as pd

    from bioimageflow.cache import dataframe_publish
    from bioimageflow_server.services.graph_builder import build_workflow

    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockDataFrameTool",
                      position=(0, 0),
                      parameters={"threshold": 0.5}),
        ],
        edges=[],
    )

    workflow, _errors, _disabled = build_workflow(graph, registry, storage_path=tmp_path)
    plans = workflow.plan(dev_mode=True)
    sig = plans["n1"].logical_signature

    dataframe_publish(tmp_path, "n1", sig, pd.DataFrame({"x": [1]}))

    result = validate_graph(graph, registry, session_manager, storage_path=tmp_path, dev_mode=True)
    assert result.node_statuses["n1"].status == "executed"
    assert result.node_statuses["n1"].cached is True
    refreshed_plan = session_manager.session.to_workflow().plan(dev_mode=True)
    assert result.node_statuses["n1"].result_key == refreshed_plan["n1"].final_result_key
    assert result.node_statuses["n1"].record_id == refreshed_plan["n1"].selected_record_id


def test_cache_out_of_date(registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path) -> None:
    """A node with a prior selected result key maps to out_of_date."""
    import pandas as pd

    from bioimageflow.cache import dataframe_publish

    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockDataFrameTool",
                      position=(0, 0),
                      parameters={"threshold": 0.75}),
        ],
        edges=[],
    )

    dataframe_publish(tmp_path, "n1", "0" * 64, pd.DataFrame({"x": [1]}))

    result = validate_graph(graph, registry, session_manager, storage_path=tmp_path)
    assert result.node_statuses["n1"].status == "out_of_date"


def test_cache_unexecuted(registry: ToolRegistryService, session_manager: SessionManager, tmp_path: Path) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0),
                      parameters={"input_image": "/a"}),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry, session_manager, storage_path=tmp_path)
    assert result.node_statuses["n1"].status == "unexecuted"


def test_missing_package_surfaced(session_manager: SessionManager) -> None:
    reg = ToolRegistryService()
    reg.register_tool(
        "Missing",
        ToolMetadata(
            name="Missing",
            display_name="Missing",
            package="does-not-exist",
            package_version="0.0.1",
            tool_type="ProcessingTool",
        ),
    )
    graph = GraphState(
        nodes=[NodeState(id="n1", name="n1", tool_name="Missing",
                         position=(0, 0), parameters={})],
        edges=[],
    )
    result = validate_graph(graph, reg, session_manager)
    assert any(e.type == "missing_package" for e in result.errors)


def test_multiple_errors_not_short_circuited(registry: ToolRegistryService, session_manager: SessionManager) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="IntParamTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "n": "bad"}),
            NodeState(id="n2", name="n2", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry, session_manager)
    types = {e.type for e in result.errors}
    assert "parameter_invalid" in types
    assert "missing_connection" in types


def test_dataframe_producer_without_outputs_skips_type_check(
    registry: ToolRegistryService, session_manager: SessionManager,
) -> None:
    """DataFrameTool with no Outputs should not trigger type_incompatible."""
    graph = GraphState(
        nodes=[
            NodeState(id="df", name="df", tool_name="MockDataFrameTool",
                      position=(0, 0), parameters={}),
            NodeState(id="dst", name="dst", tool_name="CompatTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="df", target_node="dst",
                          source_output="anything", target_input="mask_input"),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    assert not any(e.type == "type_incompatible" for e in result.errors)


# ---- validate_parameters ---------------------------------------------------


def test_validate_parameters_valid(registry: ToolRegistryService) -> None:
    result = validate_parameters(
        "n1", "IntParamTool", {"n": 5}, registry, storage_path=None
    )
    assert result.valid is True
    assert list(result.node_statuses.keys()) == ["n1"]


def test_validate_parameters_invalid(registry: ToolRegistryService) -> None:
    result = validate_parameters(
        "n1", "IntParamTool", {"n": "not-an-int"}, registry, storage_path=None
    )
    assert result.valid is False
    assert any(
        e.type == "parameter_invalid" and e.field == "n" for e in result.errors
    )


def test_validate_parameters_rejects_binding(registry: ToolRegistryService) -> None:
    result = validate_parameters(
        "n1",
        "MockProcessingTool",
        {"input_image": {"node_id": "up", "output": "mask"}},
        registry,
        storage_path=None,
    )
    assert result.valid is False
    assert any(
        e.type == "parameter_invalid" and e.field == "input_image"
        for e in result.errors
    )


def test_validate_parameters_unknown_tool(registry: ToolRegistryService) -> None:
    result = validate_parameters(
        "n1", "NoSuchTool", {}, registry, storage_path=None
    )
    assert result.valid is False
    assert any(e.type == "missing_tool" for e in result.errors)


def test_validate_parameters_cache_status_no_dir(
    registry: ToolRegistryService, tmp_path: Path
) -> None:
    result = validate_parameters(
        "n1", "IntParamTool", {"n": 5}, registry, storage_path=tmp_path
    )
    assert result.node_statuses["n1"].status == "unexecuted"


def test_validate_parameters_cache_status_existing_dir(
    registry: ToolRegistryService, tmp_path: Path
) -> None:
    (tmp_path / "data" / "n1" / "legacy").mkdir(parents=True)

    result = validate_parameters(
        "n1", "IntParamTool", {"n": 5}, registry, storage_path=tmp_path
    )
    assert result.node_statuses["n1"].status == "unexecuted"


def test_validate_parameters_does_not_call_compute_signature_hash(
    registry: ToolRegistryService, monkeypatch: Any
) -> None:
    """PATCH must not compute signature hashes — it has no upstream context."""
    called = {"count": 0}

    def fail(*args: Any, **kwargs: Any) -> Any:
        called["count"] += 1
        raise AssertionError("compute_signature_hash must not be called in PATCH")

    monkeypatch.setattr(
        "bioimageflow.cache.compute_signature_hash", fail, raising=True
    )
    result = validate_parameters(
        "n1", "IntParamTool", {"n": 5}, registry, storage_path=None
    )
    assert called["count"] == 0
    assert result is not None


def test_positional_edge_into_source_tool_produces_source_tool_upstream_error(
    registry: ToolRegistryService, session_manager: SessionManager,
) -> None:
    """Wiring a positional edge into a source DataFrameTool yields source_tool_upstream."""
    graph = GraphState(
        nodes=[
            NodeState(id="upstream", name="upstream", tool_name="MockDataFrameTool",
                      position=(0, 0), parameters={}),
            NodeState(id="source", name="source", tool_name="MockSourceDataFrameTool",
                      position=(100, 0), parameters={"path": "/tmp"}),
        ],
        edges=[
            PositionalEdge(id="e_pos", source_node="upstream", target_node="source",
                           positional_index=0),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    source_errs = [e for e in result.errors if e.type == "source_tool_upstream"]
    assert len(source_errs) >= 1
    assert any(e.edge_id == "e_pos" for e in source_errs)


def test_positional_edge_into_processing_tool_is_rejected(
    registry: ToolRegistryService, session_manager: SessionManager,
) -> None:
    """Forged header edges cannot target ProcessingTool nodes."""
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/tmp/x.tif"}),
            NodeState(id="dst", name="dst", tool_name="CompatTool",
                      position=(100, 0), parameters={}),
        ],
        edges=[
            PositionalEdge(id="e_pos", source_node="src", target_node="dst",
                           positional_index=0),
        ],
    )
    result = validate_graph(graph, registry, session_manager)
    positional_errs = [
        e for e in result.errors
        if e.type == "parameter_invalid" and e.edge_id == "e_pos"
    ]
    assert len(positional_errs) == 1
    assert "cannot accept positional DataFrame inputs" in positional_errs[0].detail
