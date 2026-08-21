"""Tests for the reusable manual-QA fixture command."""

from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from bioimageflow_server.models.workflow import WorkflowDocument
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.manual_qa import MARKER_NAME, MARKER_SCHEMA, clean, prepare, verify


def test_prepare_builds_verified_reusable_qa_root(tmp_path: Path) -> None:
    root = tmp_path / "manual-qa"

    payload, created = prepare(root)

    assert created is True
    assert payload["schema"] == MARKER_SCHEMA
    assert verify(root) == payload
    assert (root / "inputs" / "qa-gradient.tif").is_file()
    assert (root / "inputs" / "qa-table.csv").is_file()
    assert (root / "packages" / "qa-manual-tools.zip").is_file()
    assert (root / "evidence").is_dir()
    assert (root / "exports").is_dir()
    for workflow_id in payload["workflows"]:
        document = root / "workspace" / "workflows" / Path(str(workflow_id)) / "workflow.json"
        WorkflowDocument.model_validate_json(document.read_text(encoding="utf-8"))

    valid_archives = {
        "qa_import_collision.bioimageflow.zip",
        "qa-nested-parent.bioimageflow.zip",
        "qa-workflow-and-results.zip",
    }
    for filename in valid_archives:
        assert zipfile.is_zipfile(root / "imports" / filename)
    assert not zipfile.is_zipfile(root / "imports" / "corrupt-workflow.bioimageflow.zip")

    registry = ToolRegistryService()
    registry.register_custom_tools_directory(
        root / "workspace" / "workflows" / "QA" / "Reference Workflow" / "tools"
    )
    store = WorkflowStoreService(root / "workspace" / "workflows", registry)
    for workflow_id in (
        "QA/Reference Workflow",
        "QA/Nested Child",
        "QA/Nested Parent",
        "QA/Controlled Failure",
    ):
        workflow = store.get_workflow(workflow_id)
        built = build_workflow(
            workflow.graph,
            registry,
            storage_path=store.get_storage_path(workflow_id),
        )
        assert built.errors == []


def test_prepare_is_idempotent_for_an_unchanged_root(tmp_path: Path) -> None:
    root = tmp_path / "manual-qa"
    first, created = prepare(root)

    second, created_again = prepare(root)

    assert created is True
    assert created_again is False
    assert second == first


def test_prepare_and_verify_reject_modified_fixtures(tmp_path: Path) -> None:
    root = tmp_path / "manual-qa"
    prepare(root)
    (root / "inputs" / "qa-table.csv").write_text("modified\n", encoding="utf-8")

    with pytest.raises(ValueError, match="were modified"):
        verify(root)
    with pytest.raises(ValueError, match="were modified"):
        prepare(root)


def test_clean_requires_a_valid_marker(tmp_path: Path) -> None:
    unmarked = tmp_path / "unmarked"
    unmarked.mkdir()
    (unmarked / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="Not a generated"):
        clean(unmarked)

    assert (unmarked / "keep.txt").is_file()


def test_clean_removes_only_a_marked_root(tmp_path: Path) -> None:
    root = tmp_path / "manual-qa"
    prepare(root)
    marker = json.loads((root / MARKER_NAME).read_text(encoding="utf-8"))
    assert marker["schema"] == MARKER_SCHEMA

    clean(root)

    assert not root.exists()


def test_root_must_be_absolute(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        from tests.manual_qa import _resolved_root

        _resolved_root("relative/path")
