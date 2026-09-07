"""Tests for the reusable manual-QA fixture command."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from bioimageflow_server.models.graph import DataFrameEdge, PositionalInputPort
from bioimageflow_server.models.workflow import WorkflowDocument
from bioimageflow_server.services.graph_builder import build_workflow
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService
from tests.manual_qa import MARKER_NAME, MARKER_SCHEMA, clean, prepare, verify


@pytest.mark.integration
@pytest.mark.parametrize("nested", [False, True])
def test_imported_qa_workflow_runs_after_reopening(tmp_path: Path, nested: bool) -> None:
    root = tmp_path / "manual-qa"
    prepare(root)
    workflows = root / "workspace" / "workflows"
    registry = ToolRegistryService()
    registry.register_custom_tools_directory(workflows / "QA" / "Reference Workflow" / "tools")
    store = WorkflowStoreService(workflows, registry)
    if nested:
        archive = (root / "imports" / "qa-nested-parent.bioimageflow.zip").read_bytes()
    else:
        _, archive = store.export_workflow_archive("QA/Reference Workflow")
    store.import_workflow_archive(archive, name_override="imported")

    # Use a fresh process to prove restart independence and keep execution-engine
    # initialization out of the parent test process's global state.
    reopened = subprocess.run(
        [sys.executable, "-c", """
from pathlib import Path
import sys
from bioimageflow_server.services.graph_validator import GraphValidationService
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService

registry = ToolRegistryService()
store = WorkflowStoreService(Path(sys.argv[1]), registry)
graph = store.get_workflow("imported").graph
validated = GraphValidationService(registry).validate_with_compilation(
    graph, storage_path=store.get_storage_path("imported"),
)
assert validated.validation.valid, validated.validation.errors
assert validated.compilation.workflow.compute(dev_mode=True)[sys.argv[2]].tolist() == [2, 3, 4]
""", str(workflows), "Nested result" if nested else "Incremented number"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert reopened.returncode == 0, reopened.stdout + reopened.stderr


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
    assert not list(root.rglob("__pycache__"))
    assert not list(root.rglob("*.pyc"))
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

    with zipfile.ZipFile(root / "imports" / "qa-nested-parent.bioimageflow.zip") as archive:
        archive_payload = json.loads(archive.read("workflow.json"))
    archived_workflow = archive_payload["workflow"]
    assert archived_workflow["edges"][0]["type"] == "dataframe"
    archived_child = archived_workflow["nodes"][1]["workflow"]
    assert archived_child["interface"]["inputs"][0]["kind"] == "dataframe"
    increment_source = next(
        source["source"]
        for source in archive_payload["custom_sources"]
        if source["filename"] == "qa_increment.py"
    )
    assert "QaIncrementInputs" not in increment_source

    registry = ToolRegistryService()
    registry.register_custom_tools_directory(
        root / "workspace" / "workflows" / "QA" / "Reference Workflow" / "tools"
    )
    store = WorkflowStoreService(root / "workspace" / "workflows", registry)
    reference = store.get_workflow("QA/Reference Workflow")
    reference_edge = reference.graph.edges[0]
    assert isinstance(reference_edge, DataFrameEdge)
    assert reference_edge.target_position == 0

    child = store.get_workflow("QA/Nested Child")
    child_input = child.graph.interface.inputs[0]
    assert child_input.id == "numbers-dataframe-input"
    assert child_input.kind == "dataframe"
    assert isinstance(child_input.targets[0].port, PositionalInputPort)
    assert child_input.targets[0].port.index == 0

    parent = store.get_workflow("QA/Nested Parent")
    parent_edge = parent.graph.edges[0]
    assert isinstance(parent_edge, DataFrameEdge)
    assert parent_edge.target_input == "numbers-dataframe-input"

    controlled_failure = store.get_workflow("QA/Controlled Failure")
    failure_edge = controlled_failure.graph.edges[0]
    assert isinstance(failure_edge, DataFrameEdge)
    assert failure_edge.target_position == 0

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

    for workflow_id, output_name in (
        ("QA/Reference Workflow", "Incremented number"),
        ("QA/Nested Parent", "Nested result"),
    ):
        workflow = store.get_workflow(workflow_id)
        built = build_workflow(
            workflow.graph,
            registry,
            storage_path=store.get_storage_path(workflow_id),
        )
        result = built.workflow.compute(dev_mode=True)
        assert result[output_name].tolist() == [2, 3, 4]

    built_failure = build_workflow(
        controlled_failure.graph,
        registry,
        storage_path=store.get_storage_path("QA/Controlled Failure"),
    )
    with pytest.raises(RuntimeError, match="Intentional manual QA failure"):
        built_failure.workflow.compute(dev_mode=True)


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
