"""Tests for workflow filesystem persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioimageflow_server.models.graph import GraphState, NodeState
from bioimageflow_server.models.tools import PackageInfo
from bioimageflow_server.models.workflow import WorkflowCreate, WorkflowSaveBody, WorkflowUpdate
from bioimageflow_server.services.tool_registry import ToolRegistryService
from bioimageflow_server.services.workflow_store import WorkflowStoreService


@pytest.fixture
def registry() -> ToolRegistryService:
    reg = ToolRegistryService()
    reg.register_package(
        "missing-pkg",
        PackageInfo(
            name="missing-pkg",
            installed_versions=["1.0.0"],
            active_version="1.0.0",
            tools={"1.0.0": ["ExistingTool"]},
        ),
    )
    return reg


@pytest.fixture
def store(tmp_path: Path, registry: ToolRegistryService) -> WorkflowStoreService:
    return WorkflowStoreService(
        root_dir=tmp_path / "workflows",
        tool_registry=registry,
        storage_base_dir=tmp_path / "outputs",
    )


def test_create_list_and_get_empty_workflow(store: WorkflowStoreService) -> None:
    info = store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))
    assert info.name == "wf"
    assert info.display_name == "Workflow"
    assert info.storage_path is not None
    assert [item.name for item in store.list_workflows()] == ["wf"]

    workflow = store.get_workflow("wf")
    assert workflow.info.name == "wf"
    assert workflow.graph == GraphState(nodes=[], edges=[])
    assert workflow.gui == {"nodes": {}}


def test_get_storage_path_reads_metadata_directly(store: WorkflowStoreService) -> None:
    info = store.create_workflow(WorkflowCreate(name="wf"))

    assert store.get_storage_path("wf") == Path(info.storage_path)


def test_save_preserves_invalid_graph_losslessly(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    graph = GraphState(
        nodes=[
            NodeState(
                id="bad",
                name="Bad",
                tool_name="MissingTool",
                position=(12, 34),
                parameters={"value": 1},
            )
        ],
        edges=[],
    )

    store.save_workflow("wf", WorkflowSaveBody(graph=graph))
    restored = store.get_workflow("wf")

    assert restored.graph == graph
    assert restored.missing_tools == []
    raw = json.loads((store.root_dir / "wf.json").read_text())
    assert raw["graph"]["nodes"][0]["tool_name"] == "MissingTool"
    assert raw["workflow"]["nodes"] == []


def test_legacy_file_reports_missing_packages_and_tools(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "workflow": {
            "nodes": [
                {
                    "name": "n1",
                    "tool_class": "RemovedTool",
                    "tool_package": "missing-pkg",
                    "tool_package_version": "9.9.9",
                    "constants": {},
                }
            ],
            "edges": [],
        },
        "gui": {"nodes": {"n1": {"position": [1, 2]}}},
        "metadata": {"display_name": "Legacy"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    (store.root_dir / "legacy.json").write_text(json.dumps(raw), encoding="utf-8")

    workflow = store.get_workflow("legacy")

    assert workflow.graph.nodes[0].id == "n1"
    assert workflow.missing_packages[0].package_name == "missing-pkg"
    assert workflow.missing_packages[0].required_version == "9.9.9"
    assert workflow.missing_tools[0].node_id == "n1"
    assert workflow.missing_tools[0].tool_name == "RemovedTool"


def test_duplicate_and_update_metadata(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="wf", display_name="Workflow"))

    updated = store.patch_workflow(
        "wf",
        WorkflowUpdate(action="update", display_name="Renamed", description="desc"),
    )
    assert updated.display_name == "Renamed"
    assert updated.description == "desc"

    duplicate = store.patch_workflow(
        "wf",
        WorkflowUpdate(action="duplicate", new_name="copy", display_name="Copy"),
    )
    assert duplicate.name == "copy"
    assert duplicate.display_name == "Copy"
    assert store.get_workflow("copy").info.name == "copy"


def test_delete_removes_only_managed_storage(
    tmp_path: Path,
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(
        WorkflowCreate(
            name="wf",
            storage_path=str(tmp_path / "external"),
        )
    )
    managed = store.storage_base_dir / "wf"
    managed.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()

    store.delete_workflow("wf")

    assert not (store.root_dir / "wf.json").exists()
    assert not managed.exists()
    assert external.exists()


def test_suggest_name(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    store.create_workflow(WorkflowCreate(name="wf_2"))
    assert store.suggest_name("wf") == "wf_3"
