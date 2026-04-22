"""Tests for :mod:`bioimageflow_server.services.graph_validator`."""

from pathlib import Path
from typing import Any

import pytest

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
from bioimageflow_server.services.tool_registry import ToolRegistryService


# ---- Mock tools -------------------------------------------------------------


def _build_tool_classes() -> dict[str, type]:
    from bioimageflow.dataframe_tool import DataFrameTool
    from bioimageflow_core.environment import EnvironmentSpec
    from bioimageflow_core.tool import IOModel, ProcessingTool
    from bioimageflow_core.types import ImagePath, Semantic

    class ProcInputs(IOModel):
        input_image: ImagePath(semantics={Semantic.INTENSITY})
        diameter: float = 30.0

    class ProcOutputs(IOModel):
        mask: ImagePath(semantics={Semantic.LABEL})

    class MockProcessingTool(ProcessingTool):
        environment = EnvironmentSpec(name="test", dependencies={})
        Inputs = ProcInputs
        Outputs = ProcOutputs

        def process_row(self, arguments: Any) -> Any:
            return {}

    class CompatInputs(IOModel):
        mask_input: ImagePath(semantics={Semantic.LABEL})

    class CompatOutputs(IOModel):
        result: ImagePath(semantics={Semantic.LABEL})

    class CompatTool(ProcessingTool):
        environment = EnvironmentSpec(name="test", dependencies={})
        Inputs = CompatInputs
        Outputs = CompatOutputs

        def process_row(self, arguments: Any) -> Any:
            return {}

    class IncompatInputs(IOModel):
        img: ImagePath(semantics={Semantic.DISPLACEMENT})

    class IncompatOutputs(IOModel):
        out: ImagePath(semantics={Semantic.LABEL})

    class IncompatTool(ProcessingTool):
        environment = EnvironmentSpec(name="test", dependencies={})
        Inputs = IncompatInputs
        Outputs = IncompatOutputs

        def process_row(self, arguments: Any) -> Any:
            return {}

    class IntParamInputs(IOModel):
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

    return {
        "MockProcessingTool": MockProcessingTool,
        "CompatTool": CompatTool,
        "IncompatTool": IncompatTool,
        "IntParamTool": IntParamTool,
        "MockDataFrameTool": MockDataFrameTool,
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
    for name, cls in _build_tool_classes().items():
        reg.register_tool(name, _meta(name), tool_class=cls)
    return reg


@pytest.fixture(autouse=True)
def _clear_active_workflow() -> Any:
    from bioimageflow.node import set_active_workflow

    set_active_workflow(None)
    yield
    set_active_workflow(None)


# ---- validate_graph -------------------------------------------------------


def test_valid_graph(registry: ToolRegistryService) -> None:
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
    result = validate_graph(graph, registry)
    assert result.valid is True
    assert "n1" in result.node_statuses
    assert result.node_statuses["n1"].status == "unexecuted"
    assert result.errors == []


def test_cycle_detected(registry: ToolRegistryService) -> None:
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
            # Feed b's result back into a → cycle
            ColumnRefEdge(id="e2", source_node="b", target_node="a",
                          source_output="result", target_input="input_image"),
        ],
    )
    result = validate_graph(graph, registry)
    cycle_errors = [e for e in result.errors if e.type == "cycle_detected"]
    assert len(cycle_errors) == 1
    assert "->" in cycle_errors[0].detail or "Cycle" in cycle_errors[0].detail


def test_self_loop_detected(registry: ToolRegistryService) -> None:
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
    result = validate_graph(graph, registry)
    cycle_errors = [e for e in result.errors if e.type == "cycle_detected"]
    assert len(cycle_errors) == 1
    assert "Self-loop" in cycle_errors[0].detail
    assert "a" in cycle_errors[0].detail


def test_type_incompatible(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dst", name="dst", tool_name="IncompatTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[
            # MockProcessingTool.mask is Semantic.LABEL but IncompatTool.img
            # requires Semantic.DISPLACEMENT → incompatible.
            ColumnRefEdge(id="e1", source_node="src", target_node="dst",
                          source_output="mask", target_input="img"),
        ],
    )
    result = validate_graph(graph, registry)
    type_errs = [e for e in result.errors if e.type == "type_incompatible"]
    assert len(type_errs) == 1
    assert type_errs[0].edge_id == "e1"


def test_parameter_invalid(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(
                id="n1",
                name="n1",
                tool_name="IntParamTool",
                position=(0, 0),
                # Pydantic rejects "not-a-number" for int field n
                parameters={"input_image": "/a", "n": "not-a-number"},
            ),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry)
    param_errs = [e for e in result.errors if e.type == "parameter_invalid"]
    assert len(param_errs) >= 1
    assert any(e.field == "n" and e.node == "n1" for e in param_errs)


def test_missing_connection(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            # MockProcessingTool has required input_image; we omit it.
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={}),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry)
    missing = [e for e in result.errors if e.type == "missing_connection"]
    assert any(e.field == "input_image" and e.node == "n1" for e in missing)


def test_connected_input_skips_parameter_validation(registry: ToolRegistryService) -> None:
    """A field that has an incoming edge should NOT be validated as a constant."""
    graph = GraphState(
        nodes=[
            NodeState(id="src", name="src", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={"input_image": "/a"}),
            NodeState(id="dst", name="dst", tool_name="CompatTool",
                      position=(0, 0), parameters={"mask_input": "garbage"}),
        ],
        edges=[
            ColumnRefEdge(id="e1", source_node="src", target_node="dst",
                          source_output="mask", target_input="mask_input"),
        ],
    )
    result = validate_graph(graph, registry)
    param_errs = [
        e for e in result.errors
        if e.type == "parameter_invalid" and e.node == "dst"
    ]
    assert param_errs == []


def test_disabled_node_status(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={}, enabled=False),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry)
    assert result.node_statuses["n1"].status == "disabled"


def test_cache_hit_status(registry: ToolRegistryService, tmp_path: Path) -> None:
    """A node with a matching cache directory gets status=executed."""
    from bioimageflow.cache import compute_env_hash, compute_signature_hash
    from bioimageflow.storage import create_hash_dir, get_node_dir
    from bioimageflow.validation import get_source_hash

    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0),
                      parameters={"input_image": "/a"}),
        ],
        edges=[],
    )

    tool_class = registry.get_tool_class("MockProcessingTool")
    assert tool_class is not None
    env_hash = compute_env_hash({})
    sig = compute_signature_hash(
        tool_class.__name__,
        "1.0.0",
        env_hash,
        {"input_image": "/a"},
        {},
        source_hash=get_source_hash(tool_class),
    )
    node_dir = get_node_dir(tmp_path, "n1")
    hash_dir = create_hash_dir(node_dir, sig)
    (hash_dir / "dataframe.parquet").write_bytes(b"dummy")

    result = validate_graph(graph, registry, storage_path=tmp_path, dev_mode=True)
    assert result.node_statuses["n1"].status == "executed"
    assert result.node_statuses["n1"].cached is True


def test_cache_out_of_date(registry: ToolRegistryService, tmp_path: Path) -> None:
    """A previously executed node whose parameters changed is out_of_date."""
    from bioimageflow.storage import create_hash_dir, get_node_dir

    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "diameter": 99.0}),
        ],
        edges=[],
    )

    # Pre-populate a stale cache directory with a non-matching hash.
    node_dir = get_node_dir(tmp_path, "n1")
    create_hash_dir(node_dir, "0" * 64)

    result = validate_graph(graph, registry, storage_path=tmp_path)
    assert result.node_statuses["n1"].status == "out_of_date"


def test_cache_unexecuted(registry: ToolRegistryService, tmp_path: Path) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="MockProcessingTool",
                      position=(0, 0),
                      parameters={"input_image": "/a"}),
        ],
        edges=[],
    )
    result = validate_graph(graph, registry, storage_path=tmp_path)
    assert result.node_statuses["n1"].status == "unexecuted"


def test_missing_package_surfaced() -> None:
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
    result = validate_graph(graph, reg)
    assert any(e.type == "missing_package" for e in result.errors)


def test_multiple_errors_not_short_circuited(registry: ToolRegistryService) -> None:
    graph = GraphState(
        nodes=[
            NodeState(id="n1", name="n1", tool_name="IntParamTool",
                      position=(0, 0),
                      parameters={"input_image": "/a", "n": "bad"}),
            NodeState(id="n2", name="n2", tool_name="MockProcessingTool",
                      position=(0, 0), parameters={}),  # missing required
        ],
        edges=[],
    )
    result = validate_graph(graph, registry)
    types = {e.type for e in result.errors}
    assert "parameter_invalid" in types
    assert "missing_connection" in types


def test_dataframe_producer_without_outputs_skips_type_check(
    registry: ToolRegistryService,
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
    result = validate_graph(graph, registry)
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
    from bioimageflow.storage import create_hash_dir, get_node_dir

    node_dir = get_node_dir(tmp_path, "n1")
    create_hash_dir(node_dir, "0" * 64)

    result = validate_parameters(
        "n1", "IntParamTool", {"n": 5}, registry, storage_path=tmp_path
    )
    assert result.node_statuses["n1"].status == "out_of_date"


def test_validate_parameters_does_not_call_compute_signature_hash(
    registry: ToolRegistryService, monkeypatch: Any
) -> None:
    """PATCH must not compute signature hashes — it has no upstream context."""
    import bioimageflow_server.services.graph_validator as gv

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
