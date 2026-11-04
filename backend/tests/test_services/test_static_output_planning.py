"""Fresh editing warnings use library facts from the actual bound tool."""

from pathlib import Path

import pytest
from tests.graph_factory import graph_state

from platform_test_tools.output_planning import (
    ConflictingOutputs,
    DistinctOutputs,
    TimestampOutputs,
    UnknownNumbers,
)
from bioimageflow_server.models.graph import GraphState
from bioimageflow_server.services.execution import ExecutionManager, NullEventBus
from bioimageflow_server.services.graph_validator import GraphValidationService
from bioimageflow_server.services.tool_registry import ToolRegistryService


def _registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    # The same-named catalog entry is deliberately distinct from the explicit
    # module/class bindings carried by the graph below.
    registry.register_tool(
        "CatalogAlias", ToolRegistryService.metadata_for_class(DistinctOutputs),
        tool_class=DistinctOutputs,
    )
    registry.register_tool(
        "UnknownNumbers", ToolRegistryService.metadata_for_class(UnknownNumbers),
        tool_class=UnknownNumbers,
    )
    return registry


def _node(tool: type, node_id: str = "write") -> dict:
    return {
        "type": "tool", "id": node_id, "name": node_id,
        "tool_name": "CatalogAlias", "tool_module": tool.__module__,
        "tool_class": tool.__name__, "parameters": {"number": 7},
        "position": [0, 0],
    }


def _validate(graph: GraphState, tmp_path: Path):
    registry = _registry()
    manager = ExecutionManager(NullEventBus(), registry, storage_path=tmp_path)
    assert not manager._output_corrections
    return GraphValidationService(
        registry, output_warning_provider=manager.output_planning_warnings,
    ).validate(graph, storage_path=tmp_path)


@pytest.mark.parametrize("nested", [False, True])
def test_fresh_constant_collision_warns_without_blocking_or_science(tmp_path: Path, nested: bool) -> None:
    child = graph_state(nodes=[_node(ConflictingOutputs)])
    graph = graph_state(nodes=[{
        "type": "workflow", "id": "nested", "name": "nested", "workflow": child,
        "bindings": {}, "position": [0, 0],
    }]) if nested else child
    result = _validate(graph, tmp_path)
    assert result.valid, result.errors
    assert result.errors == []
    report, = result.output_planning_warnings
    assert report.node_id == ("nested/write" if nested else "write")
    assert report.code == "output_path_collision"
    assert report.conflicts[0].path == "same.txt"
    assert {field.field for field in report.fields} == {"left", "right"}
    assert not report.correction_available
    assert not list(tmp_path.rglob("*.txt"))


@pytest.mark.parametrize("tool", [DistinctOutputs, TimestampOutputs])
def test_distinct_or_unknown_time_destinations_are_silent(tmp_path: Path, tool: type) -> None:
    result = _validate(graph_state(nodes=[_node(tool)]), tmp_path)
    assert result.valid, result.errors
    assert result.output_planning_warnings == []
    assert not list(tmp_path.rglob("*.txt"))


def test_unknown_column_bound_rows_are_silent_without_executing_upstream(tmp_path: Path) -> None:
    write = _node(ConflictingOutputs)
    write["parameters"] = {}
    graph = graph_state(nodes=[{
        "type": "tool", "id": "numbers", "name": "numbers", "tool_name": "UnknownNumbers",
        "position": [0, 0], "parameters": {},
    }, write], edges=[{
        "type": "column", "id": "numbers-write", "source_node": "numbers",
        "source_output": "number", "target_node": "write", "target_input": "number",
    }])
    result = _validate(graph, tmp_path)
    assert result.valid, result.errors
    assert result.output_planning_warnings == []
    assert not list(tmp_path.rglob("*.txt"))


def test_explicit_root_and_nested_bindings_remain_independent(tmp_path: Path) -> None:
    child = graph_state(nodes=[_node(ConflictingOutputs)])
    graph = graph_state(nodes=[_node(DistinctOutputs, "root"), {
        "type": "workflow", "id": "nested", "name": "nested", "workflow": child,
        "bindings": {}, "position": [0, 0],
    }])
    result = _validate(graph, tmp_path)
    assert result.valid, result.errors
    assert [report.node_id for report in result.output_planning_warnings] == ["nested/write"]
