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
        assert include_custom_tools is False
        return self.data


class _WorkflowApi:
    loaded_paths: list[Path] = []
    imported_archives: list[tuple[Path, Path]] = []
    loaded_workflow = _LoadedWorkflow()

    @classmethod
    def load(cls, path: Path) -> _LoadedWorkflow:
        cls.loaded_paths.append(path)
        return cls.loaded_workflow

    @classmethod
    def import_archive(cls, path: Path, destination: Path) -> _LoadedWorkflow:
        cls.imported_archives.append((path, destination))
        return cls.loaded_workflow

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> _LoadedWorkflow:
        cls.loaded_workflow = _LoadedWorkflow(data)
        return cls.loaded_workflow


def test_export_archive_delegates_to_bioimageflow_workflow_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text('{"workflow": {"nodes": [], "edges": []}}', encoding="utf-8")
    archive_path = tmp_path / "wf.bioimageflow.zip"

    BioImageFlowWorkflowArchiveAdapter().export_archive(workflow_path, archive_path)

    assert _WorkflowApi.loaded_workflow.exported_to == archive_path


def test_read_archive_delegates_to_bioimageflow_workflow_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _WorkflowApi.loaded_workflow = _LoadedWorkflow({"nodes": [{"name": "n1"}], "edges": []})
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"

    data = BioImageFlowWorkflowArchiveAdapter().read_archive(archive_path)

    assert _WorkflowApi.loaded_paths[-1] == archive_path
    assert data == {"nodes": [{"name": "n1"}], "edges": []}


def test_read_archive_can_delegate_extraction_to_bioimageflow_workflow_api(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _WorkflowApi.loaded_workflow = _LoadedWorkflow({"nodes": [{"name": "n1"}], "edges": []})
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"
    destination = tmp_path / "wf"

    data = BioImageFlowWorkflowArchiveAdapter().read_archive(
        archive_path,
        extract_to=destination,
    )

    assert _WorkflowApi.imported_archives[-1] == (archive_path, destination)
    assert data == {"nodes": [{"name": "n1"}], "edges": []}
