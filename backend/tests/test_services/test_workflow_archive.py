"""Tests for the BioImageFlow workflow archive adapter boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bioimageflow_server.services import workflow_archive
from bioimageflow_server.services.workflow_archive import BioImageFlowWorkflowArchiveAdapter


class _LoadedWorkflow:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = data or {"nodes": [], "edges": []}
        self.exported_to: Path | None = None

    def export(self, path: Path) -> None:
        self.exported_to = path

    def to_dict(self, *, include_custom_tools: bool = False) -> dict[str, Any]:
        assert include_custom_tools is True
        return self.data


class _WorkflowApi:
    loaded_paths: list[tuple[Path, Path]] = []
    imported_archives: list[tuple[Path, Path, Path]] = []
    loaded_workflow = _LoadedWorkflow()

    @classmethod
    def load(cls, path: Path, *, storage_path: Path) -> _LoadedWorkflow:
        cls.loaded_paths.append((path, storage_path))
        return cls.loaded_workflow

    @classmethod
    def import_archive(
        cls,
        path: Path,
        destination: Path,
        *,
        storage_path: Path,
    ) -> _LoadedWorkflow:
        cls.imported_archives.append((path, destination, storage_path))
        return cls.loaded_workflow

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        storage_path: Path,
    ) -> _LoadedWorkflow:
        assert storage_path.name == "results"
        cls.loaded_workflow = _LoadedWorkflow(data)
        return cls.loaded_workflow


def test_export_archive_delegates_to_bioimageflow_workflow_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"
    results_path = tmp_path / "results"

    BioImageFlowWorkflowArchiveAdapter().export_archive(
        {"nodes": [], "edges": []},
        archive_path,
        storage_path=results_path,
    )

    assert _WorkflowApi.loaded_workflow.exported_to == archive_path


def test_read_archive_delegates_to_bioimageflow_workflow_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _WorkflowApi.loaded_workflow = _LoadedWorkflow({"nodes": [{"name": "n1"}], "edges": []})
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"
    results_path = tmp_path / "results"

    data = BioImageFlowWorkflowArchiveAdapter().read_archive(
        archive_path,
        storage_path=results_path,
    )

    assert _WorkflowApi.loaded_paths[-1] == (archive_path, results_path)
    assert data == {"nodes": [{"name": "n1"}], "edges": []}


def test_read_archive_can_delegate_extraction_to_bioimageflow_workflow_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _WorkflowApi.loaded_workflow = _LoadedWorkflow({"nodes": [{"name": "n1"}], "edges": []})
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"
    destination = tmp_path / "wf"
    results_path = tmp_path / "results"

    data = BioImageFlowWorkflowArchiveAdapter().read_archive(
        archive_path,
        extract_to=destination,
        storage_path=results_path,
    )

    assert _WorkflowApi.imported_archives[-1] == (
        archive_path,
        destination,
        results_path,
    )
    assert data == {"nodes": [{"name": "n1"}], "edges": []}
