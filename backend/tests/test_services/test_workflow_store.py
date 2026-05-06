"""Tests for workflow filesystem persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bioimageflow_server.models.graph import ColumnRefEdge, GraphState, NodeState
from bioimageflow_server.models.tools import PackageInfo, ToolMetadata
from bioimageflow_server.models.workflow import (
    ExportedWorkflow,
    WorkflowCreate,
    WorkflowExportDocument,
    WorkflowSaveBody,
    WorkflowUpdate,
)
from bioimageflow_server.services.workflow_store import (
    WorkflowImportParseError,
    WorkflowStoreService,
)
from bioimageflow_server.services.tool_registry import ToolRegistryService


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


def _export_document(
    *,
    name: str = "imported",
    library: dict | None = None,
    graph: dict | None = None,
    gui: dict | None = None,
    metadata: dict | None = None,
) -> WorkflowExportDocument:
    return WorkflowExportDocument(
        exported_at="2026-04-30T10:30:00Z",
        workflow=ExportedWorkflow(
            name=name,
            display_name="Imported",
            description="desc",
            storage_path="/other/machine/outputs/imported",
            graph=graph or {"nodes": [], "edges": []},
            library=library or {"nodes": [], "edges": []},
            gui=gui or {"nodes": {}},
            metadata=metadata
            or {
                "display_name": "Imported",
                "description": "desc",
                "storage_path": "/other/machine/outputs/imported",
            },
        ),
        required_packages=[],
        local_tools=[],
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


def test_create_workflow_anchors_relative_storage_path_once(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(
        WorkflowCreate(name="wf", storage_path="relative-results")
    )

    expected = Path.cwd() / "relative-results"
    assert info.storage_path == str(expected)
    assert store.get_storage_path("wf") == expected

    raw = json.loads((store.root_dir / "wf.json").read_text())
    assert raw["metadata"]["storage_path"] == str(expected)
    assert raw["workflow"]["config"]["storage_path"] == str(expected)


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
        updated.name,
        WorkflowUpdate(action="duplicate", new_name="copy", display_name="Copy"),
    )
    assert duplicate.name == "copy"
    assert duplicate.display_name == "Copy"
    assert store.get_workflow("copy").info.name == "copy"

    duplicate_custom = store.patch_workflow(
        updated.name,
        WorkflowUpdate(
            action="duplicate",
            new_name="copy_custom",
            storage_path="copy-relative-results",
        ),
    )
    assert duplicate_custom.storage_path == str(Path.cwd() / "copy-relative-results")


def test_display_name_update_renames_file_and_managed_storage(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))
    old_storage = Path(info.storage_path)
    old_storage.mkdir(parents=True)
    marker = old_storage / "result.txt"
    marker.write_text("kept", encoding="utf-8")

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )

    assert updated.name == "new_workflow"
    assert updated.display_name == "New workflow"
    assert not (store.root_dir / "Untitled.json").exists()
    assert (store.root_dir / "new_workflow.json").exists()
    assert updated.storage_path == str(store.storage_base_dir / "new_workflow")
    assert not old_storage.exists()
    assert (store.storage_base_dir / "new_workflow" / "result.txt").read_text() == "kept"
    raw = json.loads((store.root_dir / "new_workflow.json").read_text())
    assert raw["metadata"]["storage_path"] == str(store.storage_base_dir / "new_workflow")
    assert raw["workflow"]["config"]["storage_path"] == str(store.storage_base_dir / "new_workflow")


def test_display_name_update_rejects_existing_target_managed_storage_without_old_source(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))
    old_storage = Path(info.storage_path)
    target_storage = store.storage_base_dir / "new_workflow"
    target_storage.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        store.patch_workflow(
            "Untitled",
            WorkflowUpdate(action="update", display_name="New workflow"),
        )

    assert not old_storage.exists()
    assert (store.root_dir / "Untitled.json").exists()
    assert not (store.root_dir / "new_workflow.json").exists()


def test_display_name_update_preserves_custom_storage_path(
    tmp_path: Path,
    store: WorkflowStoreService,
) -> None:
    custom_storage = tmp_path / "external-results"
    store.create_workflow(
        WorkflowCreate(
            name="Untitled",
            display_name="Untitled",
            storage_path=str(custom_storage),
        )
    )

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )

    assert updated.name == "new_workflow"
    assert updated.storage_path == str(custom_storage)


def test_update_workflow_anchors_relative_storage_path_once(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))

    updated = store.patch_workflow(
        "wf",
        WorkflowUpdate(action="update", storage_path="updated-relative-results"),
    )

    expected = Path.cwd() / "updated-relative-results"
    assert updated.storage_path == str(expected)
    raw = json.loads((store.root_dir / "wf.json").read_text())
    assert raw["metadata"]["storage_path"] == str(expected)
    assert raw["workflow"]["config"]["storage_path"] == str(expected)


def test_display_name_update_rejects_managed_target_collision_with_custom_storage(
    tmp_path: Path,
    store: WorkflowStoreService,
) -> None:
    custom_storage = tmp_path / "external-results"
    store.create_workflow(
        WorkflowCreate(
            name="Untitled",
            display_name="Untitled",
            storage_path=str(custom_storage),
        )
    )
    target_storage = store.storage_base_dir / "new_workflow"
    target_storage.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        store.patch_workflow(
            "Untitled",
            WorkflowUpdate(action="update", display_name="New workflow"),
        )

    workflow = store.get_workflow("Untitled")
    assert workflow.info.display_name == "Untitled"
    assert workflow.info.storage_path == str(custom_storage)
    assert target_storage.exists()


def test_display_name_update_without_valid_slug_keeps_canonical_identity(
    store: WorkflowStoreService,
) -> None:
    info = store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))

    updated = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="测试"),
    )

    assert updated.name == "Untitled"
    assert updated.display_name == "测试"
    assert updated.storage_path == info.storage_path
    assert (store.root_dir / "Untitled.json").exists()
    assert not (store.root_dir / ".json").exists()
    raw = json.loads((store.root_dir / "Untitled.json").read_text())
    assert raw["metadata"]["display_name"] == "测试"
    assert raw["metadata"]["storage_path"] == info.storage_path
    assert raw["workflow"]["config"]["storage_path"] == info.storage_path


def test_save_after_rename_retains_graph_edges(store: WorkflowStoreService) -> None:
    store.create_workflow(WorkflowCreate(name="Untitled", display_name="Untitled"))
    graph = GraphState(
        nodes=[
            NodeState(
                id="a",
                name="A",
                tool_name="MissingSource",
                position=(0, 0),
                parameters={},
            ),
            NodeState(
                id="b",
                name="B",
                tool_name="MissingTarget",
                position=(100, 0),
                parameters={},
            ),
        ],
        edges=[
            ColumnRefEdge(
                id="e1",
                source_node="a",
                target_node="b",
                source_output="result",
                target_input="image",
            )
        ],
    )

    renamed = store.patch_workflow(
        "Untitled",
        WorkflowUpdate(action="update", display_name="New workflow"),
    )
    store.save_workflow(renamed.name, WorkflowSaveBody(graph=graph))
    restored = store.get_workflow(renamed.name)

    assert restored.graph.edges == graph.edges


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


def test_suggest_name_skips_managed_storage_collisions(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="wf"))
    (store.storage_base_dir / "wf_2").mkdir(parents=True)

    assert store.suggest_name("wf") == "wf_3"


def test_export_workflow_preserves_raw_sections_and_required_packages(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "graph": {
            "nodes": [
                {
                    "id": "n1",
                    "name": "Node",
                    "tool_name": "ExistingTool",
                    "position": [1, 2],
                    "parameters": {},
                }
            ],
            "edges": [],
            "sub_workflow": {"kept": True},
        },
        "workflow": {
            "nodes": [
                {
                    "name": "n1",
                    "tool_class": "ExistingTool",
                    "tool_package": "missing-pkg",
                    "tool_package_version": "1.0.0",
                },
                {
                    "name": "n2",
                    "tool_class": "ExistingTool",
                    "tool_package": "missing-pkg",
                    "tool_package_version": "1.0.0",
                },
            ],
            "edges": [],
        },
        "gui": {"nodes": {"n1": {"position": [1, 2]}}},
        "metadata": {
            "display_name": "Workflow",
            "description": "desc",
            "storage_path": "/tmp/old",
        },
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    (store.root_dir / "wf.json").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert document.bioimageflow_export is True
    assert document.export_version == "1.0"
    assert document.workflow.name == "wf"
    assert document.workflow.graph == raw["graph"]
    assert document.workflow.library == raw["workflow"]
    assert document.workflow.gui == raw["gui"]
    assert document.workflow.metadata == raw["metadata"]
    assert [item.model_dump() for item in document.required_packages] == [
        {"name": "missing-pkg", "version": "1.0.0"}
    ]
    assert document.local_tools == []


def test_export_workflow_falls_back_to_registry_and_marks_local_tools(
    store: WorkflowStoreService,
    registry: ToolRegistryService,
) -> None:
    registry.register_tool(
        "RegistryTool",
        ToolMetadata(
            name="RegistryTool",
            display_name="Registry Tool",
            package="registry-pkg",
            package_version="2.0.0",
            tool_type="ProcessingTool",
        ),
    )
    raw = {
        "graph": {"nodes": [], "edges": []},
        "workflow": {
            "nodes": [
                {"name": "registry_1", "tool_class": "RegistryTool"},
                {"name": "local_1", "tool_class": "LocalTool"},
                {"name": "local_2", "tool_class": "LocalTool"},
            ],
            "edges": [],
        },
        "gui": {"nodes": {}},
        "metadata": {"display_name": "Workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    (store.root_dir / "wf.json").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert [item.model_dump() for item in document.required_packages] == [
        {"name": "registry-pkg", "version": "2.0.0"}
    ]
    assert len(document.local_tools) == 1
    assert document.local_tools[0].tool_name == "LocalTool"
    assert document.local_tools[0].node_ids == ["local_1", "local_2"]


def test_export_workflow_marks_graph_only_local_tools(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "graph": {
            "nodes": [
                {
                    "id": "local_1",
                    "name": "Local",
                    "tool_name": "LocalTool",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "edges": [],
        },
        "workflow": {"nodes": [], "edges": []},
        "gui": {"nodes": {}},
        "metadata": {"display_name": "Workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    (store.root_dir / "wf.json").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert document.required_packages == []
    assert len(document.local_tools) == 1
    assert document.local_tools[0].tool_name == "LocalTool"
    assert document.local_tools[0].node_ids == ["local_1"]


def test_export_workflow_collects_nested_sub_workflow_packages(
    store: WorkflowStoreService,
) -> None:
    raw = {
        "graph": {"nodes": [], "edges": []},
        "workflow": {
            "nodes": [
                {
                    "name": "sub_1",
                    "tool_class": "__sub_workflow__",
                    "sub_workflow": {
                        "nodes": [
                            {
                                "name": "inner_1",
                                "tool_class": "InnerTool",
                                "tool_package": "inner-pkg",
                                "tool_package_version": "0.1.0",
                            }
                        ],
                        "edges": [],
                    },
                }
            ],
            "edges": [],
        },
        "gui": {"nodes": {}},
        "metadata": {"display_name": "Workflow"},
    }
    store.root_dir.mkdir(parents=True, exist_ok=True)
    (store.root_dir / "wf.json").write_text(json.dumps(raw), encoding="utf-8")

    document = store.export_workflow("wf")

    assert [item.model_dump() for item in document.required_packages] == [
        {"name": "inner-pkg", "version": "0.1.0"}
    ]


def test_parse_import_document_rejects_malformed_json(
    store: WorkflowStoreService,
) -> None:
    with pytest.raises(WorkflowImportParseError):
        store.parse_import_document(b"{bad json")


def test_parse_import_document_rejects_non_utf_json(
    store: WorkflowStoreService,
) -> None:
    with pytest.raises(WorkflowImportParseError):
        store.parse_import_document(b"\xff")


def test_parse_import_document_reconstructs_missing_graph_from_library(
    store: WorkflowStoreService,
) -> None:
    payload = {
        "bioimageflow_export": True,
        "export_version": "1.0",
        "exported_at": "2026-04-30T10:30:00Z",
        "workflow": {
            "name": "legacy",
            "display_name": "Legacy",
            "description": None,
            "storage_path": None,
            "library": {
                "nodes": [
                    {
                        "name": "n1",
                        "display_name": "Node",
                        "tool_class": "ExistingTool",
                        "constants": {"threshold": 3},
                    }
                ],
                "edges": [],
            },
            "gui": {"nodes": {"n1": {"position": [4, 5]}}},
            "metadata": {},
        },
        "required_packages": [],
        "local_tools": [],
    }

    document = store.parse_import_document(json.dumps(payload).encode())

    assert document.workflow.graph["nodes"][0]["id"] == "n1"
    assert document.workflow.graph["nodes"][0]["position"] == [4.0, 5.0]
    assert document.workflow.graph["nodes"][0]["parameters"] == {"threshold": 3}


@pytest.mark.parametrize(
    "payload",
    [
        {"bioimageflow_export": True, "export_version": "2.0"},
        {
            "bioimageflow_export": True,
            "export_version": "1.0",
            "exported_at": "2026-04-30T10:30:00Z",
            "workflow": {
                "name": "wf",
                "display_name": "Workflow",
                "description": None,
                "storage_path": None,
                "graph": [],
                "library": {"nodes": [], "edges": []},
                "gui": {"nodes": {}},
                "metadata": {},
            },
            "required_packages": [],
            "local_tools": [],
        },
    ],
)
def test_parse_import_document_rejects_invalid_payloads(
    store: WorkflowStoreService,
    payload: dict,
) -> None:
    with pytest.raises(ValueError):
        store.parse_import_document(json.dumps(payload).encode())


def test_import_workflow_saves_with_managed_storage_path(
    store: WorkflowStoreService,
) -> None:
    document = _export_document(name="imported")

    response = store.import_workflow(document)

    assert response.info.name == "imported"
    assert response.info.display_name == "Imported"
    assert response.info.storage_path == str(store.storage_base_dir / "imported")
    assert [item.name for item in store.list_workflows()] == ["imported"]
    raw = json.loads((store.root_dir / "imported.json").read_text(encoding="utf-8"))
    assert raw["metadata"]["storage_path"] == str(store.storage_base_dir / "imported")
    assert raw["workflow"]["config"]["storage_path"] == str(store.storage_base_dir / "imported")


def test_import_workflow_name_override_and_conflict(
    store: WorkflowStoreService,
) -> None:
    store.create_workflow(WorkflowCreate(name="imported"))
    document = _export_document(name="imported")

    with pytest.raises(FileExistsError):
        store.import_workflow(document)

    response = store.import_workflow(document, name_override="imported_copy")

    assert response.info.name == "imported_copy"
    assert (store.root_dir / "imported_copy.json").exists()


def test_import_workflow_reports_missing_packages_and_tools(
    store: WorkflowStoreService,
) -> None:
    library = {
        "nodes": [
            {
                "name": "removed_1",
                "tool_class": "RemovedTool",
                "tool_package": "missing-pkg",
                "tool_package_version": "9.9.9",
            }
        ],
        "edges": [],
    }
    graph = {
        "nodes": [
            {
                "id": "removed_1",
                "name": "Removed",
                "tool_name": "RemovedTool",
                "position": [0, 0],
                "parameters": {},
            }
        ],
        "edges": [],
    }
    document = _export_document(name="imported", library=library, graph=graph)

    response = store.import_workflow(document)

    assert response.missing_packages[0].package_name == "missing-pkg"
    assert response.missing_packages[0].required_version == "9.9.9"
    assert response.missing_tools[0].node_id == "removed_1"
    assert response.missing_tools[0].tool_name == "RemovedTool"


def test_import_workflow_preserves_sub_workflow_without_missing_outer_marker(
    store: WorkflowStoreService,
    registry: ToolRegistryService,
) -> None:
    registry.register_tool(
        "ExistingTool",
        ToolMetadata(
            name="ExistingTool",
            display_name="Existing Tool",
            package="missing-pkg",
            package_version="1.0.0",
            tool_type="ProcessingTool",
        ),
    )
    sub_workflow = {
        "nodes": [
            {
                "name": "inner_1",
                "tool_class": "ExistingTool",
                "tool_package": "missing-pkg",
                "tool_package_version": "1.0.0",
            }
        ],
        "edges": [],
    }
    library = {
        "nodes": [
            {
                "name": "sub_1",
                "tool_class": "__sub_workflow__",
                "sub_workflow": sub_workflow,
            }
        ],
        "edges": [],
    }
    document = _export_document(
        name="imported",
        library=library,
        graph={
            "nodes": [
                {
                    "id": "sub_1",
                    "name": "Sub",
                    "tool_name": "__sub_workflow__",
                    "position": [0, 0],
                    "parameters": {},
                }
            ],
            "edges": [],
        },
    )

    response = store.import_workflow(document)

    assert response.missing_packages == []
    assert response.missing_tools == []
    raw = json.loads((store.root_dir / "imported.json").read_text(encoding="utf-8"))
    assert raw["workflow"]["nodes"][0]["sub_workflow"] == sub_workflow


def test_import_workflow_preserves_raw_graph_nested_sub_workflow_fields(
    store: WorkflowStoreService,
) -> None:
    graph = {
        "nodes": [
            {
                "id": "sub_1",
                "name": "Sub",
                "tool_name": "__sub_workflow__",
                "position": [0, 0],
                "parameters": {},
                "sub_workflow": {
                    "nodes": [
                        {
                            "id": "inner_1",
                            "name": "Inner",
                            "tool_name": "InnerTool",
                            "position": [1, 2],
                            "parameters": {},
                        }
                    ],
                    "edges": [],
                },
            }
        ],
        "edges": [],
    }
    document = _export_document(name="imported", graph=graph)

    store.import_workflow(document)

    raw = json.loads((store.root_dir / "imported.json").read_text(encoding="utf-8"))
    assert raw["graph"]["nodes"][0]["sub_workflow"] == graph["nodes"][0]["sub_workflow"]
