"""Tests for the BioImageFlow workflow archive adapter boundary."""

from __future__ import annotations

import json
import zipfile
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
    inspected: list[dict[str, Any]] = []

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

    @classmethod
    def inspect_viewing_requirements(cls, data: dict[str, Any]):
        cls.inspected.append(data)
        return _ViewingManifest()


class _ViewingManifest:
    def to_dict(self) -> dict[str, Any]:
        return {"requirements": [], "complete": True, "issues": []}


def _write_archive(path: Path, document: dict[str, Any]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("workflow.json", json.dumps(document))


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


def test_read_archive_inspects_portable_document_without_loading_it(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"
    results_path = tmp_path / "results"
    document = {"nodes": [{"name": "n1"}], "edges": []}
    _write_archive(archive_path, document)
    _WorkflowApi.inspected = []
    _WorkflowApi.loaded_paths = []

    data = BioImageFlowWorkflowArchiveAdapter().read_archive(
        archive_path,
        storage_path=results_path,
    )

    assert _WorkflowApi.loaded_paths == []
    assert _WorkflowApi.inspected == [document]
    assert data == document


def test_read_archive_does_not_extract_or_import_packages(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(workflow_archive, "BioImageFlowWorkflow", _WorkflowApi)
    archive_path = tmp_path / "wf.bioimageflow.zip"
    destination = tmp_path / "wf"
    results_path = tmp_path / "results"
    document = {"nodes": [{"name": "n1"}], "edges": []}
    _write_archive(archive_path, document)
    _WorkflowApi.inspected = []
    _WorkflowApi.imported_archives = []

    data = BioImageFlowWorkflowArchiveAdapter().read_archive(
        archive_path,
        extract_to=destination,
        storage_path=results_path,
    )

    assert _WorkflowApi.imported_archives == []
    assert _WorkflowApi.inspected == [document]
    assert not destination.exists()
    assert data == document
