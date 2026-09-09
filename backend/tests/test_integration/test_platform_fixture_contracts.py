"""Certify workflow fixtures before they are reused by platform journeys."""

import os
from pathlib import Path

import pytest
from bioimageflow_server.models.graph import ColumnEdge
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.graph_validator import validate_graph
from bioimageflow_server.services.result_store import ResultStoreService
from tests.platform_fixtures import dataframe_chain, local_registry, worker_chain


def test_dataframe_fixture_validates_compiles_and_preserves_rows(
    tmp_path: Path,
) -> None:
    graph = dataframe_chain()
    registry = local_registry()
    validation = validate_graph(graph, registry, storage_path=tmp_path)
    assert validation.valid, validation.errors
    assert registry.get_tool("SourceNumbers").accepts_upstream is False
    assert registry.get_tool("AddOffset").accepts_upstream is True
    assert set(registry.get_tool("AddOffset").inputs) == {"offset"}

    built = build_workflow(graph, registry, storage_path=tmp_path)
    assert built.errors == []
    # DataFrame-only graphs use Direct regardless of the portable preference.
    # This is the minimal local main-process regression, not Wetlands coverage.
    assert built.workflow.engine_type == "direct"
    assert built.workflow.execution == "sequential"
    built.workflow.compute()

    result = ResultStoreService(storage_path=tmp_path, tool_registry=registry)
    dataframe = result.get_latest_dataframe("offset")
    assert dataframe is not None
    assert list(dataframe.index) == ["row0", "row1", "row2"]
    assert dataframe.to_dict(orient="list") == {
        "value": [2, 3, 4], "shifted": [7, 8, 9],
    }


def test_column_cannot_replace_whole_dataframe_or_bind_constant_parameter(
    tmp_path: Path,
) -> None:
    graph = dataframe_chain()
    graph.edges = [
        ColumnEdge(
            type="column", id="wrong-column-binding", source_node="source",
            source_output="value", target_node="offset", target_input="offset",
        ),
    ]
    validation = validate_graph(graph, local_registry(), storage_path=tmp_path)
    assert not validation.valid
    assert len(validation.errors) == 1
    error = validation.errors[0]
    assert (error.type, error.node, error.field, error.edge_id) == (
        "type_incompatible", "offset", "offset", "wrong-column-binding",
    )
    assert "requires a constant" in error.detail


@pytest.mark.external
@pytest.mark.slow
@pytest.mark.serial
def test_processing_fixture_runs_in_real_sequential_wetlands_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provision a disposable worker; no transport or execution substitutes."""
    from bioimageflow.env_manager import _reset_shared_manager, get_shared_environment_manager

    monkeypatch.setenv("BIOIMAGEFLOW_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("BIOIMAGEFLOW_WETLANDS", str(tmp_path / "wetlands"))
    monkeypatch.setenv("BIOIMAGEFLOW_TOOL_STORE", str(tmp_path / "tool_packages"))
    _reset_shared_manager()
    try:
        registry = local_registry()
        graph = worker_chain()
        validation = validate_graph(graph, registry, storage_path=tmp_path / "results")
        assert validation.valid, validation.errors
        built = build_workflow(graph, registry, storage_path=tmp_path / "results")
        assert not built.errors
        assert built.workflow.engine_type == "wetlands"
        assert built.workflow.execution == "sequential"
        built.workflow.get_environment("platform-worker-numbers").max_workers = 1
        built.workflow.compute()

        result = ResultStoreService(storage_path=tmp_path / "results", tool_registry=registry)
        dataframe = result.get_latest_dataframe("worker")
        assert dataframe is not None
        assert list(dataframe.index) == ["row0", "row1", "row2"]
        assert dataframe["multiplied"].tolist() == [6, 9, 12]
        assert all(pid != os.getpid() for pid in dataframe["process_id"])
        assert len(set(dataframe["process_id"])) == 1
        # Canonical cached DataFrames store asset paths relative to their record.
        record_dir = result.get_latest_record_dir("worker")
        assert record_dir is not None
        relative_reports = [Path(value) for value in dataframe["report"]]
        assert all(not path.is_absolute() for path in relative_reports)
        reports = [(record_dir / path).resolve() for path in relative_reports]
        assert len(set(reports)) == 3
        assert all(path.is_relative_to(record_dir.resolve()) for path in reports)
        assert [path.read_text() for path in reports] == [
            "2 * 3 = 6\n", "3 * 3 = 9\n", "4 * 3 = 12\n",
        ]
    finally:
        try:
            # Surface cleanup failures instead of relying on the reset helper's
            # best-effort shutdown, so leaked workers fail this acceptance test.
            get_shared_environment_manager().close()
        finally:
            _reset_shared_manager()
