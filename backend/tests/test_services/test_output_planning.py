"""Public output evidence survives failures without becoming mutation authority."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from bioimageflow.output_planning import OutputPlanningEvidence, OutputPlanningError
from bioimageflow_dev_tools.processing import WriteNumberFile
from tests.graph_factory import graph_state

from bioimageflow_server.models.execution import ExecutionContext
from bioimageflow_server.models.execution_runtime import ExecutionSnapshot
from bioimageflow_server.services.execution import (
    ExecutionManager,
    NullEventBus,
    OutputTemplateCorrectionUnavailable,
    _OutputRunAuthority,
    _output_source_fingerprint,
    _output_tool_types,
)
from bioimageflow_server.services.execution_progress import reduce_progress_events
from bioimageflow_server.services.graph_compiler import GraphCompiler
from bioimageflow_server.services.tool_registry import ToolRegistryService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _failed_manager(tmp_path: Path) -> tuple[ExecutionManager, object, Path]:
    storage = tmp_path / "results"
    storage.mkdir()
    registry = ToolRegistryService()
    registry.register_tool(
        "WriteNumberFile", ToolRegistryService.metadata_for_class(WriteNumberFile),
        tool_class=WriteNumberFile,
    )
    graph = graph_state(nodes=[{
        "type": "tool", "id": "write", "name": "write", "tool_name": "WriteNumberFile",
        "position": [0, 0], "parameters": {"number": 1},
    }])
    compiled = GraphCompiler(registry).compile(graph, storage_path=storage)
    assert compiled.workflow is not None, compiled.errors
    assert not compiled.errors
    evidence = OutputPlanningEvidence.capture(
        node_id="write", assets_dir=storage / "assets", tool=WriteNumberFile(),
        row_contexts=[
            {"node_name": "write", "row_index": str(index), "number": index + 1, "_ext": ""}
            for index in range(3)
        ],
        row_indexes=["0", "1", "2"],
    )
    with pytest.raises(OutputPlanningError) as failure:
        evidence.check_templates()
    manager = ExecutionManager(NullEventBus(), registry, storage_path=storage)
    context = ExecutionContext(
        execution_id="failed-run", workflow_id="wf", draft_revision=4,
        planned_node_ids=["write"],
    )
    manager.context = context
    manager.state = "running"
    manager._active_graph = graph
    manager._output_run_authority = _OutputRunAuthority(
        context, graph, graph, storage, 7,
        _output_source_fingerprint(graph, storage, registry),
        _output_tool_types(compiled.workflow),
    )
    manager._retained_progress_by_execution[context.execution_id] = manager._retained_progress_events
    manager._on_run_done(SimpleNamespace(exception=lambda: failure.value), context)
    return manager, graph, storage


async def test_collision_report_survives_status_and_retained_history(tmp_path: Path) -> None:
    manager, _graph, _storage = _failed_manager(tmp_path)
    status = manager.get_status()
    assert status.state == "idle"
    assert status.last_result is not None
    report, = status.last_result.output_planning_reports
    assert report.code == "output_path_collision"
    assert report.node_id == "write"
    assert report.correction_available
    assert report.conflicts[0].path == "result.txt"
    assert report.total_owners == 3
    assert status.node_statuses["write"].status == "failed"

    snapshot = ExecutionSnapshot(
        execution_id="failed-run", workflow_id="wf", backend="wetlands",
        target_id="local", state="running",
    )
    retained = reduce_progress_events(snapshot, manager.retained_progress())
    diagnostic = retained.jobs["write"].diagnostic
    assert diagnostic is not None and diagnostic.output_planning_report is not None
    assert not diagnostic.output_planning_report.correction_available
    assert diagnostic.output_planning_report.conflicts == report.conflicts
    manager._release_output_corrections()


async def test_correction_checks_all_rows_without_changing_the_graph_or_writing(tmp_path: Path) -> None:
    manager, graph, storage = _failed_manager(tmp_path)
    before = graph.model_dump(mode="json")
    kwargs = dict(
        execution_id="failed-run", workflow_id="wf", draft_revision=4,
        node_id="write", graph=graph, workflow_generation=7, storage_path=storage,
    )
    unchanged = manager.check_output_templates(templates={"report": "still-shared.txt"}, **kwargs)
    assert not unchanged.valid
    assert unchanged.reports[0].conflicts[0].path == "still-shared.txt"
    corrected = manager.check_output_templates(templates={"report": "result_{row_index}.txt"}, **kwargs)
    assert corrected.valid and not corrected.reports
    assert graph.model_dump(mode="json") == before
    assert not list(storage.rglob("*.txt"))
    assert manager.context is not None and manager.context.execution_id == "failed-run"
    manager._release_output_corrections()


@pytest.mark.parametrize("change", ["revision", "generation", "storage", "run", "graph"])
async def test_correction_rejects_stale_authority(tmp_path: Path, change: str) -> None:
    manager, graph, storage = _failed_manager(tmp_path)
    kwargs = dict(
        execution_id="failed-run", workflow_id="wf", draft_revision=4,
        node_id="write", graph=graph, workflow_generation=7, storage_path=storage,
        templates={"report": "result_{row_index}.txt"},
    )
    if change == "revision":
        kwargs["draft_revision"] = 5
    elif change == "generation":
        kwargs["workflow_generation"] = 8
    elif change == "storage":
        kwargs["storage_path"] = tmp_path / "other"
    elif change == "run":
        kwargs["execution_id"] = "new-run"
    else:
        edited = graph.model_copy(deep=True)
        edited.nodes[0].parameters["number"] = 99
        kwargs["graph"] = edited
    with pytest.raises(OutputTemplateCorrectionUnavailable):
        manager.check_output_templates(**kwargs)
    manager._release_output_corrections()


async def test_expired_evidence_preserves_explanation_and_withdraws_correction(tmp_path: Path) -> None:
    manager, _graph, _storage = _failed_manager(tmp_path)
    manager._release_output_corrections()
    status = manager.get_status()
    assert status.last_result is not None
    report, = status.last_result.output_planning_reports
    assert report.conflicts[0].path == "result.txt"
    assert not report.correction_available
    assert report.correction_unavailable_reason


async def test_editing_warns_only_for_current_proven_input_evidence(tmp_path: Path) -> None:
    manager, graph, storage = _failed_manager(tmp_path)
    compiler = GraphCompiler(manager.tool_registry)
    def warnings(definition):
        compiled = compiler.compile(definition, storage_path=storage)
        return manager.output_planning_warnings(definition, compiled.workflow, storage)

    assert len(warnings(graph)) == 1
    edited = graph.model_copy(deep=True)
    edited.nodes[0].output_templates["report"] = "number_{number}.txt"
    assert warnings(edited) == []
    edited.nodes[0].output_templates["report"] = "still-shared.txt"
    assert warnings(edited)[0].conflicts[0].path == "still-shared.txt"
    edited.nodes[0].parameters["number"] = 88
    assert warnings(edited) == []
    manager._release_output_corrections()
    assert warnings(graph) == []


async def test_bound_output_metadata_exposes_the_declared_file_owner() -> None:
    metadata = ToolRegistryService.metadata_for_class(WriteNumberFile)
    declaration = metadata.output_file_declarations["report"]
    assert declaration.output_role == "exact"
    assert declaration.file_group is not None
    assert declaration.file_group.kind == "per_row"
    assert declaration.description == "One file per input row"
